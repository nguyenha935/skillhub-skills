# Telegram Manager Usage

Skill sẽ tự lấy Telegram bot token từ GoClaw channel runtime.
Không cần add API key riêng trong SkillHub cho luồng này.

## 1) Send message vào topic

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  --action send_message_to_topic \
  --chat-id -1001234567890 \
  --topic-id 42 \
  --payload '{"text":"Nội dung thông báo"}'
```

## 2) Create topic mới

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  --action create_topic \
  --chat-id -1001234567890 \
  --payload '{"name":"Sprint 17"}'
```

## 3) Action rủi ro (2-step confirm)

Bước 1 (request):

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  --action ban_member \
  --chat-id -1001234567890 \
  --payload '{"userId":123456789}'
```

Nếu response có `requiresConfirm=true`, chạy bước 2 với token:

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  --action ban_member \
  --chat-id -1001234567890 \
  --payload '{"userId":123456789}' \
  --confirm-token '<confirmToken-từ-bước-1>'
```

## 4) Input full JSON envelope

```bash
sh /app/data/skills-store/telegram-manager/1/scripts/run-telegram-manager.sh \
  '{"action":"set_chat_title","chatId":"-1001234567890","payload":{"title":"Team Chat"}}'
```
