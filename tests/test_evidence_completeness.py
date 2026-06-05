"""Tests for evidence completeness checklist and categories."""

import json
import tempfile
from pathlib import Path

from teaagent.evidence_summary import (
    RunEvidenceSummary,
    build_evidence_summary,
    summarize_run_events,
)
from teaagent.run_evidence import (
    ApprovalEvidence,
    CommandEvidence,
    KnownGap,
    ModelRouteEvidence,
    RunEvidenceBundle,
    TestEvidence,
    check_evidence_completeness,
    evidence_completeness_checklist,
)
from teaagent.run_store import RunStore

# ── evidence_completeness_checklist ────────────────────────────────────


def test_checklist_returns_all_statuses():
    checklist = evidence_completeness_checklist()
    expected_statuses = {
        'success',
        'failure',
        'cancelled',
        'pending_approval',
        'unknown',
    }
    assert set(checklist.keys()) == expected_statuses


def test_checklist_success_requires_run_started():
    checklist = evidence_completeness_checklist()
    assert 'event:run_started' in checklist['success']
    assert 'event:run_completed' in checklist['success']


def test_checklist_failure_requires_run_failed():
    checklist = evidence_completeness_checklist()
    assert 'event:run_failed' in checklist['failure']


def test_checklist_unknown_minimal():
    checklist = evidence_completeness_checklist()
    assert checklist['unknown'] == ['run_id']


# ── check_evidence_completeness ────────────────────────────────────────


def _make_events(event_types: list[str]) -> list[dict]:
    return [{'event_type': et, 'payload': {}, 'created_at': 0.0} for et in event_types]


def test_complete_success_bundle_passes():
    events = _make_events(['run_started', 'run_completed', 'tool_use'])
    bundle = RunEvidenceBundle(
        run_id='test-1',
        commands_run=[CommandEvidence(command='ls', tool_name='exec')],
        tests=[TestEvidence(test_name='t1', test_file='f.py', status='passed')],
        approvals=[ApprovalEvidence(call_id='c1', tool_name='w', approved=True)],
        routes=[
            ModelRouteEvidence(
                requested_provider='p',
                requested_model='m',
                resolved_provider='p',
                resolved_model='m',
                role='r',
                routing_reason='test',
                policy_source='test',
            )
        ],
        known_gaps=[KnownGap(category='test', description='d', severity='low')],
        workspace_root='/tmp',
        cost_cents=100,
        cost_state='estimated',
        budget_cap_cents=1000,
        undo_available=False,
        undo_mechanism='',
        undo_outcome='',
    )

    missing = check_evidence_completeness(bundle, events, 'success')
    assert missing == [], f'Unexpected missing: {missing}'


def test_missing_event_detected():
    events = _make_events(['run_started'])
    bundle = RunEvidenceBundle(run_id='test-missing-event')
    missing = check_evidence_completeness(bundle, events, 'success')
    assert any('run_completed' in m for m in missing)


def test_missing_field_detected():
    events = _make_events(['run_started', 'run_failed'])
    bundle = RunEvidenceBundle(run_id='test-missing-field')
    missing = check_evidence_completeness(bundle, events, 'failure')
    assert len(missing) > 0


def test_empty_bundle_fails_all_checks():
    events: list[dict] = []
    bundle = RunEvidenceBundle(run_id='empty')
    missing = check_evidence_completeness(bundle, events, 'success')
    assert len(missing) > 0


def test_unknown_status_minimal_check():
    events: list[dict] = []
    bundle = RunEvidenceBundle(run_id='just-id')
    missing = check_evidence_completeness(bundle, events, 'unknown')
    assert missing == []


def test_cancelled_status_requires_cancelled_event():
    events = _make_events(['run_started', 'run_cancelled'])
    bundle = RunEvidenceBundle(
        run_id='cancelled-run',
        commands_run=[CommandEvidence(command='ls', tool_name='exec')],
        tests=[TestEvidence(test_name='t1', test_file='f.py', status='passed')],
        budget_cap_cents=500,
    )
    missing = check_evidence_completeness(bundle, events, 'cancelled')
    assert missing == [], f'Unexpected missing: {missing}'

    events_no_cancel = _make_events(['run_started'])
    missing2 = check_evidence_completeness(bundle, events_no_cancel, 'cancelled')
    assert any('run_cancelled' in m for m in missing2)


