#!/bin/sh
# run-video-summarize.sh — Entry point for video-summarize skill
# Routes input: YouTube URL → submit, HTTPS URL → submit, file path → upload

set -euo pipefail

CALLBACK_MODE="${SKILLHUB_CALLBACK_MODE:-inject_then_channel_send}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --session-key)
            export SKILLHUB_SESSION_KEY="${2:-}"
            shift 2
            ;;
        --callback-mode)
            CALLBACK_MODE="${2:-inject_then_channel_send}"
            export SKILLHUB_CALLBACK_MODE="$CALLBACK_MODE"
            shift 2
            ;;
        --channel)
            export SKILLHUB_CHANNEL="${2:-}"
            shift 2
            ;;
        --chat-id)
            export SKILLHUB_CHAT_ID="${2:-}"
            shift 2
            ;;
        --user-id)
            export SKILLHUB_USER_ID="${2:-}"
            shift 2
            ;;
        --sender-id)
            export SKILLHUB_SENDER_ID="${2:-}"
            shift 2
            ;;
        --peer-kind)
            export SKILLHUB_PEER_KIND="${2:-}"
            shift 2
            ;;
        --agent-id)
            export SKILLHUB_AGENT_ID="${2:-}"
            shift 2
            ;;
        --callback-context-json)
            export SKILLHUB_CALLBACK_CONTEXT="${2:-}"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [ "$#" -lt 1 ]; then
    echo "usage: run-video-summarize.sh [--session-key KEY] [--channel NAME] [--chat-id ID] [--user-id ID] [--sender-id ID] [--peer-kind KIND] [--agent-id ID] [--callback-mode MODE] [--callback-context-json JSON] <url-or-path>" >&2
    exit 1
fi

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
