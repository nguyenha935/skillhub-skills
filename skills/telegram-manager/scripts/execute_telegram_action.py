import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config_loader import load_runtime_config


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
    result = submit(envelope, config)
    print(json.dumps(result, ensure_ascii=False))

    if result.get('ok') is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
