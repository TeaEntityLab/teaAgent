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
        # Signature-required / placeholder params vulture can't see are used:
        # __exit__ exc_* are protocol-required; apply_binary_delta's
        # current_binary is a required positional in a stub method.
        '--ignore-names',
        'exc_type,exc_val,exc_tb,current_binary',
    ]
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
