"""H4 shadow-to-enforce evidence extraction (ADR-0031, promotion spec section 3.1).

Deterministic, offline analysis of ``h4_governance_shadow`` audit receipts that
prepares the ADR-0031 exit-criterion-1 evidence: the 30-day, zero-false-positive
window. It groups shadow denials into an owner-adjudication worklist and reports
weekly observation coverage per governance surface.

Authority boundary (promotion spec section 3.1, harness-first section 5.1):
an agent may **prepare the candidate list, never the verdicts**. Every emitted
candidate carries ``owner_verdict=None`` and an empty ``owner_note``; only the
owner may mark a denial a false positive. This module reads audit logs and does
arithmetic; it changes no governance mode, wires nothing, and asserts no
promotion readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from teaagent.audit_chain import read_audit_events

#: Audit event type emitted by ``record_h4_shadow_event``.
H4_SHADOW_EVENT_TYPE = 'h4_governance_shadow'

#: Governance surfaces that emit shadow receipts (``h4_integration.py``).
H4_SURFACES = ('approval', 'subagent_launch')

_FLAT_H4_PAYLOAD_KEYS = frozenset(
    {'surface', 'mode', 'allowed', 'enforced', 'reason', 'context', 'details'}
)


@dataclass(frozen=True)
class H4DenialCandidate:
    """One shadow-mode denial awaiting owner adjudication.

    ``owner_verdict`` and ``owner_note`` are deliberately owner-only fields. An
    agent must never populate them: doing so would fabricate the false-positive
    verdict that ADR-0031 exit criterion 1 reserves for the owner.
    """

    ts: Optional[str]
    surface: str
    mode: str
    reason: str
    action: Optional[str]
    target: Optional[str]
    assignee: Optional[str]
    run_id: Optional[str]
    event_id: Optional[str]
    owner_verdict: Optional[bool] = None
    owner_note: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'ts': self.ts,
            'surface': self.surface,
            'mode': self.mode,
            'reason': self.reason,
            'action': self.action,
            'target': self.target,
            'assignee': self.assignee,
            'run_id': self.run_id,
            'event_id': self.event_id,
            'owner_verdict': self.owner_verdict,
            'owner_note': self.owner_note,
        }


@dataclass(frozen=True)
class SurfaceCoverage:
    """Weekly observation coverage for a single governance surface."""

    surface: str
    observed_events: int
    denials: int
    weeks: dict[str, int]
    empty_weeks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            'surface': self.surface,
            'observed_events': self.observed_events,
            'denials': self.denials,
            'weeks': dict(self.weeks),
            'empty_weeks': list(self.empty_weeks),
        }


@dataclass(frozen=True)
class H4EvidenceReport:
    """Deterministic evidence bundle for the ADR-0031 30-day window.

    This is candidate evidence only. ``coverage`` and ``candidates`` are facts
    derived from the audit log; whether the window *passes* criterion 1 is an
    owner verdict recorded elsewhere, not a field here.
    """

    since: Optional[str]
    until: Optional[str]
    total_events: int
    observed_events: int
    skipped_malformed: int
    candidates: list[H4DenialCandidate] = field(default_factory=list)
    coverage: list[SurfaceCoverage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_type': H4_SHADOW_EVENT_TYPE,
            'since': self.since,
            'until': self.until,
            'total_events': self.total_events,
            'observed_events': self.observed_events,
            'skipped_malformed': self.skipped_malformed,
            'candidate_count': len(self.candidates),
            'candidates': [c.to_dict() for c in self.candidates],
            'coverage': [c.to_dict() for c in self.coverage],
            'note': (
                'Candidate evidence only. owner_verdict/owner_note are owner-only; '
                'agents must not classify false positives (ADR-0031 exit criterion 1).'
            ),
        }


def _payload_of(event: dict[str, Any]) -> dict[str, Any]:
    """Return the analysis payload for a raw audit record.

    Disk records nest fields under ``payload``; in-memory captures pass the
    payload directly. Both shapes are accepted so the same extractor serves the
    persisted log and unit tests.
    """
    payload = event.get('payload')
    if isinstance(payload, dict):
        return payload
    return event


def _is_h4_event(event: dict[str, Any], payload: dict[str, Any]) -> bool:
    event_type = event.get('event_type')
    if event_type is not None:
        return event_type == H4_SHADOW_EVENT_TYPE
    # Flattened captures without a top-level event_type must carry the full
    # frozen h4_governance_shadow analysis key-set. A looser surface+allowed
    # fallback would accidentally ingest unrelated governance records.
    return _FLAT_H4_PAYLOAD_KEYS.issubset(payload)


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_bound(
    value: Optional[str], *, end_of_day: bool = False
) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            day = date.fromisoformat(value)
            if len(value) == 10:
                base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                if end_of_day:
                    return base + timedelta(days=1, microseconds=-1)
                return base
        except ValueError:
            pass
    parsed = _parse_ts(value)
    if parsed is not None:
        return parsed
    raise ValueError(f'Invalid date bound {value!r}; use ISO date or datetime.')


def _parse_window(
    since: Optional[str], until: Optional[str]
) -> tuple[Optional[datetime], Optional[datetime]]:
    since_dt = _parse_bound(since)
    until_dt = _parse_bound(until, end_of_day=True)
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise ValueError('Invalid observation window: since must be <= until.')
    return since_dt, until_dt


def _iso_week_key(moment: datetime) -> str:
    iso_year, iso_week, _ = moment.isocalendar()
    return f'{iso_year}-W{iso_week:02d}'


def _week_keys_between(first: datetime, last: datetime) -> list[str]:
    """Every ISO-week key from ``first`` to ``last`` inclusive (deterministic)."""
    keys: list[str] = []
    seen: set[str] = set()
    # Step by day to stay correct across ISO-week/year boundaries.
    cursor = datetime(
        first.year, first.month, first.day, tzinfo=first.tzinfo or timezone.utc
    )
    end = datetime(last.year, last.month, last.day, tzinfo=last.tzinfo or timezone.utc)
    while cursor <= end:
        key = _iso_week_key(cursor)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        cursor += timedelta(days=1)
    return keys


def _in_window(
    moment: Optional[datetime],
    since: Optional[datetime],
    until: Optional[datetime],
) -> bool:
    if moment is None:
        # Undated events are only excluded when a bound is set.
        return since is None and until is None
    if since is not None and moment < since:
        return False
    return not (until is not None and moment > until)


def extract_denial_candidates(
    events: list[dict[str, Any]],
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> list[H4DenialCandidate]:
    """Return the owner-adjudication worklist: shadow events with ``allowed == False``.

    Only denials can be false positives, so only denials become candidates.
    Ordering follows the input (file order) for reproducibility.
    """
    since_dt, until_dt = _parse_window(since, until)
    candidates: list[H4DenialCandidate] = []
    for event in events:
        payload = _payload_of(event)
        if not _is_h4_event(event, payload):
            continue
        if payload.get('allowed') is not False:
            continue
        moment = _parse_ts(event.get('created_at') or payload.get('created_at'))
        if not _in_window(moment, since_dt, until_dt):
            continue
        context = payload.get('context')
        context = context if isinstance(context, dict) else {}
        surface = payload.get('surface')
        if not isinstance(surface, str) or surface not in H4_SURFACES:
            continue
        target = context.get('tool_name')
        if target is None:
            target = context.get('subagent')
        candidates.append(
            H4DenialCandidate(
                ts=event.get('created_at') or payload.get('created_at'),
                surface=surface,
                mode=str(payload.get('mode', '')),
                reason=str(payload.get('reason', '')),
                action=context.get('action'),
                target=target,
                assignee=context.get('assignee'),
                run_id=event.get('run_id') or payload.get('run_id'),
                event_id=event.get('event_id'),
            )
        )
    return candidates


def build_h4_evidence_report(
    events: list[dict[str, Any]],
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> H4EvidenceReport:
    """Assemble the deterministic ADR-0031 criterion-1 evidence bundle."""
    since_dt, until_dt = _parse_window(since, until)

    observed = 0
    skipped = 0
    per_surface_weeks: dict[str, dict[str, int]] = {}
    per_surface_denials: dict[str, int] = {}
    per_surface_observed: dict[str, int] = {}
    week_moments: dict[str, list[datetime]] = {}

    for event in events:
        payload = _payload_of(event)
        if not _is_h4_event(event, payload):
            continue
        surface = payload.get('surface')
        allowed = payload.get('allowed')
        if (
            not isinstance(surface, str)
            or surface not in H4_SURFACES
            or not isinstance(allowed, bool)
        ):
            # An h4 event that lacks the frozen analysis keys (e.g. L0-stripped)
            # cannot be adjudicated; count it rather than silently dropping it.
            skipped += 1
            continue
        moment = _parse_ts(event.get('created_at') or payload.get('created_at'))
        if not _in_window(moment, since_dt, until_dt):
            continue
        observed += 1
        per_surface_observed[surface] = per_surface_observed.get(surface, 0) + 1
        if not allowed:
            per_surface_denials[surface] = per_surface_denials.get(surface, 0) + 1
        if moment is not None:
            key = _iso_week_key(moment)
            weeks = per_surface_weeks.setdefault(surface, {})
            weeks[key] = weeks.get(key, 0) + 1
            week_moments.setdefault(surface, []).append(moment)

    coverage: list[SurfaceCoverage] = []
    for surface in sorted(per_surface_observed):
        weeks = per_surface_weeks.get(surface, {})
        moments = week_moments.get(surface, [])
        empty_weeks: list[str] = []
        if moments:
            span = _week_keys_between(min(moments), max(moments))
            empty_weeks = [key for key in span if key not in weeks]
        coverage.append(
            SurfaceCoverage(
                surface=surface,
                observed_events=per_surface_observed[surface],
                denials=per_surface_denials.get(surface, 0),
                weeks=dict(sorted(weeks.items())),
                empty_weeks=empty_weeks,
            )
        )

    candidates = extract_denial_candidates(events, since=since, until=until)
    return H4EvidenceReport(
        since=since,
        until=until,
        total_events=len(events),
        observed_events=observed,
        skipped_malformed=skipped,
        candidates=candidates,
        coverage=coverage,
    )


def discover_audit_logs(root: str | Path) -> list[Path]:
    """Return de-duplicated audit JSONL paths under ``root/.teaagent``.

    Covers both persistence conventions: the workspace log
    (``.teaagent/audit.jsonl``) and per-run store files
    (``.teaagent/runs/*.jsonl`` and ``.teaagent/runs/**/audit.jsonl``).
    """
    base = Path(root).resolve() / '.teaagent'
    seen: dict[Path, None] = {}
    candidates = [base / 'audit.jsonl']
    runs = base / 'runs'
    if runs.is_dir():
        candidates.extend(sorted(runs.glob('*.jsonl')))
        candidates.extend(sorted(runs.glob('**/audit.jsonl')))
    for path in candidates:
        if path.is_file():
            seen.setdefault(path.resolve(), None)
    return list(seen)


def load_events_from_paths(paths: list[Path]) -> list[dict[str, Any]]:
    """Read and concatenate audit events from every path, in path then file order."""
    events: list[dict[str, Any]] = []
    for path in paths:
        events.extend(read_audit_events(path))
    return events
