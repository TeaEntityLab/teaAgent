#!/usr/bin/env python3
"""Pre-commit hook: require staged changes or commit message to reference an action ID.

Enforces review-system.md G9 — every PR/commit must reference an ID from
docs/retrospective/06-action-register.md or register a new action.

Usage:
    python3 scripts/check_action_register_link.py [--commit-msg PATH]

Exit codes:
    0 — action ID found or no relevant files changed
    1 — no action ID found and relevant files changed
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ACTION_ID_PATTERN = re.compile(
    r'\b[SGUA]-P[0-2]-[0-9]\b'  # e.g. S-P2-4, G-P0-1, A-P1-3, U-P2-5
)

# File patterns that require an action ID when changed.
RELEVANT_PATTERNS: list[str] = [
    'teaagent/',
    'docs/',
    'tests/',
    '.github/',
    '.pre-commit-config.yaml',
    'scripts/',
    'pyproject.toml',
]


def _get_staged_files() -> list[str]:
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f'Error listing staged files: {result.stderr}', file=sys.stderr)
        sys.exit(1)
    return [f for f in result.stdout.splitlines() if f]


def _is_relevant(file_path: str) -> bool:
    return any(file_path.startswith(p) for p in RELEVANT_PATTERNS)


def _has_action_id(text: str) -> bool:
    return bool(ACTION_ID_PATTERN.search(text))


def _read_commit_msg(path: str | None) -> str:
    if path:
        return Path(path).read_text()
    return ''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit-msg', help='Path to commit message file')
    args = parser.parse_args()

    commit_msg = _read_commit_msg(args.commit_msg)
    if _has_action_id(commit_msg):
        return 0

    staged = _get_staged_files()
    relevant_changed = [f for f in staged if _is_relevant(f)]
    if not relevant_changed:
        return 0

    # Check if staged diff content contains an action ID.
    result = subprocess.run(
        ['git', 'diff', '--cached'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if _has_action_id(result.stdout):
        return 0

    print(
        'ERROR: No action ID found in commit message or staged changes.',
        file=sys.stderr,
    )
    print(
        '  Add an Action ID reference matching [SGUA]-P[0-2]-N, e.g.:',
        file=sys.stderr,
    )
    print(
        '    Action: S-P2-4  (or the appropriate ID from'
        ' docs/retrospective/06-action-register.md)',
        file=sys.stderr,
    )
    print(
        '  Or if this change does not correspond to an existing action,'
        ' register a new one.',
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    sys.exit(main())
