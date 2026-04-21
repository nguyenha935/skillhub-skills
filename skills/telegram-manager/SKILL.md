---
name: telegram-manager
description: Quản trị Telegram group/forum qua SkillHub (topic, message, moderation, settings).
license: All rights reserved
metadata:
  author: nguyenha935
  version: "1.0.0"
---

# telegram-manager Skill

Điều khiển Telegram bằng Telegram Bot API thông qua SkillHub runtime endpoint.

## GoClaw Runtime Command

Luôn dùng `sh`:

```bash
sed -n '1,260p' /app/data/skills-store/telegram-manager/1/SKILL.md
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh '{"action":"send_message_to_topic","chatId":"-1001234567890","topicId":"42","payload":{"text":"Xin chào"}}'
```

Có thể truyền theo cờ:

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  --action send_message_to_topic \
  --chat-id -1001234567890 \
  --topic-id 42 \
  --payload '{"text":"Xin chào"}'
```

## Runtime Rules For Agents

1. Trước lần gọi đầu tiên trong mỗi run, đọc lại `SKILL.md` (preflight command ở trên).
2. Không gọi path legacy hoặc script ngoài package này.
3. Với action rủi ro (`delete/ban/restrict/revoke/demote/...`), endpoint có thể trả `requiresConfirm=true`.
4. Khi cần confirm, gọi lại cùng payload + `--confirm-token` để execute bước 2.
5. Không tự đoán `chatId`; phải dùng đúng chat/group đã cho.
6. Không đưa token/secret vào câu trả lời user.

## Input Envelope

Envelope JSON chuẩn:

```json
{
  "action": "send_message_to_topic",
  "chatId": "-1001234567890",
  "topicId": "42",
  "payload": {
    "text": "Xin chào"
  },
  "requestId": "optional-idempotency-key",
  "confirmToken": "only-when-required",
  "providerSlug": "telegram-bot",
  "skillSlug": "telegram-manager"
}
```

## Supported Actions (v1)

- Topic/forum: `create_topic`, `edit_topic`, `close_topic`, `reopen_topic`, `delete_topic`, `hide_general_topic`, `unhide_general_topic`, `close_general_topic`, `reopen_general_topic`, `edit_general_topic`, `list_topic_icons`, `list_topics`
- Message: `send_message_to_topic`, `send_media_to_topic`, `edit_message_text`, `pin_message`, `unpin_message`, `delete_message`
- Moderation/member: `ban_member`, `unban_member`, `restrict_member`, `unrestrict_member`, `mute_member`, `unmute_member`, `approve_join_request`, `decline_join_request`
- Chat settings/admin: `set_chat_title`, `set_chat_description`, `set_chat_photo`, `delete_chat_photo`, `create_invite_link`, `edit_invite_link`, `revoke_invite_link`, `list_invite_links`, `set_slow_mode`, `set_default_permissions`, `promote_member`, `demote_member`

## Platform Constraints

- Telegram Bot API **không hỗ trợ** tạo group/channel mới.
- Bot phải được add vào group mục tiêu và có quyền admin phù hợp.
- SkillHub backend bắt buộc `allowedChatIds` để chống lạm dụng.
