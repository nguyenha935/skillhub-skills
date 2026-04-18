# Result Format

## Successful Result

When a job completes successfully, the result JSON contains:

```json
{
  "jobType": "youtube_summarize",
  "sourceType": "youtube_url",
  "selectedProvider": "gemini-video",
  "executionProvider": "youtubei",
  "attemptedProviders": ["youtubei"],
  "fallbackUsed": false,
  "summary": "Video nói về...\n1. Tên video\n2. Tóm tắt ngắn gọn...",
  "transcriptSource": "youtubei",
  "modelUsed": "gemini-3.1-flash-lite-preview"
}
```

## Failed Result

```json
{
  "jobType": "youtube_summarize",
  "sourceType": "youtube_url",
  "selectedProvider": "gemini-video",
  "executionProvider": "captionTracks",
  "attemptedProviders": ["youtubei", "captionTracks", "gemini_url"],
  "fallbackUsed": true,
  "errorCode": "youtube_transcript_unavailable",
  "errorMessage": "Both youtubei and captionTracks extraction failed",
  "modelUsed": "gemini-3.1-flash-lite-preview"
}
```

## Provider Trail

`attemptedProviders` shows the full ordered ladder of what was tried:
- `youtubei` — YouTube transcript endpoint
- `captionTracks` — Caption track from player response
- `gemini_url` — Gemini generateContent with YouTube URL
- `gemini_file` — Gemini Files API (uploaded file)
