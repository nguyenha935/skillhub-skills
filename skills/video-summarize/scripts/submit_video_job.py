import hashlib
import hmac
import json
import os
import sys
import time
from typing import Optional
from urllib.request import Request, urlopen

from config_loader import load_runtime_config


def classify_source(value: str) -> str:
    lower = value.lower()
    if 'youtube.com/watch' in lower or 'youtu.be/' in lower:
        return 'youtube_url'
    if value.startswith('http://') or value.startswith('https://'):
        return 'url'
    return 'file_path'


def first_env(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key, '').strip()
        if value:
            return value
    return ''


def parse_session_key(session_key: str) -> dict:
    parts = (session_key or '').split(':')
    if len(parts) < 5 or parts[0] != 'agent':
        return {}
    return {
        'agentId': parts[1].strip(),
        'channel': parts[2].strip(),
        'peerKind': parts[3].strip(),
        'chatId': parts[4].strip(),
    }


def enrich_callback_context(callback_context: Optional[dict]) -> Optional[dict]:
    callback_context = dict(callback_context or {})
    session_key = (
        str(callback_context.get('sessionKey', '')).strip()
        or first_env('SKILLHUB_SESSION_KEY', 'GOCLAW_SESSION_KEY', 'SESSION_KEY')
    )
    if not session_key:
        return None

    parsed = parse_session_key(session_key)
    callback_mode = (
        str(callback_context.get('callbackMode', '')).strip()
        or first_env('SKILLHUB_CALLBACK_MODE')
        or 'inject_then_channel_send'
    )

    channel = (
        str(callback_context.get('channel', '')).strip()
        or first_env('SKILLHUB_CHANNEL', 'CHANNEL', 'GOCLAW_CHANNEL')
        or parsed.get('channel', '')
    )
    chat_id = (
        str(callback_context.get('chatId', '')).strip()
        or first_env('SKILLHUB_CHAT_ID', 'CHAT_ID', 'TO', 'GOCLAW_CHAT_ID')
        or parsed.get('chatId', '')
    )
    peer_kind = (
        str(callback_context.get('peerKind', '')).strip()
        or first_env('SKILLHUB_PEER_KIND', 'PEER_KIND', 'GOCLAW_PEER_KIND')
        or parsed.get('peerKind', '')
    )
    agent_id = (
        str(callback_context.get('agentId', '')).strip()
        or first_env('SKILLHUB_AGENT_ID', 'AGENT_ID', 'GOCLAW_AGENT_ID')
        or parsed.get('agentId', '')
    )
    user_id = (
        str(callback_context.get('userId', '')).strip()
        or first_env('SKILLHUB_USER_ID', 'USER_ID', 'GOCLAW_USER_ID')
    )
    sender_id = (
        str(callback_context.get('senderId', '')).strip()
        or first_env(
            'SKILLHUB_SENDER_ID',
            'SENDER_ID',
            'SENDER',
            'SKILLHUB_FROM_ID',
            'FROM_ID',
            'GOCLAW_SENDER_ID',
        )
    )

    if not user_id:
        if channel and chat_id and peer_kind == 'group':
            user_id = f'group:{channel}:{chat_id}'
        elif chat_id:
            user_id = chat_id

    if not sender_id:
        sender_id = chat_id or user_id

    return {
        'sessionKey': session_key,
        'channel': channel,
        'chatId': chat_id,
        'userId': user_id,
        'senderId': sender_id,
        'peerKind': peer_kind,
        'agentId': agent_id,
        'callbackMode': callback_mode,
    }


def build_payload(
    source_type: str,
    source_ref: str,
    skill_slug: str = 'video-summarize',
    youtube_mode: str = 'auto',
    model: Optional[str] = None,
    callback_context: Optional[dict] = None,
) -> dict:
    job_type = 'youtube_summarize' if source_type == 'youtube_url' else 'video_summarize'
    payload = {
        'skillSlug': skill_slug,
        'jobType': job_type,
        'youtubeMode': youtube_mode,
        'sourceType': source_type,
        'sourceRef': source_ref,
    }
    if callback_context:
        payload['callbackContext'] = callback_context
    if model:
        payload['model'] = model
    return payload


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


