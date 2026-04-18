# Usage — video-summarize

## Quick Start

```bash
./scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Input Types

### YouTube URL
```bash
./scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=VIDEO_ID"
./scripts/run-video-summarize.sh "https://youtu.be/VIDEO_ID"
```
Transcript is extracted first; Gemini is only called if no captions are available.

### Direct Video URL
```bash
./scripts/run-video-summarize.sh "https://cdn.example.com/video.mp4"
```
File is downloaded and uploaded to Gemini Files API.

### Local File Path
```bash
./scripts/run-video-summarize.sh "/workspace/video.mkv"
```
File is streamed to SkillHub via Gemini Files API.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SKILLHUB_URL` | `http://skillhub:4080` | SkillHub internal URL |
| `GOCLAW_GATEWAY_TOKEN` | — | Required: GoClaw gateway token |

## Output

Prints the video summary to stdout. Returns exit code 0 on success, 1 on failure.

## Error Codes

- `youtube_transcript_unavailable` — No captions and youtubeMode=web
- `gemini_generate_failed` — Gemini API error
- `provider_exhausted` — All credentials failed or cooling down
- `timeout` — Job did not complete within 600 seconds
