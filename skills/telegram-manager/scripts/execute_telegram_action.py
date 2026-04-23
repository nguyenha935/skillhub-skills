import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config_loader import load_runtime_config

TOKEN_PATTERN = re.compile(r'^\d{8,12}:[A-Za-z0-9_-]{20,}$')
INSTANCE_NAME_PATTERN = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')


def hash_request_body(body: str) -> str:
    return hmac.new(b'', body.encode(), hashlib.sha256).hexdigest()


def build_signed_headers(timestamp: str, nonce: str, body: str, secret: str) -> dict:
    body_hash = hash_request_body(body)
    sig_input = f'{timestamp}{nonce}{body_hash}'
    signature = hmac.new(secret.encode(), sig_input.encode(), hashlib.sha256).hexdigest()
    return {
        'X-SkillHub-Timestamp': timestamp,
        'X-SkillHub-Nonce': nonce,
        'X-SkillHub-Body-SHA256': body_hash,
        'X-SkillHub-Signature': signature,
        'Content-Type': 'application/json',
    }


def resolve_runtime_secret(signing_context: str) -> str:
    shared_secret = os.environ.get('SKILLHUB_RUNTIME_SHARED_SECRET', '').strip()
    if shared_secret:
        return shared_secret

    gateway_token = os.environ.get('GOCLAW_GATEWAY_TOKEN', '').strip()
    if gateway_token:
        return hmac.new(
            gateway_token.encode(),
            signing_context.encode(),
            hashlib.sha256,
        ).hexdigest()

    raise SystemExit('Missing SKILLHUB_RUNTIME_SHARED_SECRET or GOCLAW_GATEWAY_TOKEN')


def parse_payload_json(raw: str) -> dict:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'Invalid payload JSON: {exc}')
    if not isinstance(parsed, dict):
        raise SystemExit('Payload must be a JSON object')
    return parsed


def parse_envelope_json(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'Invalid envelope JSON: {exc}')
    if not isinstance(parsed, dict):
        raise SystemExit('Envelope must be a JSON object')
    return parsed


def parse_agent_key_from_session_key(session_key: str) -> str:
    text = str(session_key or '').strip()
    if not text.startswith('agent:'):
        return ''
    parts = text.split(':')
    if len(parts) < 2:
        return ''
    agent_key = parts[1].strip()
    return agent_key if INSTANCE_NAME_PATTERN.match(agent_key) else ''


def _sql_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _derive_aes_key(encryption_key: str) -> bytes:
    text = str(encryption_key or '').strip()
    if not text:
        raise SystemExit('Missing GOCLAW_ENCRYPTION_KEY in runtime environment')
    if re.fullmatch(r'[0-9a-fA-F]{64,}', text):
        key_bytes = bytes.fromhex(text)
    else:
        key_bytes = text.encode('utf-8')
    if len(key_bytes) < 32:
        raise SystemExit('GOCLAW_ENCRYPTION_KEY must resolve to at least 32 bytes')
    return key_bytes[:32]


def _extract_token_from_plaintext(plaintext: str) -> str:
    text = str(plaintext or '').strip()
    if not text:
        return ''
    if TOKEN_PATTERN.match(text):
        return text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return ''
    if isinstance(parsed, dict):
        candidate = str(parsed.get('token') or parsed.get('bot_token') or '').strip()
        if TOKEN_PATTERN.match(candidate):
            return candidate
    return ''


def _decrypt_goclaw_channel_credentials(encrypted_blob: str, encryption_key: str) -> str:
    text = str(encrypted_blob or '').strip()
    if not text.startswith('aes-gcm:'):
        raise SystemExit('Unsupported GoClaw channel credential format')
    encoded = text[len('aes-gcm:') :]
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise SystemExit(f'Invalid base64 credential payload: {exc}')
    if len(raw) <= 12 + 16:
        raise SystemExit('Invalid encrypted credential payload length')
    iv = raw[:12]
    ciphertext_and_tag = raw[12:]
    plaintext = AESGCM(_derive_aes_key(encryption_key)).decrypt(iv, ciphertext_and_tag, None).decode('utf-8', errors='replace')
    token = _extract_token_from_plaintext(plaintext)
    if not token:
        raise SystemExit('Could not extract Telegram bot token from decrypted channel credentials')
    return token