def resolve_runtime_secret(signing_context: str = 'skillhub-internal-v1') -> str:
    shared_secret = os.environ.get('SKILLHUB_RUNTIME_SHARED_SECRET', '').strip()
    if shared_secret:
        return shared_secret

    gateway_token = os.environ.get('GOCLAW_GATEWAY_TOKEN', '').strip()
    return hmac.new(
        gateway_token.encode(),
        signing_context.encode(),
        hashlib.sha256,
    ).hexdigest()


def resolve_callback_context() -> Optional[dict]:
    raw = os.environ.get('SKILLHUB_CALLBACK_CONTEXT', '').strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                enriched = enrich_callback_context(parsed)
                if enriched:
                    return enriched
        except Exception:
            pass

    return enrich_callback_context(None)


def ensure_callback_context_for_remote_source(
    source_type: str,
    callback_context: Optional[dict],
) -> None:
    if source_type not in ('youtube_url', 'url'):
        return
    required_fields = (
        ('sessionKey', 'sessionKey'),
        ('channel', 'channel'),
        ('chatId', 'chatId'),
        ('userId', 'userId'),
        ('senderId', 'senderId'),
        ('peerKind', 'peerKind'),
        ('agentId', 'agentId'),
    )
    missing = [
        label
        for key, label in required_fields
        if not str((callback_context or {}).get(key, '')).strip()
    ]
    if not missing:
        return
    field_source_hints = (
        'Field source map: '
        'sessionKey<-event.sessionKey; '
        'channel<-event.channel; '
        'chatId<-event.chatId (fallback: parse part 5 from sessionKey); '
        'userId<-event.userId; '
        'senderId<-event.senderId; '
        'peerKind<-parse part 4 from sessionKey (direct|group); '
        'agentId<-event.agentId (fallback: parse part 2 from sessionKey). '
    )
    raise SystemExit(
        'MISSING_CALLBACK_ROUTE: Remote video jobs must include a full callback route so SkillHub can callback the same GoClaw conversation. '
        f"Missing: {', '.join(missing)}. "
        'Call this skill with SKILLHUB_CALLBACK_CONTEXT or pass '
        'SKILLHUB_SESSION_KEY + SKILLHUB_CHANNEL + SKILLHUB_CHAT_ID + SKILLHUB_USER_ID + SKILLHUB_SENDER_ID + SKILLHUB_PEER_KIND + SKILLHUB_AGENT_ID. '
        'Nếu chỉ có SKILLHUB_SESSION_KEY thì script sẽ tự suy ra route cơ bản từ sessionKey chuẩn '
        'agent:<agentId>:<channel>:<peerKind>:<chatId> và tự điền userId/senderId khi có thể. '
        + field_source_hints
    )


def submit(source: str, skill_slug: str = 'video-summarize') -> dict:
    config = load_runtime_config()
    source_type = classify_source(source)
    callback_context = resolve_callback_context()
    ensure_callback_context_for_remote_source(source_type, callback_context)
    payload = build_payload(
        source_type,
        source,
        skill_slug,
        youtube_mode=config.get('youtubeMode', 'auto'),
        model=config.get('defaultModel'),
        callback_context=callback_context,
    )
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    nonce = f'{timestamp}-{os.urandom(8).hex()}'
    runtime_secret = resolve_runtime_secret()
    headers = build_signed_headers(timestamp, nonce, body, runtime_secret)
    req = Request(
        f"{config.get('skillHubUrl', 'http://skillhub:4080')}/api/jobs",
        data=body.encode(),
        headers=headers,
        method='POST',
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: submit_video_job.py <url-or-youtube-url>')
    print(json.dumps(submit(sys.argv[1])))


if __name__ == '__main__':
    main()
