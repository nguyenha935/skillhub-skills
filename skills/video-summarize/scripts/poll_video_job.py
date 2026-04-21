import hashlib
import hmac
import json
import os
import sys
import time
from urllib.request import Request, urlopen

from config_loader import load_runtime_config
from submit_video_job import resolve_runtime_secret

DEFAULT_SYNC_WAIT_SECONDS = 55
DEFAULT_POLL_INTERVAL_SECONDS = 1


def hash_request_body(body: str) -> str:
    return hmac.new(b'', body.encode(), hashlib.sha256).hexdigest()


def resolve_poll_settings(config: dict) -> dict:
    try:
        max_wait = int(config.get('syncWaitSeconds', DEFAULT_SYNC_WAIT_SECONDS))
    except (TypeError, ValueError):
        max_wait = DEFAULT_SYNC_WAIT_SECONDS

    try:
        poll_interval = int(config.get('pollIntervalSeconds', DEFAULT_POLL_INTERVAL_SECONDS))
    except (TypeError, ValueError):
        poll_interval = DEFAULT_POLL_INTERVAL_SECONDS

    return {
        'max_wait': max(5, min(max_wait, 55)),
        'poll_interval': max(1, min(poll_interval, 10)),
    }


def build_auth_headers(runtime_secret: str) -> dict:
    timestamp = str(int(time.time()))
    nonce = f'{timestamp}-{os.urandom(8).hex()}'
    body_hash = hash_request_body('')
    return {
        'X-SkillHub-Timestamp': timestamp,
        'X-SkillHub-Nonce': nonce,
        'X-SkillHub-Body-SHA256': body_hash,
        'X-SkillHub-Signature': hmac.new(
            runtime_secret.encode(),
            f'{timestamp}{nonce}{body_hash}'.encode(),
            hashlib.sha256,
        ).hexdigest(),
    }


def fetch_json(url: str, runtime_secret: str):
    headers = build_auth_headers(runtime_secret)
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def fetch_result(job_id: str, config: dict, runtime_secret: str):
    base_url = config.get('skillHubUrl', 'http://skillhub:4080')
    return fetch_json(f'{base_url}/api/jobs/{job_id}/result', runtime_secret)


def fetch_job(job_id: str, config: dict, runtime_secret: str):
    base_url = config.get('skillHubUrl', 'http://skillhub:4080')
    return fetch_json(f'{base_url}/api/jobs/{job_id}', runtime_secret)


def mark_consumed_sync(job_id: str, config: dict, runtime_secret: str):
    base_url = config.get('skillHubUrl', 'http://skillhub:4080')
    headers = build_auth_headers(runtime_secret)
    headers['Content-Type'] = 'application/json'
    req = Request(
        f'{base_url}/api/jobs/{job_id}/consume-sync',
        data=b'',
        headers=headers,
        method='POST',
    )
    try:
        with urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def poll_result(
    job_id: str,
    max_wait=None,
    config=None,
    runtime_secret=None,
    fetch_result_fn=None,
    fetch_job_fn=None,
    sleep_fn=time.sleep,
    now_fn=time.time,
) -> dict:
    config = config or load_runtime_config()
    runtime_secret = runtime_secret or resolve_runtime_secret()
    settings = resolve_poll_settings(config)
    max_wait = settings['max_wait'] if max_wait is None else max_wait
    poll_interval = settings['poll_interval']
    fetch_result_fn = fetch_result_fn or fetch_result
    fetch_job_fn = fetch_job_fn or fetch_job

    deadline = now_fn() + max_wait
    last_job_status = 'processing'

    while now_fn() < deadline:
        result = fetch_result_fn(job_id, config, runtime_secret)
        if isinstance(result, dict) and result.get('status') in ('completed', 'failed'):
            return result

        job = fetch_job_fn(job_id, config, runtime_secret)
        if isinstance(job, dict) and job.get('status'):
            last_job_status = job.get('status')

        if now_fn() >= deadline:
            break
        sleep_fn(poll_interval)

    job = fetch_job_fn(job_id, config, runtime_secret)
    if isinstance(job, dict) and job.get('status'):
        last_job_status = job.get('status')

    return {
        'status': 'pending',
        'jobId': job_id,
        'jobStatus': last_job_status or 'processing',
    }


def main():
    if len(sys.argv) < 2:
        job_input = sys.stdin.read().strip()
        if not job_input:
            print(json.dumps({'error': 'No job input provided'}))
            sys.exit(1)
        try:
            job = json.loads(job_input)
        except Exception:
            print(json.dumps({'error': f'Invalid job JSON: {job_input[:200]}'}))
            sys.exit(1)
    else:
        job = json.loads(sys.argv[1])

    job_id = job.get('id')
    if not job_id:
        print(json.dumps({'error': 'No job id in response', 'job': job}))
        sys.exit(1)

    result = poll_result(job_id)
    if result.get('status') == 'completed' and result.get('resultJson'):
        # Best-effort signal: this result was already delivered synchronously
        # in the current tool run, so async callback can be skipped.
        mark_consumed_sync(job_id, load_runtime_config(), resolve_runtime_secret())
        try:
            data = json.loads(result['resultJson'])
            print(data.get('summary', result['resultJson']))
        except Exception:
            print(result.get('resultJson', result))
    elif result.get('status') == 'failed':
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)
    elif result.get('status') == 'pending':
        status = result.get('jobStatus', 'processing')
        callback_state = str(job.get('callbackState') or '').strip()
        callback_note = (
            'SkillHub sẽ tự gửi kết quả cuối về đúng session hiện tại khi job hoàn tất.'
            if callback_state
            else 'Lần gọi này không kèm session callback, nên chưa thể tự đẩy kết quả về lại cùng phiên chat.'
        )
        print(
            f'ASYNC_PENDING job_id={job_id} status={status} callback_state={callback_state or "none"}.\n'
            'PENDING_RULES: wait_only,no_pre_summary,no_recall_same_input_in_same_run.\n'
            'BẮT BUỘC: chỉ trả lời ngắn gọn rằng hệ thống đang xử lý nền và sẽ gửi lại khi xong.\n'
            'BẮT BUỘC: không được tạo, suy diễn, hoặc trích dẫn bất kỳ nội dung tóm tắt video nào trước khi callback của đúng job_id này quay về.\n'
            'BẮT BUỘC: không gọi lại video-summarize cho cùng input trong cùng run hiện tại (chỉ áp dụng cho run hiện tại; yêu cầu mới ở lượt sau vẫn được gọi tool bình thường).\n'
            f'{callback_note}'
        )
    else:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