def _run_psql_query(query: str) -> list[str]:
    dsn = os.environ.get('GOCLAW_POSTGRES_DSN', '').strip()
    if not dsn:
        raise SystemExit('Missing GOCLAW_POSTGRES_DSN in runtime environment')
    cmd = ['psql', dsn, '-At', '-F', '\t', '-c', query]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip().splitlines()[:1]
        raise SystemExit(f'Failed to query GoClaw channel metadata: {"; ".join(detail) if detail else "unknown error"}')
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _append_candidate(candidates: list[str], value: str) -> None:
    item = str(value or '').strip()
    if not item or not INSTANCE_NAME_PATTERN.match(item):
        return
    if item not in candidates:
        candidates.append(item)


def _resolve_instance_candidates(chat_id: str) -> list[str]:
    candidates: list[str] = []
    _append_candidate(candidates, os.environ.get('SKILLHUB_TELEGRAM_CHANNEL_INSTANCE', ''))
    _append_candidate(candidates, parse_agent_key_from_session_key(os.environ.get('SKILLHUB_SESSION_KEY', '')))
    _append_candidate(candidates, os.environ.get('SKILLHUB_CHANNEL', ''))

    normalized_chat = str(chat_id or '').strip()
    if normalized_chat:
        chat_literal = _sql_quote(normalized_chat)
        lines = _run_psql_query(
            f"""
            SELECT channel_instance
            FROM channel_contacts
            WHERE channel_type = 'telegram'
              AND (
                sender_id = {chat_literal}
                OR user_id = {chat_literal}
                OR thread_id = {chat_literal}
              )
            ORDER BY last_seen_at DESC NULLS LAST
            LIMIT 10
            """
        )
        for line in lines:
            _append_candidate(candidates, line.split('\t')[0])

    if candidates:
        return candidates

    fallback = _run_psql_query(
        """
        SELECT name
        FROM channel_instances
        WHERE channel_type = 'telegram' AND enabled = true
        ORDER BY updated_at DESC
        """
    )
    unique = [line.split('\t')[0] for line in fallback if line]
    if len(unique) == 1:
        _append_candidate(candidates, unique[0])
        return candidates
    raise SystemExit(
        'Unable to resolve Telegram channel instance from chat context. '
        'Set SKILLHUB_TELEGRAM_CHANNEL_INSTANCE explicitly.'
    )


