---
name: video-summarize
description: Summarize video from YouTube, direct URL, upload, or local file path via SkillHub.
license: All rights reserved
metadata:
  author: nguyenha935
  version: "1.0.6"
---

# video-summarize Skill

Summarize video from YouTube, direct video URLs, or local file paths through SkillHub.

## Features

- YouTube URLs: transcript-first extraction, with Gemini fallback when captions are unavailable.
- Direct video URLs: SkillHub downloads the video and uploads it to Gemini Files API.
- Local files: stream file bytes to SkillHub, then summarize with Gemini Files API.
- Background jobs: SkillHub handles long-running work and can callback into the current GoClaw session.

## GoClaw Runtime Command

Always use `sh`. Do not call the script directly and do not use `bash`.

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=..."
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://cdn.example.com/video.mp4"
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "/local/path/to/video.mp4"
```

For long jobs, call `session_status` first, copy the current `Session:` value,
then pass it as `SKILLHUB_SESSION_KEY`:

```bash
SKILLHUB_SESSION_KEY="agent:..." sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=..."
```

## Runtime Rules For Agents

1. Use the command above directly.
2. Do not use `read_file` on `/app/data/skills-store/...`; this skill file already contains the required command.
3. Do not use `bash`; GoClaw containers may only provide POSIX `sh`.
4. Do not execute `./scripts/run-video-summarize.sh` directly; installed skill files may not preserve executable bits.
5. If the first command returns a JSON job failure, report that failure. Do not guess alternative script paths.

## Configuration

Runtime config is read from `assets/config.json` or defaults:

```json
{
  "skillHubUrl": "http://skillhub:4080",
  "defaultModel": "gemini-3.1-flash-lite-preview",
  "youtubeMode": "auto",
  "supportedFormats": ["mp4", "mkv", "webm", "mov", "avi"],
  "maxFileSizeBytes": 2147483648
}
```

## YouTube Modes

| Mode | Behavior |
|---|---|
| `auto` | Try transcript extraction first, then Gemini fallback. |
| `web` | Try transcript extraction only. |
| `gemini` | Skip transcript and use Gemini fallback directly. |

## Requirements

- GoClaw with custom skill support.
- SkillHub service reachable at `http://skillhub:4080`.
- Preferred: `SKILLHUB_RUNTIME_SHARED_SECRET` for HMAC auth.
- Backward-compatible fallback: `GOCLAW_GATEWAY_TOKEN`.
- At least one Gemini API key configured in SkillHub admin UI.
