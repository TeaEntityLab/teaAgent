"""Coordinator CLI argument parsers."""

from __future__ import annotations

import argparse
from typing import Any


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Any],
) -> None:
    """Register coordinator subcommands."""
    classify_cmd = subparsers.add_parser(
        'classify', help='Classify a task by type and complexity'
    )
    classify_cmd.add_argument('task', help='Task description to classify')
    classify_cmd.set_defaults(func=handlers['classify'])
