import argparse
import os
import sys
import unittest
from unittest.mock import patch

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import execute_telegram_action as action


class TelegramManagerEnvelopeTest(unittest.TestCase):
    def test_build_envelope_from_flags(self):
        args = argparse.Namespace(
            envelope=None,
            action='send_message_to_topic',
            chat_id='-100123',
            topic_id='42',
            payload='{"text":"hello"}',
            request_id='req-1',
            confirm_token=None,
            provider_slug='telegram-bot',
            skill_slug='telegram-manager',
        )
        config = {'skillSlug': 'telegram-manager', 'providerSlug': 'telegram-bot'}
        envelope = action.build_envelope(args, config)
        self.assertEqual(envelope['action'], 'send_message_to_topic')
        self.assertEqual(envelope['chatId'], '-100123')
        self.assertEqual(envelope['topicId'], '42')
        self.assertEqual(envelope['payload']['text'], 'hello')
        self.assertEqual(envelope['requestId'], 'req-1')

    def test_parse_agent_key_from_session_key(self):
        self.assertEqual(
            action.parse_agent_key_from_session_key('agent:bao-an:bao-an:group:-1003945746436:topic:1'),
            'bao-an',
        )
        self.assertEqual(action.parse_agent_key_from_session_key('invalid-session'), '')

    @patch.dict(os.environ, {'SKILLHUB_TELEGRAM_BOT_TOKEN': '8641653219:AAEfLNXfx6XJExzDzz_690JPWtkxaKDfe00'}, clear=False)
    def test_resolve_delegated_bot_token_from_env(self):
        envelope = {
            'action': 'send_message_to_topic',
            'chatId': '-100123',
            'payload': {'text': 'hello'},
        }
        token = action.resolve_delegated_bot_token(envelope)
        self.assertEqual(token, '8641653219:AAEfLNXfx6XJExzDzz_690JPWtkxaKDfe00')
        self.assertEqual(envelope['delegatedBotToken'], token)


if __name__ == '__main__':
    unittest.main()
