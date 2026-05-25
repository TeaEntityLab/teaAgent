"""Messaging Gateway Platform — connect TeaAgent to Telegram, Slack, and more.

Each platform adapter implements ``GatewayAdapter`` and registers with the
``GatewayServer``, which dispatches incoming messages to the agent loop.
"""

from teaagent.gateway._base import GatewayAdapter, GatewayMessage, GatewayServer
from teaagent.gateway._discord import DiscordAdapter
from teaagent.gateway._slack import SlackAdapter
from teaagent.gateway._telegram import TelegramAdapter

__all__ = [
    'GatewayAdapter',
    'GatewayMessage',
    'GatewayServer',
    'TelegramAdapter',
    'SlackAdapter',
    'DiscordAdapter',
]
