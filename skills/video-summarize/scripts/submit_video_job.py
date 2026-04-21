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
                session_key = str(parsed.get('sessionKey', '')).strip()
                if session_key:
                    return {
                        'sessionKey': session_key,
                        'channel': str(parsed.get('channel', '')).strip(),
                        'chatId': str(parsed.get('chatId', '')).strip(),
                        'userId': str(parsed.get('userId', '')).strip(),
                        'senderId': str(parsed.get('senderId', '')).strip(),
                        'peerKind': str(parsed.get('peerKind', '')).strip(),
                        'agentId': str(parsed.get('agentId', '')).strip(),
                        'callbackMode': str(parsed.get('callbackMode', 'inject_then_channel_send')).strip() or 'inject_then_channel_send',
                    }
        except Exception:
            pass

    session_key = (
        os.environ.get('SKILLHUB_SESSION_KEY', '').strip()
        or os.environ.get('GOCLAW_SESSION_KEY', '').strip()
        or os.environ.get('SESSION_KEY', '').strip()
    )
    if not session_key:
        return None
    callback_mode = os.environ.get('SKILLHUB_CALLBACK_MODE', 'inject_then_channel_send').strip() or 'inject_then_channel_send'
    return {
        'sessionKey': session_key,
        'channel': os.environ.get('SKILLHUB_CHANNEL', '').strip(),
        'chatId': os.environ.get('SKILLHUB_CHAT_ID', '').strip(),
        'userId': os.environ.get('SKILLHUB_USER_ID', '').strip(),
        'senderId': os.environ.get('SKILLHUB_SENDER_ID', '').strip(),
        'peerKind': os.environ.get('SKILLHUB_PEER_KIND', '').strip(),
        'agentId': os.environ.get('SKILLHUB_AGENT_ID', '').strip(),
        'callbackMode': callback_mode,
    }


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
    raise SystemExit(
        'MISSING_CALLBACK_ROUTE: Remote video jobs must include a full callback route so SkillHub can callback the same GoClaw conversation. '
        f"Missing: {', '.join(missing)}. "
        'Call this skill with SKILLHUB_CALLBACK_CONTEXT or pass '
        'SKILLHUB_SESSION_KEY + SKILLHUB_CHANNEL + SKILLHUB_CHAT_ID + '
        'SKILLHUB_USER_ID + SKILLHUB_SENDER_ID + SKILLHUB_PEER_KIND + SKILLHUB_AGENT_ID.'
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
