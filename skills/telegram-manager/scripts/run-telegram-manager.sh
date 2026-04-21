#!/bin/sh
# run-telegram-manager.sh — Entry point for telegram-manager skill

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: run-telegram-manager.sh <json-envelope>" >&2
  echo "   or: run-telegram-manager.sh --action ACTION --chat-id CHAT_ID [--topic-id TOPIC_ID] [--payload JSON] [--request-id ID] [--confirm-token TOKEN] [--provider-slug SLUG] [--skill-slug SLUG]" >&2
  exit 1
fi

python3 "$(dirname "$0")/execute_telegram_action.py" "$@"
