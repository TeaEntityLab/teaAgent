from __future__ import annotations

import argparse
from typing import Callable


def _surfaces(
    subparsers: argparse._SubParsersAction,
    explain_handler: Callable,
) -> None:
    surfaces = subparsers.add_parser(
        'surfaces',
        help='Explain supported commands and known gaps per surface.',
    )
    subs = surfaces.add_subparsers(dest='surfaces_command', required=True)
    explain = subs.add_parser(
        'explain',
        help='List CLI, TUI, IDE, and dashboard capabilities.',
    )
    explain.add_argument(
        '--human',
        action='store_true',
        help='Print a readable summary instead of JSON.',
    )
    explain.set_defaults(func=explain_handler, command='surfaces')
