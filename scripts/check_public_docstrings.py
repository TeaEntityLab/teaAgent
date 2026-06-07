#!/usr/bin/env python3
"""Verify public API modules have module docstrings (DEV-006 / CQ-004)."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

PUBLIC_MODULES = [
    'teaagent/__init__.py',
    'teaagent/errors.py',
    'teaagent/tools.py',
    'teaagent/policy.py',
    'teaagent/audit.py',
    'teaagent/runner/__init__.py',
    'teaagent/llm/__init__.py',
    'teaagent/types/__init__.py',
    'teaagent/approval/__init__.py',
]


def check_module(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    if ast.get_docstring(tree) is None:
        return ['<module>']
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description='Check public API docstrings.')
    _ = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    failures: list[str] = []
    for rel in PUBLIC_MODULES:
        path = repo / rel
        if not path.is_file():
            continue
        missing = check_module(path)
        if missing:
            failures.append(f'{rel}: missing module docstring')
    if failures:
        print('Missing docstrings on public modules:')
        for item in failures:
            print(f'  - {item}')
        return 1
    print(f'OK: module docstrings present in {len(PUBLIC_MODULES)} public modules')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
