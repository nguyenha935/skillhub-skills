# Usage - video-summarize

## Quick Start

Use `sh`. Do not use `bash` and do not execute the script directly.

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Input Types

### YouTube URL

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=VIDEO_ID"
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://youtu.be/VIDEO_ID"
```

Transcript is extracted first; Gemini is only called if no captions are available.

### Direct Video URL

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://cdn.example.com/video.mp4"
```

SkillHub downloads the file and uploads it to Gemini Files API.

### Local File Path

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "/workspace/video.mkv"
```

SkillHub streams local file bytes through the upload endpoint.

## Callback Session

For long-running jobs, call GoClaw `session_status` first and pass the returned
`Session:` value:

```bash
SKILLHUB_SESSION_KEY="agent:..." sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://cdn.example.com/video.mp4"
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SKILLHUB_URL` | `http://skillhub:4080` | SkillHub internal URL |
| `SKILLHUB_RUNTIME_SHARED_SECRET` | - | Preferred shared secret for SkillHub runtime HMAC auth |
| `GOCLAW_GATEWAY_TOKEN` | - | Backward-compatible fallback when no dedicated SkillHub runtime secret exists |

## GoClaw Runtime Notes

- Use `sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh ...`.
- Do not use `bash`; the GoClaw container may not install it.
- Do not execute `./scripts/run-video-summarize.sh`; installed skill files may not preserve executable bits.
- Do not use `read_file` on `/app/data/skills-store/...`; use the command above directly.

## Output

Prints the video summary to stdout. Returns exit code 0 on success, 1 on failure.

## Error Codes

- `youtube_transcript_unavailable` - No captions and youtubeMode=web.
- `gemini_generate_failed` - Gemini API error.
- `provider_exhausted` - All credentials failed or cooling down.
- `timeout` - Job did not complete within the polling timeout.
