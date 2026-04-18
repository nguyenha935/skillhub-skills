import hashlib
import hmac
import json
import os
import sys
import time
from urllib.request import Request, urlopen

from config_loader import load_runtime_config
from submit_video_job import resolve_runtime_secret

POLL_INTERVAL = 3


def poll_result(job_id: str, max_wait=600) -> dict:
    config = load_runtime_config()
    runtime_secret = resolve_runtime_secret()

    deadline = time.time() + max_wait
    while time.time() < deadline:
        timestamp = str(int(time.time()))
        nonce = f'{timestamp}-{os.urandom(8).hex()}'
        body_hash = hashlib.sha256(b'').hexdigest()
        headers = {
            'X-SkillHub-Timestamp': timestamp,
            'X-SkillHub-Nonce': nonce,
            'X-SkillHub-Body-SHA256': body_hash,
            'X-SkillHub-Signature': hmac.new(
                runtime_secret.encode(),
                f'{timestamp}{nonce}{body_hash}'.encode(),
                hashlib.sha256,
            ).hexdigest(),
        }

        req = Request(f"{config.get('skillHubUrl', 'http://skillhub:4080')}/api/jobs/{job_id}/result", headers=headers)
        try:
            with urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                if result.get('status') in ('completed', 'failed'):
                    return result
        except Exception:
            pass

        time.sleep(POLL_INTERVAL)

    return {'error': 'timeout', 'jobId': job_id}


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
        try:
            data = json.loads(result['resultJson'])
            print(data.get('summary', result['resultJson']))
        except Exception:
            print(result.get('resultJson', result))
    elif result.get('status') == 'failed':
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)
    else:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
