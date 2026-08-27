#!/usr/bin/env python3
"""Track cyclomatic complexity baseline and fail on regressions (CQ-002)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BASELINE = 99


def count_violations(repo: Path) -> int:
    try:
        result = subprocess.run(
            ['uv', 'run', 'ruff', 'check', '--no-cache', 'teaagent/', '--select=C901'],
            cwd=repo,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        result = subprocess.run(
            ['ruff', 'check', '--no-cache', 'teaagent/', '--select=C901'],
            cwd=repo,
            capture_output=True,
            text=True,
        )
    output = result.stdout + result.stderr
    matches = re.findall(r'Found (\d+) error', output)
    if matches:
        return int(matches[-1])
    return 0 if result.returncode == 0 else BASELINE


def main() -> int:
    parser = argparse.ArgumentParser(description='Complexity baseline gate.')
    parser.add_argument(
        '--max',
        type=int,
        default=50,
        help='Target maximum C901 violations.',
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    count = count_violations(repo)
    print(f'C901 violations: {count} (target <= {args.max})')
    if count > args.max:
        print(
            f'FAIL: {count} violations exceed target {args.max}',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
