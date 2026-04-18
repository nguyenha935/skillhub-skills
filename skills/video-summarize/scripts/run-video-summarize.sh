#!/bin/sh
# run-video-summarize.sh — Entry point for video-summarize skill
# Routes input: YouTube URL → submit, HTTPS URL → submit, file path → upload

set -euo pipefail

INPUT="$1"

if printf '%s' "$INPUT" | grep -Eq '^(https?://(www\.)?(youtube\.com|youtu\.be)/)'; then
    # YouTube URL
    JOB_JSON="$(python3 "$(dirname "$0")/submit_video_job.py" "$INPUT")"
elif printf '%s' "$INPUT" | grep -Eq '^https?://'; then
    # Generic HTTPS URL (direct video)
    JOB_JSON="$(python3 "$(dirname "$0")/submit_video_job.py" "$INPUT")"
else
    # Local file path
    JOB_JSON="$(python3 "$(dirname "$0")/upload_video_job.py" "$INPUT")"
fi

# Pass job JSON to polling script
printf '%s' "$JOB_JSON" | python3 "$(dirname "$0")/poll_video_job.py"
