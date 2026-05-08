from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    memory = subparsers.add_parser('memory', help='Manage local workspace memory.')
    subs = memory.add_subparsers(dest='memory_command', required=True)

    add = subs.add_parser('add', help='Add one memory entry.')
    add.add_argument('content', help='Memory content to store.')
    add.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    add.add_argument(
        '--tag', action='append', default=[], help='Tag to attach. Can be repeated.'
    )
    add.set_defaults(func=handlers['add'])

    lst = subs.add_parser('list', help='List recent memory entries.')
    lst.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    lst.add_argument('--limit', type=int, default=20, help='Maximum memories to list.')
    lst.set_defaults(func=handlers['list'])

    search = subs.add_parser('search', help='Search memory entries.')
    search.add_argument('query', help='Search query.')
    search.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    search.add_argument(
        '--limit', type=int, default=10, help='Maximum memories to return.'
    )
    search.set_defaults(func=handlers['search'])

    show = subs.add_parser('show', help='Show one memory entry.')
    show.add_argument('memory_id', help='Memory id to show.')
    show.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    show.set_defaults(func=handlers['show'])
