from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    release = subparsers.add_parser('release', help='Release evidence commands.')
    subs = release.add_subparsers(dest='release_command', required=True)
    _evidence(subs, handlers['evidence'])


def _evidence(
    subs: argparse._SubParsersAction,  # type: ignore[type-arg]
    handler: Callable,
) -> None:
    p = subs.add_parser(
        'evidence',
        help='Generate release evidence bundle with seven-loop status',
    )
    p.add_argument(
        '--output',
        default='docs/release-evidence.json',
        help='Output path',
    )
    p.add_argument(
        '--profile',
        choices=('release', 'full', 'counts-only'),
        default='release',
    )
    p.add_argument(
        '--root',
        default='.',
        help='Workspace root',
    )
    p.set_defaults(func=handler)
