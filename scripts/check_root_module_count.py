#!/usr/bin/env python3
"""WDF-001: fail when root teaagent module count exceeds frozen baseline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_BASELINE = 184
_REPO = Path(__file__).resolve().parents[1]
_TEAAGENT = _REPO / 'teaagent'


def count_root_modules() -> int:
    return len([p for p in _TEAAGENT.glob('*.py') if p.name != '__init__.py'])


def main() -> int:
    count = count_root_modules()
    if count > ROOT_BASELINE:
        print(
            f'ERROR: root module count {count} exceeds frozen baseline {ROOT_BASELINE}',
            file=sys.stderr,
        )
        return 1
    print(f'Root module count OK: {count} <= {ROOT_BASELINE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
