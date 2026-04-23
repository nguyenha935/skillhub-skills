# Telegram Manager Actions

Lưu ý runtime: bot token được resolve tự động từ GoClaw channel credentials theo chat context.

## Topic / Forum
- `create_topic` payload: `{ "name": "...", "iconColor": 7322096?, "iconEmojiId": "..."? }`
- `edit_topic` payload: `{ "name": "..."?, "iconEmojiId": "..."? }` + `topicId`
- `close_topic` + `topicId`
- `reopen_topic` + `topicId`
- `delete_topic` + `topicId`
- `hide_general_topic`
- `unhide_general_topic`
- `close_general_topic`
- `reopen_general_topic`
- `edit_general_topic` payload: `{ "name": "..." }`
- `list_topic_icons`
- `list_topics` (hybrid index + verify)

## Message
- `send_message_to_topic` payload: `{ "text": "...", "parseMode": "Markdown"? }`
- `send_media_to_topic` payload: `{ "mediaType": "photo|video|document", "mediaUrl": "https://...", "caption": "..."? }`
- `edit_message_text` payload: `{ "messageId": 123, "text": "..." }`
- `pin_message` payload: `{ "messageId": 123, "disableNotification": true? }`
- `unpin_message` payload: `{ "messageId": 123 }`
- `delete_message` payload: `{ "messageId": 123 }`

## Moderation / Member
- `ban_member` payload: `{ "userId": 123, "untilDate": 0?, "revokeMessages": true? }`
- `unban_member` payload: `{ "userId": 123, "onlyIfBanned": true? }`
- `restrict_member` / `mute_member` payload: `{ "userId": 123, "permissions": {...}?, "untilDate": 0? }`
- `unrestrict_member` / `unmute_member` payload: `{ "userId": 123, "permissions": {...}? }`
- `approve_join_request` payload: `{ "userId": 123 }`
- `decline_join_request` payload: `{ "userId": 123 }`

## Chat Settings / Admin
- `set_chat_title` payload: `{ "title": "..." }`
- `set_chat_description` payload: `{ "description": "..." }`
- `set_chat_photo` payload: `{ "photo": "https://... hoặc file_id" }`
- `delete_chat_photo`
- `create_invite_link` payload: `{ "name": "..."?, "expireDate": 0?, "memberLimit": 0?, "createsJoinRequest": false? }`
- `edit_invite_link` payload: `{ "inviteLink": "...", "name": "..."?, "expireDate": 0?, "memberLimit": 0?, "createsJoinRequest": false? }`
- `revoke_invite_link` payload: `{ "inviteLink": "..." }`
- `list_invite_links` (hybrid index + verify)
- `set_slow_mode` payload: `{ "seconds": 10 }`
- `set_default_permissions` payload: `{ "permissions": {...} }`
- `promote_member` payload: `{ "userId": 123, "permissions": {...} }`
- `demote_member` payload: `{ "userId": 123 }`

## Common envelope fields
- `chatId` là bắt buộc cho mọi action.
- `topicId` bắt buộc với các action thao tác theo topic.
- `requestId` khuyến nghị để idempotency.
- `confirmToken` chỉ dùng ở bước xác nhận action rủi ro.
