import hashlib
import hmac
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from submit_video_job import (
    classify_source,
    build_payload,
    build_signed_headers,
    ensure_callback_context_for_remote_source,
    enrich_callback_context,
    resolve_runtime_secret,
)
import poll_video_job
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


def test_build_payload_includes_callback_context_when_present():
    payload = build_payload(
        'youtube_url',
        'https://youtube.com/watch?v=abc',
        'video-summarize',
        callback_context={
            'sessionKey': 'agent:test:zalo:group:123',
            'callbackMode': 'inject_then_chat_send',
        },
    )
    assert payload['callbackContext']['sessionKey'] == 'agent:test:zalo:group:123'
    print('build_payload callback context: OK')


def test_remote_sources_require_session_key_for_callback():
    try:
        ensure_callback_context_for_remote_source('url', None)
        raise AssertionError('Expected missing callback route failure for remote URL')
    except SystemExit as exc:
        assert 'MISSING_CALLBACK_ROUTE' in str(exc)
        assert 'Field source map' in str(exc)
    print('remote source callback route required: OK')


def test_remote_sources_allow_route_derived_from_session_key():
    ensure_callback_context_for_remote_source(
        'youtube_url',
        enrich_callback_context(
            {
                'sessionKey': 'agent:ly-content:bao-ly-zalo:direct:3497207824213987778',
            },
        ),
    )
    print('remote source route derived from session key: OK')


def test_remote_sources_reject_invalid_session_key_without_full_route():
    try:
        ensure_callback_context_for_remote_source(
            'youtube_url',
            enrich_callback_context(
                {
                    'sessionKey': 'invalid-session',
                    'channel': 'bao-ly-zalo',
                    'chatId': '3497207824213987778',
                },
            ),
        )
        raise AssertionError('Expected missing full callback route failure for invalid session key')
    except SystemExit as exc:
        assert 'MISSING_CALLBACK_ROUTE' in str(exc)
        assert 'peerKind' in str(exc)
        assert 'agentId' in str(exc)
    print('remote source invalid session key rejected: OK')


def test_remote_sources_allow_callback_when_full_route_present():
    ensure_callback_context_for_remote_source(
        'youtube_url',
        {
            'sessionKey': 'agent:test:zalo:direct:123',
            'channel': 'bao-ly-zalo',
            'chatId': '3497207824213987778',
            'userId': 'nguyenha935',
            'senderId': '3497207824213987778',
            'peerKind': 'direct',
            'agentId': 'ly-content',
            'callbackMode': 'inject_then_channel_send',
        },
    )
    print('remote source full callback route accepted: OK')


def test_local_file_path_does_not_require_session_key():
    ensure_callback_context_for_remote_source('file_path', None)
    print('local file path does not require session key: OK')


def test_enrich_callback_context_derives_route_from_session_key():
    enriched = enrich_callback_context({
        'sessionKey': 'agent:ly-content:bao-ly-zalo:group:5246639850626543237',
    })
    assert enriched is not None
    assert enriched['agentId'] == 'ly-content'
    assert enriched['channel'] == 'bao-ly-zalo'
    assert enriched['peerKind'] == 'group'
    assert enriched['chatId'] == '5246639850626543237'
    assert enriched['userId'] == 'group:bao-ly-zalo:5246639850626543237'
    assert enriched['senderId'] == '5246639850626543237'
    print('enrich_callback_context derive from session key: OK')


def test_enrich_callback_context_session_key_overrides_mismatched_route_fields():
    enriched = enrich_callback_context({
        'sessionKey': 'agent:ly-content:bao-ly-zalo:group:5246639850626543237',
        'channel': 'zalo_personal',
        'chatId': '999999',
        'peerKind': 'direct',
        'agentId': 'wrong-agent',
    })
    assert enriched is not None
    assert enriched['channel'] == 'bao-ly-zalo'
    assert enriched['chatId'] == '5246639850626543237'
    assert enriched['peerKind'] == 'group'
    assert enriched['agentId'] == 'ly-content'
    print('enrich_callback_context keeps route coherent with session key: OK')


