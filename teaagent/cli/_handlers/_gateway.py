"""CLI handlers for ``teaagent gateway`` commands."""

from __future__ import annotations

import os
import signal
import sys
from argparse import Namespace
from typing import Any


def gateway_start_command(args: Namespace) -> int:
    from teaagent.gateway import (
        DiscordAdapter,
        GatewayServer,
        SlackAdapter,
        TelegramAdapter,
    )

    server = GatewayServer()
    platforms = args.platform or []
    if not platforms:
        platforms = ['telegram']

    for platform in platforms:
        if platform == 'telegram':
            token = os.environ.get('TELEGRAM_BOT_TOKEN', args.telegram_token or '')
            if not token:
                print('error: TELEGRAM_BOT_TOKEN not set', file=sys.stderr)
                return 1
            adapter: Any = TelegramAdapter(token, server=server)
            server.register_adapter(adapter)
            print('Registered Telegram adapter')
        elif platform == 'slack':
            bot_token = os.environ.get('SLACK_BOT_TOKEN', args.slack_bot_token or '')
            app_token = os.environ.get('SLACK_APP_TOKEN', args.slack_app_token or '')
            if not bot_token or not app_token:
                print('error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN required', file=sys.stderr)
                return 1
            adapter = SlackAdapter(bot_token, app_token, server=server)
            server.register_adapter(adapter)
            print('Registered Slack adapter')
        elif platform == 'discord':
            token = os.environ.get('DISCORD_BOT_TOKEN', args.discord_token or '')
            if not token:
                print('error: DISCORD_BOT_TOKEN not set', file=sys.stderr)
                return 1
            adapter = DiscordAdapter(token, server=server)
            server.register_adapter(adapter)
            print('Registered Discord adapter')
        else:
            print(f'error: unknown platform: {platform}', file=sys.stderr)
            return 1

    def _shutdown(*_: Any) -> None:
        server.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    print(f'Gateway running. Platforms: {", ".join(server.list_platforms())}')
    server.start_all()
    signal.pause()
    return 0


def gateway_list_command(args: Namespace) -> int:
    from teaagent.gateway import GatewayServer

    server = GatewayServer()
    platforms = server.list_platforms() if args.quiet else ['telegram', 'slack', 'discord']
    for p in platforms if platforms else ['telegram', 'slack', 'discord']:
        print(p)
    return 0
