"""Control-loop freshness validator for roadmap-status.md.

Checks that feature rows in control-loop tracking sections of the roadmap:
  - Reference at least one control-loop work item ID (SCL-P*, CPP-P*, DSK-P*)
  - Have a valid status marker

Usage:
  python3 scripts/validate_control_loop_freshness.py
  python3 scripts/validate_control_loop_freshness.py --check-file custom.md --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# ---- Patterns ----

# Table-row ID patterns
_CL_ID_PATTERN = re.compile(r'(?:SCL|CPP|DSK)-P\d+-\d+')

# Status labels (text + emoji equivalents)
_VALID_STATUSES = frozenset(
    {
        # Text labels
        'Not Started',
        'In Progress',
        'Complete',
        'Blocked',
        'Proposed',
        'Pending',
        'On Hold',
        # Emoji equivalents
        '\U0001f534',  # 🔴 Not Started / Blocked
        '\U0001f7e1',  # 🟡 In Progress
        '\U0001f7e2',  # 🟢 Complete
        '\u23f3',  # ⏳ Pending
    }
)

# Status markers that count as "present" — substring match on the row.
# We use the text labels as primary since the roadmap uses them.
_STATUS_MARKERS = (
    'Not Started',
    'In Progress',
    'Complete',
    'Blocked',
    'Proposed',
    'Pending',
    'On Hold',
    '\U0001f534',  # 🔴
    '\U0001f7e1',  # 🟡
    '\U0001f7e2',  # 🟢
    '\u23f3',  # ⏳
)

# H2 section headings that trigger control-loop ID checking.
_CONTROL_LOOP_SECTION_KEYWORDS = (
    'ecosystem trust',
    'dynamic skill',
    'seven control loop',
    'community pain point',
    'cross-horizon',
)

# Lines that look like a table row with an ID column and at least 3 data columns.
_TABLE_ROW_RE = re.compile(r'^\|\s*([A-Z][A-Z0-9-]+)\s*\|[^|]+\|[^|]+\|[^|]+\|')

# Status column extraction: the 5th column (0-indexed from split).
# Row format: | ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
_STATUS_COLUMN_INDEX = 3  # 0=empty, 1=ID, 2=WorkItem, 3=Owner, 4=Status

# Heading detection
_HEADING_RE = re.compile(r'^##\s+(.+)')


# ---- Core logic ----


def _parse_control_loop_sections(
    lines: list[str],
) -> tuple[set[int], int]:
    """Return the set of line numbers that fall within a control-loop section.

    A control-loop section is a contiguous block starting at an H2 heading
    that contains one of the known keywords and ending at the next H2 heading
    (or EOF).
    """
    scoped: set[int] = set()
    in_section = False
    for idx, line in enumerate(lines):
        h_match = _HEADING_RE.match(line)
        if h_match:
            heading_lower = h_match.group(1).lower()
            in_section = any(
                kw in heading_lower for kw in _CONTROL_LOOP_SECTION_KEYWORDS
            )
            continue
        if in_section:
            scoped.add(idx)
    return scoped, len(lines)


def _extract_status(row_line: str) -> str | None:
    """Extract the status value from a table row."""
    parts = [p.strip() for p in row_line.split('|')]
    # parts[0] is empty, parts[1]=ID, parts[2]=WorkItem, parts[3]=Owner, parts[4]=Status
    if len(parts) > _STATUS_COLUMN_INDEX + 1:
        return parts[_STATUS_COLUMN_INDEX + 1]
    return None


def _has_status_marker(row_line: str) -> bool:
    """Check if the row contains any valid status marker."""
    return any(marker in row_line for marker in _STATUS_MARKERS)


def _has_control_loop_id(row_line: str) -> bool:
    """Check if the row contains at least one control-loop work item ID."""
    return bool(_CL_ID_PATTERN.search(row_line))


def validate_roadmap(path: Path, *, verbose: bool = False) -> list[str]:
    """Validate a roadmap file for control-loop freshness.

    Returns a list of error strings (empty = all pass).
    """
    errors: list[str] = []

    if not path.is_file():
        errors.append(f'File not found: {path}')
        return errors

    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()

    scoped_lines, total_lines = _parse_control_loop_sections(lines)

    rows_checked = 0
    rows_ok = 0
    rows_missing_id = 0
    rows_missing_status = 0

    for idx, line in enumerate(lines):
        lineno = idx + 1

        if not _TABLE_ROW_RE.match(line):
            continue

        # Exclude header row
        if line.startswith('| ID |'):
            continue

        rows_checked += 1
        has_id = _has_control_loop_id(line)
        has_status = _has_status_marker(line)
        in_scope = idx in scoped_lines

        row_ok = True

        if in_scope and not has_id:
            errors.append(
                f'{path.name}:{lineno}: missing control-loop ID '
                f'(SCL/CPP/DSK-P*) in control-loop section row: '
                f'{line[:80].strip()}'
            )
            rows_missing_id += 1
            row_ok = False

        if not has_status:
            errors.append(
                f'{path.name}:{lineno}: missing status marker '
                f'in row: {line[:80].strip()}'
            )
            rows_missing_status += 1
            row_ok = False

        if verbose:
            status_str = 'PASS' if row_ok else 'FAIL'
            scope_str = 'CL' if in_scope else '--'
            id_str = 'ID' if has_id else '--'
            st_str = 'STATUS' if has_status else 'NO_STATUS'
            print(
                f'  [{status_str}] L{lineno} [{scope_str}] [{id_str}] [{st_str}] '
                f'{_extract_status(line) or "?"}'
            )

        if row_ok:
            rows_ok += 1

    if verbose or rows_missing_id or rows_missing_status:
        print(
            f'Rows checked: {rows_checked}, '
            f'ok: {rows_ok}, '
            f'missing control-loop ID: {rows_missing_id}, '
            f'missing status: {rows_missing_status}'
        )

    return errors


# ---- CLI ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Validate control-loop freshness in roadmap-status.md.'
    )
    parser.add_argument(
        '--check-file',
        default=str(_REPO_ROOT / 'docs' / 'roadmap-status.md'),
        help='Path to the roadmap file to check.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print every row, not just failures.',
    )
    args = parser.parse_args(argv)

    errors = validate_roadmap(Path(args.check_file), verbose=args.verbose)

    if errors:
        for err in errors:
            print(f'ERROR: {err}', file=sys.stderr)
        return 1

    print('Control-loop freshness check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
