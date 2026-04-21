---
name: video-summarize
description: Summarize video from YouTube, direct URL, upload, or local file path via SkillHub.
license: All rights reserved
metadata:
  author: nguyenha935
  version: "1.0.11"
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

Mandatory preflight for every new run: read this file first.

```bash
sed -n '1,220p' /app/data/skills-store/video-summarize/1/SKILL.md
```

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

1. Before first skill call in a run, read `SKILL.md` using the preflight command above.
2. Use only the canonical command above directly.
3. Never use legacy path `/app/bundled-skills/summarize/scripts/run-summarize.sh`.
4. Do not use `read_file` on `/app/data/skills-store/...`; this skill file already contains the required command.
5. Do not use `bash`; GoClaw containers may only provide POSIX `sh`.
6. Do not execute `./scripts/run-video-summarize.sh` directly; installed skill files may not preserve executable bits.
7. If the first command returns a JSON job failure, report that failure. Do not guess alternative script paths.
8. For remote jobs (`youtube_url` and direct `url`), pass full callback route fields:
   `sessionKey`, `channel`, `chatId`, `userId`, `senderId`, `peerKind`, `agentId`.
9. If error is `MISSING_CALLBACK_ROUTE`, retry once with full callback fields.
10. Callback field source mapping:
    `sessionKey` <- event `sessionKey`
    `channel` <- event `channel`
    `chatId` <- event `chatId` (fallback: parse part 5 from `sessionKey`)
    `userId` <- event `userId`
    `senderId` <- event `senderId`
    `peerKind` <- parse part 4 from `sessionKey` (`direct` or `group`)
    `agentId` <- event `agentId` (fallback: parse part 2 from `sessionKey`)
    Route coherence rule: if any route field conflicts with parsed `sessionKey`, trust `sessionKey`.
11. Never expose internal markers/fields in user-facing messages: `[skillhub_memory]`, `[[skillhub_memory]]`, `[skillhub_result]`, `[[skillhub_result]]`, `job_id:`, `status:`, `source_ref:`.

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
