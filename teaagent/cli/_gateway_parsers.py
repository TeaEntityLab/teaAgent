"""CLI argument parsers for ``teaagent gateway`` subcommands."""

from __future__ import annotations

from typing import Any


def register(
    subparsers: Any,
    handlers: dict[str, Any],
) -> None:
    parser = subparsers.add_parser(
        'gateway',
        help='Messaging gateway — connect to Telegram, Slack, and more.',
    )
    gw_sub = parser.add_subparsers(dest='gateway_command', required=True)

    p_start = gw_sub.add_parser('start', help='Start the messaging gateway.')
    p_start.add_argument(
        '--platform',
        action='append',
        default=[],
        help='Platform to enable (telegram, slack, discord). Repeatable.',
    )
    p_start.add_argument(
        '--telegram-token',
        default='',
        help='Telegram bot token (or TELEGRAM_BOT_TOKEN env).',
    )
    p_start.add_argument(
        '--slack-bot-token',
        default='',
        help='Slack bot token (or SLACK_BOT_TOKEN env).',
    )
    p_start.add_argument(
        '--slack-app-token',
        default='',
        help='Slack app token (or SLACK_APP_TOKEN env).',
    )
    p_start.add_argument(
        '--discord-token',
        default='',
        help='Discord bot token (or DISCORD_BOT_TOKEN env).',
    )
    p_start.set_defaults(func=handlers['start'])

    p_list = gw_sub.add_parser('list', help='List available gateway platforms.')
    p_list.add_argument(
        '--quiet', action='store_true', help='Only list platform names.'
    )
    p_list.set_defaults(func=handlers['list'])