def test_pending_approval_requires_paused_event():
    events = _make_events(['run_started', 'run_paused'])
    bundle = RunEvidenceBundle(
        run_id='pending-run',
        commands_run=[CommandEvidence(command='ls', tool_name='exec')],
        tests=[TestEvidence(test_name='t1', test_file='f.py', status='passed')],
        approvals=[ApprovalEvidence(call_id='c1', tool_name='w', approved=False)],
        budget_cap_cents=500,
    )
    missing = check_evidence_completeness(bundle, events, 'pending_approval')
    assert missing == [], f'Unexpected missing: {missing}'

    events_no_pause = _make_events(['run_started'])
    missing2 = check_evidence_completeness(bundle, events_no_pause, 'pending_approval')
    assert any('run_paused' in m for m in missing2)


# ── evidence categories in summaries ───────────────────────────────────


def _write_run_events(root: str, run_id: str, events: list[dict]) -> Path:
    store = RunStore(root)
    run_path = store.run_path(run_id)
    lines = '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n'
    run_path.write_text(lines, encoding='utf-8')
    return run_path


def test_evidence_categories_default_zero():
    s = RunEvidenceSummary(run_id='test-cat')
    assert s.evidence_categories == {}


def test_evidence_categories_in_to_dict():
    s = RunEvidenceSummary(
        run_id='test-cat',
        evidence_categories={
            'verified': 3,
            'claimed': 1,
            'not_tested': 0,
            'known_failure': 2,
        },
    )
    d = s.to_dict()
    assert d['evidence_categories'] == {
        'verified': 3,
        'claimed': 1,
        'not_tested': 0,
        'known_failure': 2,
    }


def test_summarize_run_events_tracks_categories():
    events = [
        {'event_type': 'run_started', 'timestamp': 'T1'},
        {
            'event_type': 'test_run',
            'payload': {'status': 'passed', 'test_name': 't1', 'test_file': 'f.py'},
        },
        {
            'event_type': 'test_run',
            'payload': {'status': 'passed', 'test_name': 't2', 'test_file': 'f.py'},
        },
        {
            'event_type': 'test_run',
            'payload': {'status': 'failed', 'test_name': 't3', 'test_file': 'f.py'},
        },
        {
            'event_type': 'test_run',
            'payload': {'status': 'skipped', 'test_name': 't4', 'test_file': 'f.py'},
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'x.py'},
            },
        },
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'y.py'},
            },
        },
        {'event_type': 'run_failed', 'payload': {'message': 'fail'}},
        {'event_type': 'run_completed', 'timestamp': 'T2'},
    ]
    result = summarize_run_events(events)
    cats = result['evidence_categories']
    assert cats['verified'] == 2
    assert cats['known_failure'] >= 2  # 1 failed test + 1 run_failed
    assert cats['not_tested'] == 1
    assert cats['claimed'] >= 2


def test_build_evidence_summary_includes_categories():
    events = [
        {'run_id': 'r', 'event_type': 'run_started', 'timestamp': 'T1'},
        {
            'run_id': 'r',
            'event_type': 'test_run',
            'payload': {'status': 'passed', 'test_name': 't1', 'test_file': 'f.py'},
        },
        {
            'run_id': 'r',
            'event_type': 'test_run',
            'payload': {'status': 'failed', 'test_name': 't2', 'test_file': 'f.py'},
        },
        {'run_id': 'r', 'event_type': 'run_completed', 'timestamp': 'T2'},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_run_events(tmpdir, 'r', events)
        store = RunStore(tmpdir)
        summary = build_evidence_summary(store, 'r', tmpdir)
        assert summary.evidence_categories['verified'] == 1
        assert summary.evidence_categories['known_failure'] == 1


def test_empty_events_categories_zeroed():
    result = summarize_run_events([])
    cats = result['evidence_categories']
    assert cats == {'verified': 0, 'claimed': 0, 'not_tested': 0, 'known_failure': 0}
