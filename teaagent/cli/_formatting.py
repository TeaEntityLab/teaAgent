"""CLI formatting helpers for TeaAgent."""

from __future__ import annotations

import sys


def stderr_supports_color() -> bool:
    """Return True when ANSI colors are safe on stderr."""
    if not hasattr(sys.stderr, 'isatty') or not sys.stderr.isatty():
        return False
    import os

    if os.environ.get('NO_COLOR'):
        return False
    term = os.environ.get('TERM', '')
    return term not in {'dumb', ''}


class CliColors:
    """Minimal ANSI color codes for CLI error output."""

    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    DIM = '\033[2m'


def colorize(text: str, color: str, *, enabled: bool | None = None) -> str:
    use_color = stderr_supports_color() if enabled is None else enabled
    if not use_color:
        return text
    return f'{color}{text}{CliColors.RESET}'


def format_error_block(
    title: str,
    message: str,
    *,
    hint: str | None = None,
    category: str | None = None,
) -> str:
    """Format a user-facing CLI error with optional color and hint."""
    use_color = stderr_supports_color()
    lines: list[str] = []
    label = title
    if category:
        label = f'{title} [{category}]'
    lines.append(colorize(label, CliColors.RED + CliColors.BOLD, enabled=use_color))
    lines.append(message)
    if hint:
        arrow = colorize('→', CliColors.CYAN, enabled=use_color)
        lines.append(f'  {arrow} {hint}')
    return '\n'.join(lines)
