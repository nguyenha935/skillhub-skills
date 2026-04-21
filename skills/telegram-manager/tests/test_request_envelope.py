import argparse
import os
import sys
import unittest

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


if __name__ == '__main__':
    unittest.main()
