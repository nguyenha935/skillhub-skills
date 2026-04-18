import hashlib
import hmac
import json
import os
import sys
import time
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
    model: str | None = None,
) -> dict:
    job_type = 'youtube_summarize' if source_type == 'youtube_url' else 'video_summarize'
    payload = {
        'skillSlug': skill_slug,
        'jobType': job_type,
        'youtubeMode': youtube_mode,
        'sourceType': source_type,
        'sourceRef': source_ref,
    }
    if model:
        payload['model'] = model
    return payload


def build_signed_headers(timestamp: str, nonce: str, body: str, secret: str) -> dict:
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    sig_input = f'{timestamp}{nonce}{body_hash}'
    signature = hmac.new(secret.encode(), sig_input.encode(), hashlib.sha256).hexdigest()
    return {
        'X-SkillHub-Timestamp': timestamp,
        'X-SkillHub-Nonce': nonce,
        'X-SkillHub-Body-SHA256': body_hash,
        'X-SkillHub-Signature': signature,
        'Content-Type': 'application/json',
    }


def submit(source: str, skill_slug: str = 'video-summarize') -> dict:
    config = load_runtime_config()
    source_type = classify_source(source)
    payload = build_payload(
        source_type,
        source,
        skill_slug,
        youtube_mode=config.get('youtubeMode', 'auto'),
        model=config.get('defaultModel'),
    )
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    nonce = f'{timestamp}-{os.urandom(8).hex()}'
    gateway_token = os.environ.get('GOCLAW_GATEWAY_TOKEN', '')
    runtime_secret = hmac.new(
        gateway_token.encode(),
        b'skillhub-internal-v1',
        hashlib.sha256,
    ).hexdigest()
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
