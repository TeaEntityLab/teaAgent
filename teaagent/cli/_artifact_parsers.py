"""Artifact readback CLI parsers."""

from __future__ import annotations

import argparse
from typing import Callable, Optional


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Callable],
) -> None:
    _artifact(
        subparsers,
        handlers.get('read'),
        handlers.get('list'),
    )


def _artifact(
    subparsers: argparse._SubParsersAction,
    read_handler: Optional[Callable] = None,
    list_handler: Optional[Callable] = None,
) -> None:
    artifact = subparsers.add_parser(
        'artifact', help='Read and list stored tool result artifacts.'
    )
    subs = artifact.add_subparsers(dest='artifact_command', required=True)

    if list_handler is not None:
        lst = subs.add_parser('list', help='List all stored artifact files.')
        lst.add_argument('--root', default='.', help='Workspace root.')
        lst.set_defaults(func=list_handler)

    if read_handler is not None:
        read = subs.add_parser('read', help='Read a stored artifact by path.')
        read.add_argument('artifact_path', help='Relative path to the artifact file.')
        read.add_argument(
            '--cursor',
            default=None,
            help='Cursor string, e.g. "offset:1024". Default: start from beginning.',
        )
        read.add_argument(
            '--max-bytes',
            type=int,
            default=50_000,
            help='Maximum bytes to return (default: 50000).',
        )
        read.add_argument('--root', default='.', help='Workspace root.')
        read.set_defaults(func=read_handler)
