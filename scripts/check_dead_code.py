#!/usr/bin/env python3
"""Run vulture dead-code scan when available."""

from __future__ import annotations

import shutil
import subprocess


def main() -> int:
    if not shutil.which('vulture'):
        print('vulture not installed — skip (pip install vulture)')
        return 0
    cmd = [
        'vulture',
        'teaagent/',
        '--min-confidence',
        '80',
        '--exclude',
        'teaagent/tui/',
    ]
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
