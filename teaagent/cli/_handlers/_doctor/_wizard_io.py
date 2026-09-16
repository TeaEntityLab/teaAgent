"""Shared interactive-input guard for ``teaagent doctor ... --wizard`` flows."""

from __future__ import annotations

import sys

from .sanitize import print_json


def require_wizard_tty(wizard: str) -> bool:
    """Return True when stdin is a TTY; else emit a classified error and False.

    The doctor wizards prompt with ``input()``/``getpass``. On non-interactive
    stdin those raise ``EOFError`` and surface as the generic ``Unexpected
    error`` (the same first-run crash class removed for ``init``/``setup`` in
    G23/G38). Fail fast with an actionable message instead.
    """
    if sys.stdin.isatty():
        return True
    print_json(
        {
            'ok': False,
            'error': (
                f'{wizard} needs an interactive terminal; run it in a TTY, or '
                'use the non-wizard commands/flags to configure without prompts'
            ),
        }
    )
    return False
