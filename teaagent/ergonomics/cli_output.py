"""TTY-aware CLI output defaults (friction F3 / owner-evidence UX)."""

from __future__ import annotations

import argparse
import sys


def wants_human_cli(args: argparse.Namespace, *, force_json: bool = False) -> bool:
    """Human-readable output when --human or interactive stdout (not --json-stream)."""
    if getattr(args, 'human', False):
        return True
    if (
        force_json
        or getattr(args, 'json', False)
        or getattr(args, 'json_stream', False)
    ):
        return False
    return sys.stdout.isatty()
