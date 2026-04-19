import hashlib
import hmac
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from submit_video_job import classify_source, build_payload, build_signed_headers, resolve_runtime_secret
from upload_video_job import (
    stream_file_chunks,
    build_upload_metadata,
    build_multipart_body,
    build_upload_auth_headers,
)
from config_loader import load_runtime_config


def test_classify_source():
    assert classify_source('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'youtube_url'
    assert classify_source('https://youtu.be/dQw4w9WgXcQ') == 'youtube_url'
    assert classify_source('https://youtube.com/watch?v=abc') == 'youtube_url'
    assert classify_source('https://example.com/video.mp4') == 'url'
    assert classify_source('http://example.com/video.mkv') == 'url'
    assert classify_source('/workspace/video.mkv') == 'file_path'
    assert classify_source('video.mp4') == 'file_path'
    print('classify_source: OK')


def test_build_payload():
    payload = build_payload('url', 'https://cdn.example.com/test.mp4', 'video-summarize')
    assert payload['sourceType'] == 'url'
    assert payload['skillSlug'] == 'video-summarize'
    assert payload['jobType'] == 'video_summarize'

    youtube_payload = build_payload(
        'youtube_url',
        'https://youtube.com/watch?v=abc',
        'video-summarize',
    )
    assert youtube_payload['sourceType'] == 'youtube_url'
    assert youtube_payload['jobType'] == 'youtube_summarize'
    print('build_payload: OK')


def test_build_signed_headers():
    headers = build_signed_headers('1234567890', 'nonce123', '{"test":true}', 'secret123')
    assert 'X-SkillHub-Timestamp' in headers
    assert 'X-SkillHub-Nonce' in headers
    assert 'X-SkillHub-Body-SHA256' in headers
    assert 'X-SkillHub-Signature' in headers
    assert headers['X-SkillHub-Timestamp'] == '1234567890'
    assert headers['X-SkillHub-Nonce'] == 'nonce123'
    print('build_signed_headers: OK')


def test_resolve_runtime_secret_prefers_explicit_skillhub_secret():
    old_runtime = os.environ.get('SKILLHUB_RUNTIME_SHARED_SECRET')
    old_gateway = os.environ.get('GOCLAW_GATEWAY_TOKEN')
    try:
      os.environ['SKILLHUB_RUNTIME_SHARED_SECRET'] = 'runtime-secret'
      os.environ['GOCLAW_GATEWAY_TOKEN'] = 'gateway-secret'
      assert resolve_runtime_secret() == 'runtime-secret'
      print('resolve_runtime_secret explicit: OK')
    finally:
      if old_runtime is None:
          os.environ.pop('SKILLHUB_RUNTIME_SHARED_SECRET', None)
      else:
          os.environ['SKILLHUB_RUNTIME_SHARED_SECRET'] = old_runtime
      if old_gateway is None:
          os.environ.pop('GOCLAW_GATEWAY_TOKEN', None)
      else:
          os.environ['GOCLAW_GATEWAY_TOKEN'] = old_gateway


def test_stream_file_chunks():
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(b'a' * (2 * 1024 * 1024 + 123))
        path = handle.name
    try:
        chunks = list(stream_file_chunks(path, chunk_size=1024 * 1024))
        assert len(chunks) == 3, f'Expected 3 chunks, got {len(chunks)}'
        assert sum(len(chunk) for chunk in chunks) == 2 * 1024 * 1024 + 123
        print('stream_file_chunks: OK')
    finally:
        os.unlink(path)


def test_build_upload_metadata():
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as handle:
        path = handle.name
    try:
        meta = build_upload_metadata(path, 'video-summarize')
        assert meta['jobType'] == 'video_summarize'
        assert meta['sourceType'] == 'file_path'
        assert meta['sourceName'] == os.path.basename(path)
        assert 'sourceMimeType' in meta
        print('build_upload_metadata: OK')
    finally:
        os.unlink(path)


def test_load_runtime_config_prefers_asset_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as handle:
            json.dump({
                'skillHubUrl': 'http://skillhub.internal:4080',
                'defaultModel': 'gemini-test-model',
                'youtubeMode': 'web',
            }, handle)

        config = load_runtime_config(config_path)
        assert config['skillHubUrl'] == 'http://skillhub.internal:4080'
        assert config['defaultModel'] == 'gemini-test-model'
        assert config['youtubeMode'] == 'web'
        print('load_runtime_config: OK')


def test_build_multipart_body_contains_payload_and_file_bytes():
    payload = {
        'skillSlug': 'video-summarize',
        'jobType': 'video_summarize',
        'sourceType': 'file_path',
        'sourceRef': '/tmp/video.mp4',
        'sourceName': 'video.mp4',
        'sourceMimeType': 'video/mp4',
    }
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as handle:
        handle.write(b'video-bytes')
        path = handle.name
    try:
        body, content_type = build_multipart_body(payload, path)
        assert 'multipart/form-data' in content_type
        assert b'"skillSlug": "video-summarize"' in body
        assert b'video-bytes' in body
        assert b'filename="video.mp4"' in body
        print('build_multipart_body: OK')
    finally:
        os.unlink(path)


def test_build_upload_auth_headers_signs_payload_text():
    payload = {
        'skillSlug': 'video-summarize',
        'jobType': 'video_summarize',
        'sourceType': 'file_path',
        'sourceRef': '/tmp/video.mp4',
        'sourceName': 'video.mp4',
        'sourceMimeType': 'video/mp4',
    }
    payload_text = json.dumps(payload)
    headers = build_upload_auth_headers(
        payload_text=payload_text,
        runtime_secret='runtime-secret',
        timestamp='1234567890',
        nonce='nonce123',
    )
    expected_body_hash = hmac.new(
        b'',
        payload_text.encode(),
        hashlib.sha256,
    ).hexdigest()
    expected_signature = hmac.new(
        b'runtime-secret',
        f'1234567890nonce123{expected_body_hash}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert headers['X-SkillHub-Body-SHA256'] == expected_body_hash
    assert headers['X-SkillHub-Signature'] == expected_signature
    print('build_upload_auth_headers: OK')


if __name__ == '__main__':
    test_classify_source()
    test_build_payload()
    test_build_signed_headers()
    test_stream_file_chunks()
    test_build_upload_metadata()
    test_load_runtime_config_prefers_asset_file()
    test_build_multipart_body_contains_payload_and_file_bytes()
    test_build_upload_auth_headers_signs_payload_text()
    print('\nAll tests passed!')
