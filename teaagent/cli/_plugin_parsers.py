"""Plugin CLI argument parsers."""

from __future__ import annotations

import argparse
from typing import Callable, Optional


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Callable],
) -> None:
    _plugin(
        subparsers,
        handlers.get('list'),
        handlers.get('show'),
        handlers.get('verify'),
    )


def _plugin(
    subparsers: argparse._SubParsersAction,
    list_handler: Optional[Callable] = None,
    show_handler: Optional[Callable] = None,
    verify_handler: Optional[Callable] = None,
) -> None:
    plugin = subparsers.add_parser('plugin', help='Plugin system commands.')
    subs = plugin.add_subparsers(dest='plugin_command', required=True)

    if list_handler is not None:
        list_cmd = subs.add_parser('list', help='List all discovered plugins.')
        list_cmd.add_argument(
            '--root', default='.', help='Workspace root. Defaults to current directory.'
        )
        list_cmd.set_defaults(func=list_handler)

    if show_handler is not None:
        show_cmd = subs.add_parser('show', help='Show detailed plugin information.')
        show_cmd.add_argument('name', help='Plugin name.')
        show_cmd.add_argument(
            '--root', default='.', help='Workspace root. Defaults to current directory.'
        )
        show_cmd.set_defaults(func=show_handler)

    if verify_handler is not None:
        verify_cmd = subs.add_parser(
            'verify', help='Verify plugin manifest and entry point.'
        )
        verify_cmd.add_argument('name', help='Plugin name.')
        verify_cmd.add_argument(
            '--root', default='.', help='Workspace root. Defaults to current directory.'
        )
        verify_cmd.set_defaults(func=verify_handler)
