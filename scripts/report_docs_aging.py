"""Documentation aging dashboard (DOW-023).

Generates a deterministic report of current-truth doc freshness grouped by
owner surface. Secondary to docs/INDEX.md.

Archive-tier docs (with YYYY-MM-DD date pattern) are excluded from staleness
warnings as they are immutable records, not live promises.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT = _REPO_ROOT / 'docs' / 'generated' / 'docs-aging-dashboard.md'

_REVIEW_DATE = re.compile(
    r'(?:Last reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*'
    r'|\*\*Last reviewed:\*\*\s*(\d{4}-\d{2}-\d{2}))',
    re.IGNORECASE,
)
_REVIEW_TRIGGER = re.compile(
    r'>\s*\*\*Review trigger:\*\*\s*(.+?)(?:\n|$)', re.IGNORECASE
)
_OWNER_SURFACE = re.compile(r'>\s*\*\*Owns:\*\*\s*(.+?)(?:\n|$)', re.IGNORECASE)
_ARCHIVE_DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')

STALE_DAYS = 90


def _is_archive_tier(rel_path: str) -> bool:
    """Return True if doc is archive-tier (contains YYYY-MM-DD date pattern)."""
    return bool(_ARCHIVE_DATE_PATTERN.search(rel_path))


class DocReviewEntry(NamedTuple):
    rel_path: str
    owner: str
    review_trigger: str


DOC_REVIEW_REGISTRY: tuple[DocReviewEntry, ...] = (
    DocReviewEntry(
        'README.md',
        'project',
        'README feature claims, golden path, or provider count changes',
    ),
    DocReviewEntry(
        'docs/INDEX.md',
        'docs',
        'New front-door docs, supersession links, or validation command changes',
    ),
    DocReviewEntry(
        'docs/USAGE.md',
        'daily-driver',
        'CLI/TUI command behavior, permission modes, or surface recipes change',
    ),
    DocReviewEntry(
        'docs/cli.md',
        'cli',
        'CLI flags, subcommands, or handler behavior changes',
    ),
    DocReviewEntry(
        'docs/acceptance.md',
        'verification',
        'Acceptance test inventory or count changes',
    ),
    DocReviewEntry(
        'docs/roadmap-status.md',
        'roadmap',
        'Roadmap horizon, milestone, or track status changes',
    ),
    DocReviewEntry(
        'docs/daily-driver-current-status.md',
        'daily-driver',
        'TUI, chat, agent mode, approval, cost, undo, or resume behavior changes',
    ),
    DocReviewEntry(
        'docs/release-checklist.md',
        'release',
        'Release gates, survey cadence, or validation workflow changes',
    ),
    DocReviewEntry(
        'docs/backlog-priority.md',
        'strategy',
        'Backlog priorities or shipped/beta status claims change',
    ),
    DocReviewEntry(
        'docs/maturity-matrix.md',
        'governance',
        'Subsystem maturity labels change',
    ),
    DocReviewEntry(
        'docs/terminology.md',
        'governance',
        'Canonical terminology or state vocabulary changes',
    ),
    DocReviewEntry(
        'docs/architecture.md',
        'architecture',
        'Architecture claims, provider count, or module boundaries change',
    ),
    DocReviewEntry(
        'docs/tui-daily-driver-guide.md',
        'daily-driver',
        'TUI operator loop or recovery pointers change',
    ),
    DocReviewEntry(
        'docs/permission-and-approval-playbook.md',
        'security',
        'Approval, permission, or MCP trust behavior changes',
    ),
    DocReviewEntry(
        'docs/governance/README.md',
        'governance',
        'Governance index or process entry points change',
    ),
    DocReviewEntry(
        'docs/plans/ticket-plans/index.md',
        'daily-driver',
        'Ticket closure status or execution order changes',
    ),
    DocReviewEntry(
        'docs/analysis/active-findings-status-ledger-2026-06-06.md',
        'daily-driver',
        'Finding closure status or new CG/AG/DS ids',
    ),
)


@dataclass
class DocAgingRow:
    rel_path: str
    owner: str
    review_trigger: str
    last_reviewed: str | None
    file_mtime: str
    status: str
    notes: list[str]
    tier: str = 'working'  # constitution, working, or archive


def _parse_review_date(text: str) -> datetime | None:
    match = _REVIEW_DATE.search(text)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _scan_doc(
    entry: DocReviewEntry, *, repo_root: Path, stale_days: int
) -> DocAgingRow:
    path = repo_root / entry.rel_path
    notes: list[str] = []
    tier = 'archive' if _is_archive_tier(entry.rel_path) else 'working'

    if not path.is_file():
        return DocAgingRow(
            rel_path=entry.rel_path,
            owner=entry.owner,
            review_trigger=entry.review_trigger,
            last_reviewed=None,
            file_mtime='missing',
            status='missing',
            notes=['File not found'],
            tier=tier,
        )

    text = path.read_text(encoding='utf-8')
    reviewed = _parse_review_date(text)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    file_mtime = mtime.strftime('%Y-%m-%d')

    if not _REVIEW_TRIGGER.search(text):
        notes.append('Missing review trigger banner')
    doc_owner = _OWNER_SURFACE.search(text)
    if doc_owner is None:
        notes.append('Missing owner banner')

    now = datetime.now(tz=timezone.utc)
    if reviewed is None:
        status = 'missing_review_date'
        notes.append('Add Last reviewed: **YYYY-MM-DD**')
    elif reviewed + timedelta(days=stale_days) < now:
        status = 'stale_by_age'
        notes.append(f'Last reviewed older than {stale_days} days')
    elif mtime.date() > reviewed.date():
        status = 'stale_by_mtime'
        notes.append('File modified after last reviewed date')
    else:
        status = 'fresh'

    last_reviewed = reviewed.strftime('%Y-%m-%d') if reviewed else None
    trigger = entry.review_trigger
    if trigger_banner := _REVIEW_TRIGGER.search(text):
        trigger = trigger_banner.group(1).strip()

    return DocAgingRow(
        rel_path=entry.rel_path,
        owner=entry.owner,
        review_trigger=trigger,
        last_reviewed=last_reviewed,
        file_mtime=file_mtime,
        status=status,
        notes=notes,
        tier=tier,
    )


def generate_docs_aging_dashboard(
    *,
    repo_root: Path = _REPO_ROOT,
    stale_days: int = STALE_DAYS,
) -> str:
    rows = [
        _scan_doc(entry, repo_root=repo_root, stale_days=stale_days)
        for entry in DOC_REVIEW_REGISTRY
    ]
    # Exclude archive-tier docs from staleness warnings (they are immutable records)
    stale_rows = [
        row for row in rows if row.status != 'fresh' and row.tier != 'archive'
    ]
    archive_rows = [row for row in rows if row.tier == 'archive']
    grouped: dict[str, list[DocAgingRow]] = {}
    for row in stale_rows:
        grouped.setdefault(row.owner, []).append(row)

    lines = [
        '# Documentation Aging Dashboard (Generated)',
        '',
        '> **Not current truth.** Use [docs/INDEX.md](../INDEX.md) for the curated front door.',
        '',
        f'**Stale threshold:** {stale_days} days since `Last reviewed`',
        f'**Current-truth docs scanned:** {len(rows)}',
        f'**Needs attention (working tier only):** {len(stale_rows)}',
        f'**Archive-tier docs (exempt from staleness):** {len(archive_rows)}',
        '',
        'Regenerate: `python3 scripts/report_docs_aging.py`',
        '',
    ]

    if not stale_rows:
        lines.append('All scanned current-truth working-tier docs are fresh.')
        lines.append('')
    else:
        lines.append('## Stale Or Incomplete By Owner Surface')
        lines.append('')
        for owner in sorted(grouped):
            lines.append(f'### {owner}')
            lines.append('')
            lines.append('| Document | Status | Last reviewed | File mtime | Notes |')
            lines.append('| --- | --- | --- | --- | --- |')
            for row in sorted(grouped[owner], key=lambda item: item.rel_path.lower()):
                note = '; '.join(row.notes) if row.notes else '—'
                lines.append(
                    f'| `{row.rel_path}` | {row.status} | {row.last_reviewed or "—"} | '
                    f'{row.file_mtime} | {note} |'
                )
            lines.append('')

    if archive_rows:
        lines.append(
            '## Archive Tier (Dated, Immutable Records — Exempt from Staleness Checks)'
        )
        lines.append('')
        lines.append(
            'These docs are dated records and are not expected to be kept current.'
        )
        lines.append('')
        lines.append('| Document | Owner |')
        lines.append('| --- | --- |')
        for row in sorted(archive_rows, key=lambda item: item.rel_path.lower()):
            lines.append(f'| `{row.rel_path}` | {row.owner} |')
        lines.append('')

    lines.append('## Review Triggers (Current-Truth Docs)')
    lines.append('')
    lines.append('| Document | Owner | Tier | Review trigger |')
    lines.append('| --- | --- | --- | --- |')
    for row in rows:
        lines.append(
            f'| `{row.rel_path}` | {row.owner} | {row.tier} | {row.review_trigger} |'
        )
    lines.append('')
    return '\n'.join(lines)


def write_docs_aging_dashboard(
    *,
    repo_root: Path = _REPO_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
    stale_days: int = STALE_DAYS,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        generate_docs_aging_dashboard(repo_root=repo_root, stale_days=stale_days),
        encoding='utf-8',
    )
    return output_path


def check_docs_aging_dashboard(
    *,
    repo_root: Path = _REPO_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
    stale_days: int = STALE_DAYS,
) -> list[str]:
    expected = generate_docs_aging_dashboard(repo_root=repo_root, stale_days=stale_days)
    if not output_path.is_file():
        try:
            rel = output_path.relative_to(repo_root)
        except ValueError:
            rel = output_path
        return [f'{rel} missing; run: python3 scripts/report_docs_aging.py']
    actual = output_path.read_text(encoding='utf-8')
    if actual == expected:
        return []
    try:
        rel = output_path.relative_to(repo_root)
    except ValueError:
        rel = output_path
    return [f'{rel} is out of date; run: python3 scripts/report_docs_aging.py']


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Generate docs aging dashboard.')
    parser.add_argument(
        '--output',
        default=str(_DEFAULT_OUTPUT),
        help='Output markdown path.',
    )
    parser.add_argument(
        '--check', action='store_true', help='Fail if dashboard is stale.'
    )
    parser.add_argument('--stale-days', type=int, default=STALE_DAYS)
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    if args.check:
        errors = check_docs_aging_dashboard(
            output_path=output_path,
            stale_days=args.stale_days,
        )
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print('Docs aging dashboard check passed.')
        return 0

    written = write_docs_aging_dashboard(
        output_path=output_path,
        stale_days=args.stale_days,
    )
    print(f'wrote {written}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
