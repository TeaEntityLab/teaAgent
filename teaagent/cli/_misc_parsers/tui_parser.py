from __future__ import annotations

import argparse
from typing import Callable

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def _tui(
    subparsers: argparse._SubParsersAction, handler: Callable
) -> None:  # argparse private class lacks generic type param
    p = subparsers.add_parser(
        'tui',
        help='Start an interactive terminal UI.',
        description='Start an interactive terminal UI.',
    )
    p.add_argument(
        '--database',
        default=':memory:',
        help='SQLite database path. Defaults to :memory:.',
    )
    p.add_argument(
        '--provider',
        default='gpt',
        choices=available_providers(),
        help='Default model provider for ask commands.',
    )
    p.add_argument(
        '--model', default=None, help='Default model override for ask commands.'
    )
    p.add_argument('--root', default='.', help='Workspace root for ask commands.')
    p.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Allow destructive tools for ask commands.',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for ask commands.',
    )
    p.add_argument(
        '--chat',
        action='store_true',
        default=False,
        help='Start with chat mode enabled.',
    )
    p.add_argument(
        '--setup',
        action='store_true',
        help='Run the guided first-session setup wizard before the REPL.',
    )
    p.add_argument(
        '--write-env',
        action='store_true',
        help='With --setup, also write .teaagent/env for the provider API key.',
    )
    p.set_defaults(func=handler)
