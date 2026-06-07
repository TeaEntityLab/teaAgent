#!/usr/bin/env python3
"""Audit direct os.environ reads outside the config layer (ARC-008)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWLIST = {
    'teaagent/config_loader.py',
    'teaagent/security_env.py',
    'teaagent/llm/_types.py',
    'teaagent/cli/_formatting.py',
    'teaagent/ergonomics/workspace_defaults.py',
}

PATTERN = re.compile(r'\bos\.environ\.get\s*\(')


def audit(root: Path) -> list[tuple[str, int, str]]:
    violations: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob('*.py')):
        rel = path.relative_to(root.parent).as_posix()
        if not rel.startswith('teaagent/'):
            continue
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding='utf-8')
        for idx, line in enumerate(text.splitlines(), start=1):
            if PATTERN.search(line):
                violations.append((rel, idx, line.strip()))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit config access patterns.')
    parser.add_argument(
        '--max',
        type=int,
        default=50,
        help='Maximum allowed violations (ratchet baseline).',
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    violations = audit(repo / 'teaagent')
    if violations:
        print(f'Found {len(violations)} direct os.environ.get() calls:')
        for rel, line_no, snippet in violations[:20]:
            print(f'  {rel}:{line_no}: {snippet}')
        if len(violations) > 20:
            print(f'  ... and {len(violations) - 20} more')
    if len(violations) > args.max:
        print(
            f'FAIL: {len(violations)} violations exceed baseline {args.max}',
            file=sys.stderr,
        )
        return 1
    print(f'OK: {len(violations)} direct env reads (baseline <= {args.max})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
