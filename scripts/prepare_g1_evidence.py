#!/usr/bin/env python3
"""G1 north-star evidence: organic-use denominator plus friction verdict.

Deterministic, offline extraction over ``.teaagent/runs/runs-index.jsonl`` and
the operator friction log. G1's ratified signal is "zero doc-lookups over a
week of real use"; today no doc-lookup instrument exists on the owner path
(the only ``doc_lookup_count`` lives in the retired WDH-002 external-pilot
spec), so this report measures the *denominator* — organic vs synthetic runs —
and the friction-log signal, then emits a verdict:

- ``unexercised``        — zero organic runs in the window (G1 unevaluable)
- ``friction_observed``  — organic runs exist AND ≥1 open friction entry dated
                           in the window
- ``frictionless``       — organic runs exist AND no open in-window friction
                           entry (doc_lookup still uninstrumented; see note)

Classification is conservative: a run is ``synthetic`` only when its task
string matches a known fixture pattern; everything else counts as organic.
Until B-08 lands an explicit ``origin`` field, "organic" means "not a known
fixture", which over-counts organic runs — the verdict can only err toward
``frictionless``, never toward hiding disuse. This prepares evidence; it
classifies no owner verdict and changes no runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parents[1]

#: Task strings/prefixes produced by test fixtures and smoke scripts. A run
#: whose task matches one of these is classified synthetic; all other tasks
#: are organic candidates. Keep this list honest: add a pattern only for a
#: task string that is provably machine-generated.
_SYNTHETIC_TASK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'^Reply with exactly:', re.IGNORECASE),
    re.compile(r'^Update docs/cli\.md to document clarify command$'),
    re.compile(r'^Use no tools\.', re.IGNORECASE),
    re.compile(r'^Count the number of Python files in this project$'),
)

_FRICTION_HEADING = re.compile(r'^### (\d{4}-\d{2}-\d{2}) - ')
_FRICTION_STATUS = re.compile(r'^- \*\*Status:\*\* (\w+)')


def _parse_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _parse_bound(
    value: Optional[str], *, end_of_day: bool = False
) -> Optional[datetime]:
    if value is None:
        return None
    parsed = _parse_dt(value)
    if parsed is None:
        raise ValueError(f'Invalid date bound: {value!r}; use ISO date or datetime.')
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if end_of_day and len(value) == 10:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def _is_synthetic_task(task: str) -> bool:
    return any(pattern.search(task) for pattern in _SYNTHETIC_TASK_PATTERNS)


def load_runs_index(path: Path) -> list[dict[str, Any]]:
    """Read runs-index.jsonl rows; skip malformed lines."""
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_friction_entries(path: Path) -> list[dict[str, Any]]:
    """Parse friction-log entries: heading date + Status field per entry."""
    entries: list[dict[str, Any]] = []
    if not path.is_file():
        return entries
    current: Optional[dict[str, Any]] = None
    for line in path.read_text(encoding='utf-8').splitlines():
        heading = _FRICTION_HEADING.match(line)
        if heading:
            current = {'date': heading.group(1), 'status': None}
            entries.append(current)
            continue
        if current is not None and current['status'] is None:
            status = _FRICTION_STATUS.match(line.strip())
            if status:
                current['status'] = status.group(1).lower()
    return entries


@dataclass(frozen=True)
class G1EvidenceReport:
    """Deterministic G1 evidence bundle. Candidate evidence only — the verdict
    is a mechanical classification, not an owner attestation of daily use."""

    since: Optional[str]
    until: Optional[str]
    total_runs: int
    organic_runs: int
    synthetic_runs: int
    unknown_runs: int = 0
    friction_entries_in_window: dict[str, int] = field(default_factory=dict)

    doc_lookup_instrumented: bool = False

    @property
    def verdict(self) -> str:
        if self.organic_runs == 0:
            return 'unexercised'
        if self.friction_entries_in_window.get('open', 0) > 0:
            return 'friction_observed'
        return 'frictionless'

    def to_dict(self) -> dict[str, Any]:
        return {
            'since': self.since,
            'until': self.until,
            'total_runs': self.total_runs,
            'organic_runs': self.organic_runs,
            'synthetic_runs': self.synthetic_runs,
            'unknown_runs': self.unknown_runs,
            'friction_entries_in_window': dict(self.friction_entries_in_window),
            'doc_lookup_instrumented': self.doc_lookup_instrumented,
            'verdict': self.verdict,
            'note': (
                'Candidate evidence only. "organic" requires origin == "owner" '
                'in the runs index (B-08); missing/unknown origin counts as '
                'unknown, never organic. doc_lookup is uninstrumented (B-11 '
                'deferred): a frictionless verdict means no open in-window '
                'friction entries, not zero doc-lookups.'
            ),
        }


def build_g1_evidence_report(
    runs: list[dict[str, Any]],
    friction_entries: list[dict[str, Any]],
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> G1EvidenceReport:
    since_dt = _parse_bound(since)
    until_dt = _parse_bound(until, end_of_day=True)
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise ValueError('Invalid observation window: since must be <= until.')

    def _in_window(moment: Optional[datetime]) -> bool:
        if moment is None:
            return since_dt is None and until_dt is None
        if since_dt is not None and moment < since_dt:
            return False
        return not (until_dt is not None and moment > until_dt)

    organic = 0
    synthetic = 0
    unknown = 0
    for row in runs:
        created = _parse_dt(row.get('created_at'))
        if not _in_window(created):
            continue
        # Positive-proof classification (B-08): only origin == 'owner' counts
        # as organic. Missing/unknown origin is NOT organic — a new synthetic
        # task string can never false-positive as owner use.
        origin = row.get('origin')
        if origin == 'owner':
            organic += 1
        elif origin in ('fixture', 'synthetic') or _is_synthetic_task(
            str(row.get('task') or '')
        ):
            synthetic += 1
        else:
            unknown += 1

    friction_counts: dict[str, int] = {'open': 0, 'closed': 0, 'rejected': 0}
    for entry in friction_entries:
        entry_dt = _parse_bound(entry.get('date'))
        if not _in_window(entry_dt):
            continue
        status = entry.get('status') or 'open'
        friction_counts[status] = friction_counts.get(status, 0) + 1

    return G1EvidenceReport(
        since=since,
        until=until,
        total_runs=organic + synthetic + unknown,
        organic_runs=organic,
        synthetic_runs=synthetic,
        unknown_runs=unknown,
        friction_entries_in_window=friction_counts,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--root',
        default='.',
        help='Workspace root containing .teaagent/runs/ (default: .)',
    )
    parser.add_argument(
        '--runs-index',
        default=None,
        help='Explicit runs-index.jsonl path. Overrides --root discovery.',
    )
    parser.add_argument(
        '--friction-log',
        default=None,
        help='Friction log path (default: docs/work-log/operator-friction-log.md).',
    )
    parser.add_argument(
        '--since', default=None, help='ISO date lower bound (inclusive).'
    )
    parser.add_argument(
        '--until', default=None, help='ISO date upper bound (inclusive).'
    )
    parser.add_argument(
        '--output', default=None, help='Write JSON report here instead of stdout.'
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    index_path = (
        Path(args.runs_index)
        if args.runs_index
        else root / '.teaagent' / 'runs' / 'runs-index.jsonl'
    )
    friction_path = (
        Path(args.friction_log)
        if args.friction_log
        else root / 'docs' / 'work-log' / 'operator-friction-log.md'
    )

    if not index_path.is_file():
        print(
            f'No runs index found at {index_path}. Pass --runs-index PATH or '
            'run from a workspace with .teaagent/runs/runs-index.jsonl.',
            file=sys.stderr,
        )
        return 1

    runs = load_runs_index(index_path)
    friction_entries = load_friction_entries(friction_path)
    try:
        report = build_g1_evidence_report(
            runs, friction_entries, since=args.since, until=args.until
        )
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + '\n', encoding='utf-8')
        print(
            f'G1 evidence: {report.verdict}, '
            f'{report.organic_runs} organic / {report.synthetic_runs} synthetic '
            f'run(s) -> {out}'
        )
    else:
        print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
