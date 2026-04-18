import hashlib
import hmac
import json
import mimetypes
import os
import time
import uuid
from urllib.request import Request, urlopen

from config_loader import load_runtime_config
from submit_video_job import resolve_runtime_secret


def stream_file_chunks(path: str, chunk_size: int = 1024 * 1024):
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def build_upload_metadata(
    path: str,
    skill_slug: str = 'video-summarize',
    youtube_mode: str = 'auto',
    model: str | None = None,
) -> dict:
    mime_type, _ = mimetypes.guess_type(path)
    payload = {
        'skillSlug': skill_slug,
        'jobType': 'video_summarize',
        'youtubeMode': youtube_mode,
        'sourceType': 'file_path',
        'sourceRef': path,
        'sourceName': os.path.basename(path),
        'sourceMimeType': mime_type or 'application/octet-stream',
    }
    if model:
        payload['model'] = model
    return payload


def build_multipart_body(payload: dict, path: str):
    boundary = f'----skillhub-{uuid.uuid4().hex}'
    body = bytearray()

    def write_text(text: str):
        body.extend(text.encode())

    write_text(f'--{boundary}\r\n')
    write_text('Content-Disposition: form-data; name="payload"\r\n')
    write_text('Content-Type: application/json\r\n\r\n')
    write_text(json.dumps(payload))
    write_text('\r\n')

    filename = payload.get('sourceName') or os.path.basename(path)
    mime_type = payload.get('sourceMimeType', 'application/octet-stream')
    write_text(f'--{boundary}\r\n')
    write_text(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
    )
    write_text(f'Content-Type: {mime_type}\r\n\r\n')
    for chunk in stream_file_chunks(path):
        body.extend(chunk)
    write_text('\r\n')
    write_text(f'--{boundary}--\r\n')

    return bytes(body), f'multipart/form-data; boundary={boundary}'


def submit_upload(path: str, skill_slug: str = 'video-summarize') -> dict:
    config = load_runtime_config()
    payload = build_upload_metadata(
        path,
        skill_slug,
        youtube_mode=config.get('youtubeMode', 'auto'),
        model=config.get('defaultModel'),
    )
    payload_text = json.dumps(payload)
    timestamp = str(int(time.time()))
    nonce = f'{timestamp}-{os.urandom(8).hex()}'
    runtime_secret = resolve_runtime_secret()
    body_hash = hashlib.sha256(payload_text.encode()).hexdigest()
    signature = hmac.new(
        runtime_secret.encode(),
        f'{timestamp}{nonce}{body_hash}'.encode(),
        hashlib.sha256,
    ).hexdigest()

    multipart_body, content_type = build_multipart_body(payload, path)
    headers = {
        'X-SkillHub-Timestamp': timestamp,
        'X-SkillHub-Nonce': nonce,
        'X-SkillHub-Body-SHA256': body_hash,
        'X-SkillHub-Signature': signature,
        'Content-Type': content_type,
    }
    req = Request(
        f"{config.get('skillHubUrl', 'http://skillhub:4080')}/api/jobs",
        data=multipart_body,
        headers=headers,
        method='POST',
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        raise SystemExit('usage: upload_video_job.py <path>')
    print(json.dumps(submit_upload(sys.argv[1])))
