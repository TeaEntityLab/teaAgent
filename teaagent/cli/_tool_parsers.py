"""Tool governance CLI parsers."""

from __future__ import annotations

import argparse
from typing import Callable, Optional


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    _tool(
        subparsers,
        handlers.get('list'),
        handlers.get('inspect'),
        handlers.get('lint'),
    )


def _tool(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    list_handler: Optional[Callable] = None,
    inspect_handler: Optional[Callable] = None,
    lint_handler: Optional[Callable] = None,
) -> None:
    tool = subparsers.add_parser('tool', help='Inspect and lint ToolRegistry contracts.')
    subs = tool.add_subparsers(dest='tool_command', required=True)

    if list_handler is not None:
        lst = subs.add_parser('list', help='List registered workspace tools.')
        lst.add_argument('--root', default='.', help='Workspace root.')
        lst.add_argument(
            '--all',
            action='store_true',
            help='Include full workspace tool registry (default).',
        )
        lst.set_defaults(func=list_handler)

    if inspect_handler is not None:
        inspect = subs.add_parser('inspect', help='Show one tool contract.')
        inspect.add_argument('name', help='Tool name.')
        inspect.add_argument('--root', default='.', help='Workspace root.')
        inspect.set_defaults(func=inspect_handler)

    if lint_handler is not None:
        lint = subs.add_parser('lint', help='Lint tool schemas and annotations.')
        lint.add_argument('--root', default='.', help='Workspace root.')
        lint.add_argument(
            '--strict',
            action='store_true',
            help='Exit non-zero on warnings as well as errors.',
        )
        lint.set_defaults(func=lint_handler)
