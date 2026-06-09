"""Tests for GatewayIntakeParser."""

from __future__ import annotations

import unittest

from teaagent.gateway import GatewayMessage
from teaagent.gateway_intake import GatewayIntakeParser
from teaagent.plugin_system import PluginRegistry


class TestGatewayIntakeParser(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PluginRegistry()
        self.parser = GatewayIntakeParser(self.registry)

    def test_parse_message_run_prefix(self) -> None:
        msg = GatewayMessage(
            platform='test',
            channel_id='ch1',
            user_id='u1',
            text='@teaagent run: fix the bug',
        )
        plan = self.parser.parse_message(msg)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.task_description, 'fix the bug')

    def test_parse_message_slash_run(self) -> None:
        msg = GatewayMessage(
            platform='test',
            channel_id='ch1',
            user_id='u1',
            text='/run implement database logging',
        )
        plan = self.parser.parse_message(msg)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.task_description, 'implement database logging')

    def test_parse_message_action_word(self) -> None:
        msg = GatewayMessage(
            platform='test',
            channel_id='ch1',
            user_id='u1',
            text='refactor the authorization logic',
        )
        plan = self.parser.parse_message(msg)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.task_description, 'refactor the authorization logic')

    def test_parse_message_invalid(self) -> None:
        msg = GatewayMessage(
            platform='test',
            channel_id='ch1',
            user_id='u1',
            text='hello my friend',
        )
        plan = self.parser.parse_message(msg)
        self.assertIsNone(plan)

    def test_parse_webhook_payload_slack(self) -> None:
        payload = {
            'event': {
                'text': '@teaagent run review all code changes',
                'channel': 'C123',
                'user': 'U456',
            }
        }
        plan = self.parser.parse_webhook_payload(payload)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.task_description, 'review all code changes')

    def test_parse_webhook_payload_custom(self) -> None:
        payload = {
            'task': 'run write documentation',
            'platform': 'custom-webhook',
            'channel_id': 'custom-channel',
            'user_id': 'custom-user',
        }
        plan = self.parser.parse_webhook_payload(payload)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.task_description, 'write documentation')


if __name__ == '__main__':
    unittest.main()
