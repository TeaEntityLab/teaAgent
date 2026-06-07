#!/usr/bin/env python3
"""Remove all unused `# type: ignore` comments reported by mypy --warn-unused-ignores.

Usage: uv run python3 scripts/cleanup_unused_ignores.py
"""

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def get_unused_ignores() -> dict[str, set[int]]:
    """Run mypy and parse unused-ignore locations into {file: {line_numbers}}."""
    result = subprocess.run(
        [sys.executable, '-m', 'mypy', 'teaagent/', '--warn-unused-ignores'],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    files: dict[str, set[int]] = defaultdict(set)
    for line in result.stdout.splitlines():
        # Format: filepath:line: error: Unused "type: ignore" comment  [unused-ignore]
        m = re.match(r'^(.+?):(\d+): error: Unused "type: ignore"', line)
        if m:
            filepath = m.group(1)
            lineno = int(m.group(2))
            files[filepath].add(lineno)
    return files


IGNORE_RE = re.compile(r'[ ]*# type: ignore(?:\[[^\]]*\])?')


def remove_ignore_from_line(line: str) -> str:
    """Remove `# type: ignore[...]` comment (and its leading space) from a line."""
    result = IGNORE_RE.sub('', line)
    # Remove trailing whitespace before newline
    if result.rstrip() != result:
        result = result.rstrip() + '\n'
    return result


def main() -> int:
    files = get_unused_ignores()
    total_lines = sum(len(lines) for lines in files.values())
    print(f'Found {total_lines} unused ignores in {len(files)} files')

    for filepath, lines in sorted(files.items()):
        abs_path = REPO_ROOT / filepath
        if not abs_path.exists():
            print(f'  SKIP (not found): {filepath}')
            continue

        with open(abs_path) as f:
            content = f.readlines()

        changed = 0
        for lineno in sorted(lines, reverse=True):
            idx = lineno - 1  # 0-based
            if idx >= len(content):
                continue
            old = content[idx]
            new = remove_ignore_from_line(old)
            if old != new:
                content[idx] = new
                changed += 1

        if changed:
            with open(abs_path, 'w') as f:
                f.writelines(content)
            print(f'  OK ({changed} lines): {filepath}')
        else:
            print(f'  NO CHANGE: {filepath}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
