---
name: video-summarize
description: Summarize video from YouTube, direct URL, upload, or local file path via SkillHub.
license: All rights reserved
metadata:
  author: nguyenha935
  version: "1.0.3"
---

# video-summarize Skill

Summarize any video from a URL or local file path. Powered by SkillHub — a custom skill sidecar for GoClaw.

## Features

- **YouTube URLs**: Transcript-first extraction via youtubei + captionTracks; falls back to Gemini if no captions
- **Direct video URLs**: Downloads and uploads to Gemini Files API for native video understanding
- **Local files**: Streams file bytes to SkillHub via Gemini Files API
- **Credential rotation**: Round-robin across multiple Gemini API keys with automatic cooldown on failures
- **Job tracking**: Background worker with polling, retry, and per-job status tracking

## Usage

```bash
# From GoClaw agent: ask to summarize a video
"Please summarize this video: https://www.youtube.com/watch?v=..."

# Via skill shell script directly
./scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=..."
./scripts/run-video-summarize.sh "/local/path/to/video.mp4"
```

## Configuration

Runtime config (`assets/config.json`) read by GoClaw:

```json
{
  "skillHubUrl": "http://skillhub:4080",
  "defaultModel": "gemini-3.1-flash-lite-preview",
  "youtubeMode": "auto",
  "supportedFormats": ["mp4", "mkv", "webm", "mov", "avi"],
  "maxFileSizeBytes": 2147483648
}
```

## Architecture

```
GoClaw Agent
    │
    └── video-summarize skill
            │
            ├── run-video-summarize.sh  (router)
            ├── submit_video_job.py       (HMAC-signed POST to SkillHub)
            ├── upload_video_job.py       (stream local file → SkillHub)
            └── poll_video_job.py          (poll until done, print summary)
                    │
                    └── SkillHub (port 4080)
                            ├── Job Worker
                            ├── SQLite (jobs, credentials, sessions)
                            ├── Gemini Files API
                            └── YouTube Transcript API
```

## YouTube Modes

| Mode | Behavior |
|---|---|
| `auto` (default) | Try youtubei → captionTracks → Gemini fallback |
| `web` | Try youtubei → captionTracks, fail if no captions (no Gemini) |
| `gemini` | Skip transcript, go directly to Gemini |

## Requirements

- GoClaw with custom skill support
- SkillHub service running on port 4080
- Preferred: `SKILLHUB_RUNTIME_SHARED_SECRET` in environment for runtime HMAC auth
- Backward-compatible fallback: `GOCLAW_GATEWAY_TOKEN` if no dedicated SkillHub runtime secret is configured
- At least one Gemini API key configured in SkillHub admin UI
