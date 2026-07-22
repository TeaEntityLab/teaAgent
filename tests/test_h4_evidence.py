# test-type: contract
"""Tests for the ADR-0031 H4 shadow-denial evidence extractor.

Companion to docs/specs/rbac-shadow-to-enforce-promotion-spec-2026-07-11.md
section 3.1 (exit criterion 1: the 30-day zero-false-positive window). The
extractor prepares the owner-adjudication worklist and weekly coverage; it must
never classify a denial as a false positive (that verdict is owner-only) and
must not change any governance mode.

These tests defend observable contracts:
- only denials become candidates (an allow can never be a false positive);
- every candidate is unadjudicated (owner_verdict is None);
- nested (disk) and flat (in-memory) payload shapes both parse;
- per-surface weekly coverage counts and empty-week gap detection are correct;
- the observation window bounds are inclusive and honored;
- malformed / L0-stripped h4 events are counted, not silently dropped;
- the CLI produces the same evidence from a real AuditLogger-written JSONL.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from teaagent.audit import AuditLogger
from teaagent.governance.h4_evidence import (
    H4_SHADOW_EVENT_TYPE,
    build_h4_evidence_report,
    discover_audit_logs,
    extract_denial_candidates,
    load_events_from_paths,
)
from teaagent.governance.h4_integration import (
    H4GovernanceMode,
    record_h4_shadow_event,
)

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / 'scripts' / 'prepare_h4_evidence.py'


def _disk_event(
    *,
    event_type: str = H4_SHADOW_EVENT_TYPE,
    surface: str = 'approval',
    allowed: bool = False,
    mode: str = 'shadow',
    reason: str = 'Policy p1 would deny',
    context: dict[str, Any] | None = None,
    created_at: str | None = '2026-07-01T12:00:00+00:00',
    run_id: str = 'run-1',
    event_id: str = 'evt-1',
) -> dict[str, Any]:
    """Build a record in the on-disk shape: fields nested under 'payload'."""
    return {
        'event_id': event_id,
        'event_type': event_type,
        'run_id': run_id,
        'created_at': created_at,
        'payload': {
            'surface': surface,
            'mode': mode,
            'allowed': allowed,
            'enforced': False,
            'reason': reason,
            'context': context if context is not None else {'action': 'approve_tool'},
            'details': [],
        },
    }


def test_only_denials_become_candidates() -> None:
    """An allowed event is never a candidate; only allowed==False qualifies."""
    events = [
        _disk_event(allowed=True, event_id='allow-1'),
        _disk_event(allowed=False, event_id='deny-1'),
    ]
    candidates = extract_denial_candidates(events)
    assert [c.event_id for c in candidates] == ['deny-1']


def test_candidates_are_unadjudicated_by_default() -> None:
    """The extractor must never fill the owner-only verdict fields."""
    events = [_disk_event(allowed=False)]
    (candidate,) = extract_denial_candidates(events)
    assert candidate.owner_verdict is None
    assert candidate.owner_note == ''
    # And the serialized form keeps the verdict null for the owner to fill.
    assert candidate.to_dict()['owner_verdict'] is None


def test_candidate_extracts_target_and_action_from_context() -> None:
    """Approval denials surface tool_name as target; action is preserved."""
    events = [
        _disk_event(
            allowed=False,
            context={'action': 'approve_tool', 'tool_name': 'write_file'},
        )
    ]
    (candidate,) = extract_denial_candidates(events)
    assert candidate.surface == 'approval'
    assert candidate.action == 'approve_tool'
    assert candidate.target == 'write_file'


def test_subagent_launch_target_falls_back_to_subagent() -> None:
    """When there is no tool_name, the subagent name is the target."""
    events = [
        _disk_event(
            surface='subagent_launch',
            allowed=False,
            context={
                'action': 'launch_subagent',
                'subagent': 'reviewer',
                'assignee': 'agent-x',
            },
        )
    ]
    (candidate,) = extract_denial_candidates(events)
    assert candidate.surface == 'subagent_launch'
    assert candidate.target == 'reviewer'
    assert candidate.assignee == 'agent-x'


def test_flat_payload_shape_is_accepted() -> None:
    """In-memory captures without a 'payload' wrapper still parse.

    record_h4_shadow_event forwards payload as top-level kwargs to audit.record;
    tests and sinks may observe that flat shape, so the extractor must handle it.
    """
    flat = {
        'surface': 'approval',
        'mode': 'shadow',
        'allowed': False,
        'enforced': False,
        'reason': 'Policy p2 would deny',
        'context': {'action': 'approve_tool', 'tool_name': 'run_shell'},
        'details': [],
    }
    (candidate,) = extract_denial_candidates([flat])
    assert candidate.target == 'run_shell'
    assert candidate.mode == 'shadow'


def test_flat_non_h4_shape_is_ignored_even_with_surface_and_allowed() -> None:
    """A loose surface+allowed payload is not enough to identify H4 evidence."""
    unrelated = {
        'surface': 'approval',
        'allowed': False,
        'reason': 'ordinary approval receipt',
    }
    assert extract_denial_candidates([unrelated]) == []
    report = build_h4_evidence_report([unrelated])
    assert report.observed_events == 0
    assert report.skipped_malformed == 0


def test_non_h4_events_are_ignored() -> None:
    """Events of other types never enter the H4 evidence packet."""
    events = [
        {'event_type': 'run_started', 'run_id': 'r', 'payload': {'task': 't'}},
        _disk_event(allowed=False, event_id='deny-1'),
    ]
    report = build_h4_evidence_report(events)
    assert report.total_events == 2
    assert report.observed_events == 1
    assert [c.event_id for c in report.candidates] == ['deny-1']


def test_weekly_coverage_counts_and_detects_gaps() -> None:
    """Coverage groups by ISO week and lists empty weeks inside the span.

    2026-07-01 is ISO week 27; 2026-07-15 is week 29. Week 28 has no event and
    must appear as an empty week — the signal the owner needs for the
    '>= 1 real run per week' criterion.
    """
    events = [
        _disk_event(allowed=True, created_at='2026-07-01T09:00:00+00:00'),
        _disk_event(allowed=False, created_at='2026-07-15T09:00:00+00:00'),
    ]
    report = build_h4_evidence_report(events)
    (coverage,) = report.coverage
    assert coverage.surface == 'approval'
    assert coverage.observed_events == 2
    assert coverage.denials == 1
    assert coverage.weeks == {'2026-W27': 1, '2026-W29': 1}
    assert coverage.empty_weeks == ['2026-W28']


def test_coverage_is_per_surface() -> None:
    """Approval and subagent_launch are reported as separate surfaces."""
    events = [
        _disk_event(surface='approval', allowed=False),
        _disk_event(surface='subagent_launch', allowed=True),
    ]
    report = build_h4_evidence_report(events)
    surfaces = {c.surface for c in report.coverage}
    assert surfaces == {'approval', 'subagent_launch'}


def test_unknown_h4_surface_is_counted_malformed_not_coverage() -> None:
    """Only the frozen H4 surfaces can contribute coverage or candidates."""
    events = [_disk_event(surface='future_surface', allowed=False)]
    report = build_h4_evidence_report(events)
    assert report.skipped_malformed == 1
    assert report.observed_events == 0
    assert report.coverage == []
    assert extract_denial_candidates(events) == []


def test_window_bounds_are_inclusive_and_filter() -> None:
    """since/until bound the observation window inclusively; date-only until covers the day."""
    events = [
        _disk_event(
            allowed=False, created_at='2026-06-30T00:00:00+00:00', event_id='before'
        ),
        _disk_event(
            allowed=False, created_at='2026-07-05T00:00:00+00:00', event_id='inside'
        ),
        _disk_event(
            allowed=False,
            created_at='2026-07-30T23:59:59+00:00',
            event_id='inside-end-day',
        ),
        _disk_event(
            allowed=False, created_at='2026-07-31T00:00:00+00:00', event_id='after'
        ),
    ]
    candidates = extract_denial_candidates(
        events, since='2026-07-01', until='2026-07-30'
    )
    assert [c.event_id for c in candidates] == ['inside', 'inside-end-day']


def test_inverted_observation_window_is_rejected() -> None:
    """A since date after until is operator error, not an empty evidence packet."""
    try:
        build_h4_evidence_report([], since='2026-07-31', until='2026-07-01')
    except ValueError as exc:
        assert 'since must be <= until' in str(exc)
    else:  # pragma: no cover - makes the failure message explicit
        raise AssertionError('expected invalid observation window to raise ValueError')


def test_malformed_h4_event_is_counted_not_dropped() -> None:
    """An h4 event missing the frozen analysis keys is counted as skipped.

    An L0-stripped receipt (no surface/allowed) cannot be adjudicated. Silently
    dropping it would hide observation-window gaps, so it must be surfaced.
    """
    events = [
        {
            'event_type': H4_SHADOW_EVENT_TYPE,
            'run_id': 'r',
            'created_at': '2026-07-02T00:00:00+00:00',
            'payload': {'event_type': H4_SHADOW_EVENT_TYPE},
        },
        _disk_event(allowed=False),
    ]
    report = build_h4_evidence_report(events)
    assert report.skipped_malformed == 1
    assert report.observed_events == 1


def test_empty_input_produces_valid_empty_report() -> None:
    """No events yields a well-formed, empty evidence packet (no crash)."""
    report = build_h4_evidence_report([])
    data = report.to_dict()
    assert data['candidate_count'] == 0
    assert data['candidates'] == []
    assert data['coverage'] == []
    assert data['observed_events'] == 0


def test_report_note_states_owner_only_boundary() -> None:
    """The serialized packet documents that verdicts are owner-only."""
    note = build_h4_evidence_report([]).to_dict()['note']
    assert 'owner-only' in note
    assert 'ADR-0031' in note


def _write_real_audit_log(root: Path) -> Path:
    """Emit two shadow receipts through the real AuditLogger to disk."""
    log_path = root / '.teaagent' / 'audit.jsonl'
    with patch.object(Path, 'home', return_value=root):
        audit = AuditLogger(path=log_path)
        record_h4_shadow_event(
            audit,
            'run-a',
            surface='approval',
            mode=H4GovernanceMode.SHADOW,
            allowed=False,
            reason='Policy deny-all would deny',
            context={'action': 'approve_tool', 'tool_name': 'write_file'},
            enforced=False,
            details=[],
        )
        record_h4_shadow_event(
            audit,
            'run-a',
            surface='approval',
            mode=H4GovernanceMode.SHADOW,
            allowed=True,
            reason='Policy evaluation would allow',
            context={'action': 'approve_tool', 'tool_name': 'read_file'},
            enforced=False,
            details=[],
        )
    return log_path


def test_extractor_reads_real_auditlogger_jsonl() -> None:
    """End-to-end: the extractor consumes real on-disk audit records."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_real_audit_log(root)
        paths = discover_audit_logs(root)
        assert paths, 'discovery should find .teaagent/audit.jsonl'
        events = load_events_from_paths(paths)
        report = build_h4_evidence_report(events)
        assert report.observed_events == 2
        assert len(report.candidates) == 1
        (candidate,) = report.candidates
        assert candidate.target == 'write_file'
        assert candidate.owner_verdict is None


def test_cli_emits_json_packet_from_real_log() -> None:
    """The CLI script produces the same deterministic packet on stdout."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_path = _write_real_audit_log(root)
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), '--audit-log', str(log_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload['event_type'] == H4_SHADOW_EVENT_TYPE
        assert payload['observed_events'] == 2
        assert payload['candidate_count'] == 1
        assert payload['candidates'][0]['owner_verdict'] is None


def test_cli_missing_log_fails_cleanly() -> None:
    """With no logs found the CLI exits non-zero with an actionable message."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), '--root', tmp],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert 'No audit logs found' in result.stderr


def test_cli_invalid_window_fails_cleanly() -> None:
    """CLI propagates invalid observation windows as actionable operator errors."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        log_path = _write_real_audit_log(root)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                '--audit-log',
                str(log_path),
                '--since',
                '2026-07-31',
                '--until',
                '2026-07-01',
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert 'since must be <= until' in result.stderr
