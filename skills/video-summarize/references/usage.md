# Usage - video-summarize

## Quick Start

Use `sh`. Do not use `bash` and do not execute the script directly.

Before first call in each run, read the skill instructions:

```bash
sed -n '1,220p' /app/data/skills-store/video-summarize/1/SKILL.md
```

```bash
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Agent / Session Callback

If an agent is calling this skill from an active chat session, pass the full callback route so SkillHub can callback the same user conversation after background completion:

```bash
SKILLHUB_SESSION_KEY="$SESSION_KEY" \
SKILLHUB_CHANNEL="$CHANNEL" \
SKILLHUB_CHAT_ID="$CHAT_ID" \
SKILLHUB_USER_ID="$USER_ID" \
SKILLHUB_SENDER_ID="$SENDER_ID" \
SKILLHUB_PEER_KIND="$PEER_KIND" \
SKILLHUB_AGENT_ID="$AGENT_ID" \
sh /app/data/skills-store/video-summarize/1/scripts/run-video-summarize.sh "https://cdn.example.com/video.mov"
```

For remote video jobs, missing any of `sessionKey + channel + chatId + userId + senderId + peerKind + agentId` is a hard failure. The skill must not create a background job unless callback context is complete.

Agent behavior guardrails:

- For a user turn that asks to summarize/analyze a video URL, call this skill first before any progress reply.
- Only say "processing" when the current run has an actual tool result from this skill.
- If tool output says `MISSING_CALLBACK_ROUTE`, retry with full callback route fields instead of replying without tool execution.
- Never call legacy path `/app/bundled-skills/summarize/scripts/run-summarize.sh`.
- Do not expose internal markers/fields in user-facing replies (`skillhub_memory`, `skillhub_result`, or fields like `job_id`, `source_ref`, `summary_short`).

Field source mapping for `MISSING_CALLBACK_ROUTE`:

- `sessionKey` <- event `sessionKey`
- `channel` <- event `channel`
- `chatId` <- event `chatId` (fallback: parse part 5 from `sessionKey`)
- `userId` <- event `userId`
- `senderId` <- event `senderId`
- `peerKind` <- parse part 4 from `sessionKey` (`direct|group`)
- `agentId` <- event `agentId` (fallback: parse part 2 from `sessionKey`)
- Route coherence rule: if any route field conflicts with parsed `sessionKey`, trust `sessionKey`.

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