def _resolve_goclaw_channel_token(chat_id: str) -> str:
    encryption_key = os.environ.get('GOCLAW_ENCRYPTION_KEY', '').strip()
    if not encryption_key:
        raise SystemExit('Missing GOCLAW_ENCRYPTION_KEY in runtime environment')

    candidates = _resolve_instance_candidates(chat_id)
    for instance_name in candidates:
        row = _run_psql_query(
            f"""
            SELECT encode(credentials, 'escape')
            FROM channel_instances
            WHERE channel_type = 'telegram'
              AND enabled = true
              AND name = {_sql_quote(instance_name)}
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        if not row:
            continue
        encrypted_blob = row[0].split('\t')[0]
        if not encrypted_blob:
            continue
        return _decrypt_goclaw_channel_credentials(encrypted_blob, encryption_key)

    raise SystemExit(
        'No Telegram channel credentials found for resolved channel instances. '
        'Verify Telegram channel is configured in GoClaw.'
    )


def resolve_delegated_bot_token(envelope: dict) -> str:
    direct = str(envelope.get('delegatedBotToken') or envelope.get('telegramBotToken') or '').strip()
    if direct:
        if not TOKEN_PATTERN.match(direct):
            raise SystemExit('delegatedBotToken is present but invalid')
        envelope['delegatedBotToken'] = direct
        return direct

    env_direct = str(os.environ.get('SKILLHUB_TELEGRAM_BOT_TOKEN', '')).strip()
    if env_direct:
        if not TOKEN_PATTERN.match(env_direct):
            raise SystemExit('SKILLHUB_TELEGRAM_BOT_TOKEN is present but invalid')
        envelope['delegatedBotToken'] = env_direct
        return env_direct

    chat_id = str(envelope.get('chatId') or '').strip()
    if not chat_id:
        raise SystemExit('chatId is required to resolve Telegram credentials from GoClaw')
    resolved = _resolve_goclaw_channel_token(chat_id)
    envelope['delegatedBotToken'] = resolved
    return resolved


def build_envelope(args: argparse.Namespace, config: dict) -> dict:
    if args.envelope:
        envelope = parse_envelope_json(args.envelope)
    else:
        if not args.action or not args.chat_id:
            raise SystemExit('Missing required --action and --chat-id when envelope JSON is not provided')
        envelope = {
            'action': args.action,
            'chatId': str(args.chat_id),
            'payload': parse_payload_json(args.payload or '{}'),
        }
        if args.topic_id:
            envelope['topicId'] = str(args.topic_id)

    if 'payload' not in envelope or not isinstance(envelope['payload'], dict):
        envelope['payload'] = parse_payload_json(json.dumps(envelope.get('payload', {})))

    if args.confirm_token:
        envelope['confirmToken'] = args.confirm_token

    envelope['requestId'] = str(args.request_id or envelope.get('requestId') or uuid.uuid4())
    envelope['skillSlug'] = str(args.skill_slug or envelope.get('skillSlug') or config.get('skillSlug') or 'telegram-manager')

    provider_slug = str(args.provider_slug or envelope.get('providerSlug') or config.get('providerSlug') or '').strip()
    if provider_slug:
        envelope['providerSlug'] = provider_slug

    action = str(envelope.get('action', '')).strip()
    chat_id = str(envelope.get('chatId', '')).strip()
    if not action or not chat_id:
        raise SystemExit('Envelope requires non-empty action and chatId')

    envelope['action'] = action
    envelope['chatId'] = chat_id
    if 'topicId' in envelope and envelope['topicId'] is not None:
        envelope['topicId'] = str(envelope['topicId'])

    return envelope


def submit(envelope: dict, config: dict) -> dict:
    body = json.dumps(envelope, ensure_ascii=False)
    timestamp = str(int(time.time()))
    nonce = f'{timestamp}-{os.urandom(8).hex()}'
    secret = resolve_runtime_secret(str(config.get('signingContext', 'skillhub-internal-v1')))
    headers = build_signed_headers(timestamp, nonce, body, secret)

    skillhub_url = str(config.get('skillHubUrl', 'http://skillhub:4080')).rstrip('/')
    timeout_seconds = int(config.get('requestTimeoutSeconds', 30))

    request = Request(
        f'{skillhub_url}/api/telegram-manager/execute',
        data=body.encode('utf-8'),
        headers=headers,
        method='POST',
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode('utf-8', errors='replace')
            return json.loads(raw or '{}')
    except HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw or '{}')
        except json.JSONDecodeError:
            payload = {'ok': False, 'error': raw or str(exc)}
        payload.setdefault('ok', False)
        payload.setdefault('status', exc.code)
        return payload
    except URLError as exc:
        return {'ok': False, 'error': f'network_error:{exc}'}


def main() -> None:
    parser = argparse.ArgumentParser(description='Execute Telegram Manager action via SkillHub runtime endpoint')
    parser.add_argument('envelope', nargs='?', help='Full JSON envelope string')
    parser.add_argument('--action', help='Telegram manager action')
    parser.add_argument('--chat-id', dest='chat_id', help='Telegram chat ID')
    parser.add_argument('--topic-id', dest='topic_id', help='Telegram topic ID / message thread ID')
    parser.add_argument('--payload', help='JSON object payload for action')
    parser.add_argument('--request-id', dest='request_id', help='Idempotency key for request replay safety')
    parser.add_argument('--confirm-token', dest='confirm_token', help='Confirm token for risky operation step 2')
    parser.add_argument('--provider-slug', dest='provider_slug', help='Provider slug override (default from config)')
    parser.add_argument('--skill-slug', dest='skill_slug', help='Skill slug override (default telegram-manager)')

    args = parser.parse_args()
    config = load_runtime_config()
    envelope = build_envelope(args, config)
    resolve_delegated_bot_token(envelope)
    result = submit(envelope, config)
    print(json.dumps(result, ensure_ascii=False))

    if result.get('ok') is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
