#!/usr/bin/env python3
"""Ratchet the number of ``typing.Any`` annotations in ``teaagent/``.

``Any`` erases type information, so each new occurrence is typing debt. This
script counts the word ``Any`` (regex ``\\bAny\\b``) across ``teaagent/**/*.py``,
ignoring comment text and ``typing`` import lines, and fails when the total
exceeds ``ANY_BASELINE``. The baseline may only go down: when the count drops
below it, the script prints a HINT so the maintainer can tighten the constant.
It is a count-based ratchet, not a type checker; mypy still owns correctness.

Usage:
    python3 scripts/check_any_count.py [--baseline N] [--fail-on-increase]
                                       [--report] [--update-baseline]

Exit codes:
    0 — total Any count is at or below the baseline
    1 — total Any count exceeds the baseline
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path

# Measured 2026-10-09 at HEAD 0d9b4ae6 with `python3 scripts/check_any_count.py --report`.
ANY_BASELINE: int = 2177

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_TOP_N = 15

_ANY_TOKEN = re.compile(r'\bAny\b')
_TYPING_IMPORT = re.compile(r'^(from\s+typing\s+import\b|import\s+typing\b)')


def count_any_in_source(source: str) -> int:
    """Count ``Any`` tokens in one module's source, skipping comments and typing imports."""
    total = 0
    in_multiline_import = False
    for raw_line in source.splitlines():
        code = raw_line.split('#', 1)[0]
        stripped = code.strip()
        if in_multiline_import:
            # Continuation lines of `from typing import (...)` are part of the import.
            if ')' in stripped:
                in_multiline_import = False
            continue
        if _TYPING_IMPORT.match(stripped):
            in_multiline_import = '(' in stripped and ')' not in stripped
            continue
        total += len(_ANY_TOKEN.findall(code))
    return total


def scan(root: Path) -> dict[str, int]:
    """Return ``{repo-relative posix path: Any count}`` for ``root/teaagent/**/*.py``, sorted."""
    counts: dict[str, int] = {}
    for path in sorted((root / 'teaagent').rglob('*.py')):
        source = path.read_text(encoding='utf-8', errors='replace')
        counts[path.relative_to(root).as_posix()] = count_any_in_source(source)
    return counts


def format_report(counts: dict[str, int]) -> list[str]:
    """Render the top files by Any count, most first, ties broken by path."""
    ranked: list[tuple[int, str]] = sorted(
        ((count, path) for path, count in counts.items() if count > 0),
        key=lambda item: (-item[0], item[1]),
    )
    lines = [f'Any count by file (top {REPORT_TOP_N}):']
    for count, path in ranked[:REPORT_TOP_N]:
        lines.append(f'  {count:6d}  {path}')
    lines.append(f'  total: {sum(counts.values())} across {len(ranked)} file(s)')
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Ratchet the typing.Any count in teaagent/.'
    )
    parser.add_argument(
        '--baseline',
        type=int,
        default=ANY_BASELINE,
        help='maximum allowed Any count (default: ANY_BASELINE)',
    )
    parser.add_argument(
        '--fail-on-increase',
        action='store_true',
        help='exit 1 when the count exceeds the baseline (this is already the default)',
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help=f'print the top {REPORT_TOP_N} files by Any count',
    )
    parser.add_argument(
        '--update-baseline',
        action='store_true',
        help='print the one-line ANY_BASELINE edit for the maintainer (never edits this file)',
    )
    parser.add_argument(
        '--root',
        type=Path,
        default=REPO_ROOT,
        help='repository root to scan (default: this checkout)',
    )
    args = parser.parse_args(argv)

    counts = scan(args.root)
    total = sum(counts.values())
    baseline: int = args.baseline
    delta = total - baseline

    if args.report:
        for line in format_report(counts):
            print(line)

    if args.update_baseline:
        if total > baseline:
            print(
                f'ERROR: Any count {total} exceeds baseline {baseline} (+{delta}); '
                'the ratchet never raises the baseline. Remove Any usages instead.'
            )
            return 1
        if total == baseline:
            print(f'NO CHANGE: ANY_BASELINE already {baseline}')
            return 0
        print(f'EDIT: in scripts/check_any_count.py set ANY_BASELINE = {total}')
        return 0

    if total > baseline:
        print(f'ERROR: Any count {total} exceeds baseline {baseline} (+{delta})')
        return 1

    print(f'OK: Any count {total} <= baseline {baseline}')
    if total < baseline:
        print(f'HINT: lower ANY_BASELINE to {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
