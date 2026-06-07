from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Callable],
) -> None:
    goal = subparsers.add_parser('goal', help='Manage goals.')
    subs = goal.add_subparsers(dest='goal_command', required=True)

    list_cmd = subs.add_parser('list', help='List all goals.')
    list_cmd.add_argument('--root', default='.', help='Workspace root.')
    list_cmd.set_defaults(func=handlers['list'])

    status_cmd = subs.add_parser('status', help='Show goal status.')
    status_cmd.add_argument('goal_id', help='Goal ID.')
    status_cmd.add_argument('--root', default='.', help='Workspace root.')
    status_cmd.set_defaults(func=handlers['status'])