def test_build_signed_headers():
    body = '{"test":true}'
    headers = build_signed_headers('1234567890', 'nonce123', body, 'secret123')
    assert 'X-SkillHub-Timestamp' in headers
    assert 'X-SkillHub-Nonce' in headers
    assert 'X-SkillHub-Body-SHA256' in headers
    assert 'X-SkillHub-Signature' in headers
    assert headers['X-SkillHub-Timestamp'] == '1234567890'
    assert headers['X-SkillHub-Nonce'] == 'nonce123'
    expected_body_hash = hmac.new(
        b'',
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    expected_signature = hmac.new(
        b'secret123',
        f'1234567890nonce123{expected_body_hash}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert headers['X-SkillHub-Body-SHA256'] == expected_body_hash
    assert headers['X-SkillHub-Signature'] == expected_signature
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


def test_build_upload_metadata_includes_callback_context_when_present():
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as handle:
        path = handle.name
    try:
        meta = build_upload_metadata(
            path,
            'video-summarize',
            callback_context={
                'sessionKey': 'agent:test:zalo:group:456',
                'callbackMode': 'inject_then_chat_send',
            },
        )
        assert meta['callbackContext']['sessionKey'] == 'agent:test:zalo:group:456'
        print('build_upload_metadata callback context: OK')
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


def test_resolve_poll_settings_uses_safe_sync_window():
    settings = poll_video_job.resolve_poll_settings({
        'syncWaitSeconds': 52,
        'pollIntervalSeconds': 3,
    })
    assert settings['max_wait'] == 52
    assert settings['poll_interval'] == 3
    print('resolve_poll_settings: OK')


def test_poll_result_returns_completed_when_job_finishes_within_sync_window():
    responses = iter([
        {'status': 'processing'},
        {'status': 'completed', 'resultJson': '{"summary":"done"}'},
    ])
    ticks = iter([0, 2, 4, 6])
    result = poll_video_job.poll_result(
        'job-1',
        max_wait=10,
        config={'skillHubUrl': 'http://skillhub:4080', 'syncWaitSeconds': 10, 'pollIntervalSeconds': 2},
        runtime_secret='secret',
        fetch_result_fn=lambda *_args, **_kwargs: next(responses),
        fetch_job_fn=lambda *_args, **_kwargs: {'status': 'processing'},
        sleep_fn=lambda *_args, **_kwargs: None,
        now_fn=lambda: next(ticks),
    )
    assert result['status'] == 'completed'
    print('poll_result completed within sync window: OK')


def test_poll_result_returns_pending_only_after_sync_window_expires():
    ticks = iter([0, 2, 4, 6, 8])
    result = poll_video_job.poll_result(
        'job-2',
        max_wait=4,
        config={'skillHubUrl': 'http://skillhub:4080', 'syncWaitSeconds': 4, 'pollIntervalSeconds': 2},
        runtime_secret='secret',
        fetch_result_fn=lambda *_args, **_kwargs: None,
        fetch_job_fn=lambda *_args, **_kwargs: {'status': 'processing'},
        sleep_fn=lambda *_args, **_kwargs: None,
        now_fn=lambda: next(ticks),
    )
    assert result['status'] == 'pending'
    assert result['jobStatus'] == 'processing'
    print('poll_result pending after sync window: OK')


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
    test_build_payload_includes_callback_context_when_present()
    test_remote_sources_require_session_key_for_callback()
    test_remote_sources_allow_route_derived_from_session_key()
    test_remote_sources_reject_invalid_session_key_without_full_route()
    test_remote_sources_allow_callback_when_full_route_present()
    test_local_file_path_does_not_require_session_key()
    test_enrich_callback_context_derives_route_from_session_key()
    test_enrich_callback_context_session_key_overrides_mismatched_route_fields()
    test_build_signed_headers()
    test_resolve_runtime_secret_prefers_explicit_skillhub_secret()
    test_stream_file_chunks()
    test_build_upload_metadata()
    test_build_upload_metadata_includes_callback_context_when_present()
    test_load_runtime_config_prefers_asset_file()
    test_resolve_poll_settings_uses_safe_sync_window()
    test_poll_result_returns_completed_when_job_finishes_within_sync_window()
    test_poll_result_returns_pending_only_after_sync_window_expires()
    test_build_multipart_body_contains_payload_and_file_bytes()
    test_build_upload_auth_headers_signs_payload_text()
    print('\nAll tests passed!')
