#!/usr/bin/env python3
"""WDB-002: claim-commit gate for horizon/milestone commit messages."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_CLAIM_RE = re.compile(
    r'\b(?:H\d|M\d|Complete|Implement\s+Horizon)\b',
    re.IGNORECASE,
)
_ROADMAP_UNCHANGED = re.compile(
    r'^Roadmap-Status:\s*unchanged\s*$', re.IGNORECASE | re.MULTILINE
)


def validate_claim_commit_message(
    message: str, *, repo_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    if not _CLAIM_RE.search(message):
        return errors
    if _ROADMAP_UNCHANGED.search(message):
        return errors
    root = repo_root or Path.cwd()
    roadmap = root / 'docs' / 'roadmap-status.md'
    if not roadmap.is_file():
        errors.append('Claim-style commit requires docs/roadmap-status.md to exist.')
        return errors
    errors.append(
        'Commit message matches horizon/milestone claim pattern but lacks '
        'Roadmap-Status: unchanged trailer and docs/roadmap-status.md was not '
        'verified in this hook. Update roadmap or add Roadmap-Status: unchanged.'
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    if len(argv or sys.argv) < 2:
        print('Usage: validate_claim_commit.py <commit-msg-file>', file=sys.stderr)
        return 1
    args = argv if argv is not None else sys.argv
    msg = Path(args[1]).read_text(encoding='utf-8')
    errors = validate_claim_commit_message(msg)
    for error in errors:
        print(f'ERROR: {error}', file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
