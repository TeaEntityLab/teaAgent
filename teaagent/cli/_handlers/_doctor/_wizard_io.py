"""Shared EOF guard for ``teaagent doctor ... --wizard`` flows."""

from __future__ import annotations

import functools
from typing import Any, Callable

from .sanitize import print_json


def guard_wizard_eof(
    wizard: str,
) -> Callable[[Callable[[Any], int]], Callable[[Any], int]]:
    """Wrap a doctor wizard so exhausted stdin fails cleanly, not with a crash.

    The wizards prompt with ``input()``/``getpass``. On ``</dev/null`` or when
    piped answers run out, those raise ``EOFError``, which previously surfaced
    as the generic ``Unexpected error`` (the same first-run crash class removed
    for ``init``/``setup`` in G23/G38). Return a classified error instead;
    provided/piped answers still work while they last.
    """

    def decorator(fn: Callable[[Any], int]) -> Callable[[Any], int]:
        @functools.wraps(fn)
        def wrapper(args: Any) -> int:
            try:
                return fn(args)
            except EOFError:
                print_json(
                    {
                        'ok': False,
                        'error': (
                            f'{wizard} needs interactive input; run it in a '
                            'terminal or pipe answers to its prompts'
                        ),
                    }
                )
                return 1

        return wrapper

    return decorator
