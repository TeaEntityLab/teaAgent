#!/usr/bin/env python3
"""Detect stale plans in docs/plans/ that lack dates or supersession notes.

Flags plans that:
- Have no Last updated / Last reviewed date marker.
- Are older than STALE_DAYS (default 90) without a supersession note.
- Are undated (no date marker at all).

Exit 0 if clean, 1 if stale plans detected.
"""

from __future__ import annotations

import argparse
import re
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLANS_DIR = _REPO_ROOT / 'docs' / 'plans'

# Patterns for date markers
_DATE_LAST_UPDATED = re.compile(
    r'Last (?:updated|reviewed):\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE
)
_DATE_AS_OF = re.compile(r'#\s+(?:As of|)\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
_DATE_TITLE = re.compile(r'^#\s+.*?(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
_DATE_FRONTMATTER = re.compile(
    r'last_(?:audit|reviewed|updated):\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE
)
_DATE_INLINE = re.compile(r'^Date:\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE | re.MULTILINE)
_DATE_IN_FILENAME = re.compile(r'(\d{4}-\d{2}-\d{2})\.md$')
_SUPERSESSION_NOTE = re.compile(
    r'Supersession note[,:]?\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE
)
_SUPERSEDED_KEYWORD = re.compile(r'\b[sS]upersed(?:ed|es)\b')
_HISTORICAL_KEYWORD = re.compile(r'\bhistorical(?: evidence|)\b', re.IGNORECASE)

STALE_DAYS = 90


def _extract_date(text: str) -> datetime | None:
    """Extract the most recent date from text using known patterns."""
    dates: list[datetime] = []

    for pattern in (
        _DATE_LAST_UPDATED,
        _DATE_AS_OF,
        _DATE_TITLE,
        _DATE_FRONTMATTER,
        _DATE_INLINE,
        _SUPERSESSION_NOTE,
    ):
        for match in pattern.finditer(text):
            try:
                dt = datetime.strptime(match.group(1), '%Y-%m-%d').replace(
                    tzinfo=timezone.utc
                )
                dates.append(dt)
            except ValueError:
                continue

    return max(dates) if dates else None


def _has_supersession_note(text: str) -> bool:
    return bool(_SUPERSESSION_NOTE.search(text) or _SUPERSEDED_KEYWORD.search(text))


def _is_dated_evidence(text: str) -> bool:
    return bool(_HISTORICAL_KEYWORD.search(text))


def scan_plans(
    plans_dir: Path = _PLANS_DIR,
    stale_days: int = STALE_DAYS,
    check_review_dates: bool = False,
) -> list[str]:
    """Scan plan files and return list of issues found."""
    issues: list[str] = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_days)

    md_files = sorted(plans_dir.rglob('*.md'))

    for path in md_files:
        rel = path.relative_to(_REPO_ROOT)
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            issues.append(f'{rel}: cannot read file')
            continue

        # Skip ticket-plans directory (task execution ledgers, not strategic plans)
        if 'ticket-plans' in str(path):
            continue

        date = _extract_date(text)
        # Fall back to filename date if no date found in text
        if date is None:
            fn_match = _DATE_IN_FILENAME.search(path.name)
            if fn_match:
                with suppress(ValueError):
                    date = datetime.strptime(fn_match.group(1), '%Y-%m-%d').replace(
                        tzinfo=timezone.utc
                    )
        has_supersession = _has_supersession_note(text)
        is_historical = _is_dated_evidence(text)

        if date is None and not has_supersession and not is_historical:
            # Undated file
            issues.append(
                f'{rel}: no date marker found (Last updated/reviewed, '
                f'supersession note, or historical label). Add a date or '
                f'mark as superseded.'
            )
        elif date is not None and date < cutoff:
            # Stale file
            if has_supersession:
                # Stale but superseded — informational only in --verbose mode
                pass
            elif is_historical:
                # Stale but explicitly marked historical — ok
                pass
            else:
                issues.append(
                    f'{rel}: last updated {date.strftime("%Y-%m-%d")} '
                    f'({(now - date).days} days ago, threshold {stale_days}d). '
                    f'Add a supersession note or update the document.'
                )

        if check_review_dates and date and date < (now - timedelta(days=180)):
            issues.append(
                f'{rel}: review date {date.strftime("%Y-%m-%d")} is '
                f'older than 180 days. Refresh or add supersession note.'
            )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect stale plans in docs/plans/')
    parser.add_argument(
        '--plans-dir',
        default=str(_PLANS_DIR),
        help='Directory to scan for plan files',
    )
    parser.add_argument(
        '--stale-days',
        type=int,
        default=STALE_DAYS,
        help=f'Days after which a plan is considered stale (default: {STALE_DAYS})',
    )
    parser.add_argument(
        '--check-review-dates',
        action='store_true',
        help='Also flag files with review dates older than 180 days',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show informational messages for superseded-but-stale files',
    )

    args = parser.parse_args()

    issues = scan_plans(
        plans_dir=Path(args.plans_dir),
        stale_days=args.stale_days,
        check_review_dates=args.check_review_dates,
    )

    if not issues:
        print('No stale plans detected.')
        return 0

    for issue in issues:
        print(f'STALE: {issue}')

    print(f'\n{len(issues)} stale plan(s) detected.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
