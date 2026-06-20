from __future__ import annotations

import argparse
from typing import Callable

from teaagent.llm import available_providers
from teaagent.types import PermissionMode


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
        default=None,
        choices=available_providers(),
        help='Default model provider for ask commands. Resolved from config when omitted.',
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
    p.add_argument(
        '--max-iterations',
        type=int,
        default=10,
        help='Maximum agent iterations per task.',
    )
    p.add_argument(
        '--max-estimated-cost-cents',
        type=int,
        default=500,
        help='Maximum estimated cost in cents before confirmation.',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=5,
        help='Memory catalog limit (most recent N entries).',
    )
    p.set_defaults(func=handler)
