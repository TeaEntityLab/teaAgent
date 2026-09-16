"""Shared interactive-input guard for ``teaagent doctor ... --wizard`` flows."""

from __future__ import annotations

import functools
import sys
from typing import Any, Callable

from .sanitize import print_json


def _classified_no_tty(wizard: str) -> None:
    print_json(
        {
            'ok': False,
            'error': (
                f'{wizard} needs interactive input; run it in a terminal, or '
                'use the non-wizard commands/flags to configure without prompts'
            ),
        }
    )


def guard_wizard_eof(
    wizard: str,
) -> Callable[[Callable[[Any], int]], Callable[[Any], int]]:
    """Guard a doctor wizard against non-interactive stdin.

    The wizards prompt with ``input()``/``getpass``, which write the prompt to
    stdout. The wizard's own result is JSON on stdout, so on a non-TTY stdin we
    must not even *start* prompting — otherwise the echoed prompt corrupts the
    JSON (and the read would ``EOFError`` into the generic ``Unexpected error``,
    the first-run crash class removed for ``init``/``setup`` in G23/G38).

    So fail fast with a classified error *before* the wizard body when stdin is
    not a TTY (clean JSON, no prompt echoed), and keep an ``EOFError`` catch as a
    belt-and-suspenders for an interactive session that still hits end-of-input
    (e.g. Ctrl-D).
    """

    def decorator(fn: Callable[[Any], int]) -> Callable[[Any], int]:
        @functools.wraps(fn)
        def wrapper(args: Any) -> int:
            if not sys.stdin.isatty():
                _classified_no_tty(wizard)
                return 1
            try:
                return fn(args)
            except EOFError:
                _classified_no_tty(wizard)
                return 1

        return wrapper

    return decorator
