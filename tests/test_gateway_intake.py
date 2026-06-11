"""Tests for GatewayIntakeParser."""

from __future__ import annotations

import pytest

from teaagent.gateway import GatewayMessage
from teaagent.gateway_intake import GatewayIntakeParser
from teaagent.plugin_system import PluginRegistry


@pytest.fixture
def parser():
    """Set up test fixtures."""
    registry = PluginRegistry()
    return GatewayIntakeParser(registry)


def test_parse_message_run_prefix(parser) -> None:
    msg = GatewayMessage(
        platform='test',
        channel_id='ch1',
        user_id='u1',
        text='@teaagent run: fix the bug',
    )
    plan = parser.parse_message(msg)
    assert plan is not None
    assert plan.task_description == 'fix the bug'


def test_parse_message_slash_run(parser) -> None:
    msg = GatewayMessage(
        platform='test',
        channel_id='ch1',
        user_id='u1',
        text='/run implement database logging',
    )
    plan = parser.parse_message(msg)
    assert plan is not None
    assert plan.task_description == 'implement database logging'


def test_parse_message_action_word(parser) -> None:
    msg = GatewayMessage(
        platform='test',
        channel_id='ch1',
        user_id='u1',
        text='refactor the authorization logic',
    )
    plan = parser.parse_message(msg)
    assert plan is not None
    assert plan.task_description == 'refactor the authorization logic'


def test_parse_message_invalid(parser) -> None:
    msg = GatewayMessage(
        platform='test',
        channel_id='ch1',
        user_id='u1',
        text='hello my friend',
    )
    plan = parser.parse_message(msg)
    assert plan is None


def test_parse_webhook_payload_slack(parser) -> None:
    payload = {
        'event': {
            'text': '@teaagent run review all code changes',
            'channel': 'C123',
            'user': 'U456',
        }
    }
    plan = parser.parse_webhook_payload(payload)
    assert plan is not None
    assert plan.task_description == 'review all code changes'


def test_parse_webhook_payload_custom(parser) -> None:
    payload = {
        'task': 'run write documentation',
        'platform': 'custom-webhook',
        'channel_id': 'custom-channel',
        'user_id': 'custom-user',
    }
    plan = parser.parse_webhook_payload(payload)
    assert plan is not None
    assert plan.task_description == 'write documentation'
