#!/usr/bin/env python3
"""Check that the entire repository uses one canonical GitHub URL.

Enforces U-P0-1 remediation: no placeholder or variant URLs remain.

Exit codes:
    0 — all URLs match the canonical URL
    1 — one or more non-canonical URLs found
"""

import re
import subprocess
import sys
from pathlib import Path

CANONICAL_URL = 'TeaEntityLab/teaagent'

PLACEHOLDER_PATTERNS: list[re.Pattern] = [
    re.compile(r'github\.com/yourusername/teaagent'),
    re.compile(r'github\.com/anomalyco/teaagent'),
    re.compile(r'github\.com/[^/]+/teaagent(?!\.git)'),
]

IGNORE_PATTERNS: list[str] = [
    r'check_github_url_consistency\.py$',
    r'test_validation_script_guards\.py$',
    r'\.git/',  # git internals
    r'docs/retrospective/',  # retrospective evidence documents the historical problem
]


def get_tracked_files() -> list[str]:
    result = subprocess.run(
        ['git', 'ls-files'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f'Error listing tracked files: {result.stderr}', file=sys.stderr)
        sys.exit(1)
    return [f for f in result.stdout.splitlines() if f]


def _should_ignore(file_path: str) -> bool:
    return any(re.search(p, file_path) for p in IGNORE_PATTERNS)


def check_urls(files: list[str], repo_root: Path) -> list[str]:
    violations: list[str] = []

    # rg for performance on large repos.
    result = subprocess.run(
        [
            'rg',
            '--no-heading',
            '-n',
            '-i',
            r'github\.com/[^/]+/teaagent',
            str(repo_root),
            '--type',
            'md',
            '--type',
            'py',
            '--type',
            'yaml',
            '--type',
            'json',
            '--type-add',
            'cfg:*.cfg',
            '--type-add',
            'toml:*.toml',
            '--glob',
            '!.git/',
            '--glob',
            '!.github/',
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        file_path = line.split(':', 1)[0]
        if _should_ignore(file_path):
            continue
        # Check if this is our canonical URL — if so, skip.
        if CANONICAL_URL in line:
            continue
        # Check if it matches any placeholder pattern.
        if any(p.search(line) for p in PLACEHOLDER_PATTERNS):
            violations.append(line)

    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    files = get_tracked_files()
    violations = check_urls(files, repo_root)

    if not violations:
        print(f'OK: All GitHub URLs reference canonical "{CANONICAL_URL}".')
        return 0

    print(f'ERROR: Found {len(violations)} non-canonical GitHub URL(s):')
    for v in violations:
        print(f'  {v}')
    print()
    print(f'Update them to reference "{CANONICAL_URL}".')
    return 1


if __name__ == '__main__':
    sys.exit(main())
