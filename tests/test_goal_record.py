"""Tests for GoalRecord, GoalStore, and goal lifecycle audit events."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from teaagent.goal_record import GoalRecord, GoalStore


def test_goal_record_serialization_round_trip():
    """GoalRecord.to_dict() + GoalRecord.from_dict() round-trip preserves all fields."""
    goal = GoalRecord(
        goal_id='g-001',
        objective='Refactor authentication module',
        status='active',
        spec_id='spec-abc',
        spec_hash='sha256:deadbeef',
        task_ids=['t1', 't2', 't3'],
        run_ids=['run-1', 'run-2'],
        cost_cents=150.5,
        memory_ids=['mem-1'],
        review_ids=['rev-1'],
        human_gate_ids=['hg-1'],
        blockers=['waiting on API key rotation'],
        next_gate='deploy-review',
        created_at='2026-06-05T00:00:00Z',
        updated_at='2026-06-05T12:00:00Z',
    )

    data = goal.to_dict()
    restored = GoalRecord.from_dict(data)

    assert restored.goal_id == goal.goal_id
    assert restored.objective == goal.objective
    assert restored.status == goal.status
    assert restored.spec_id == goal.spec_id
    assert restored.spec_hash == goal.spec_hash
    assert restored.task_ids == goal.task_ids
    assert restored.run_ids == goal.run_ids
    assert restored.cost_cents == goal.cost_cents
    assert restored.memory_ids == goal.memory_ids
    assert restored.review_ids == goal.review_ids
    assert restored.human_gate_ids == goal.human_gate_ids
    assert restored.blockers == goal.blockers
    assert restored.next_gate == goal.next_gate
    assert restored.created_at == goal.created_at
    assert restored.updated_at == goal.updated_at


def test_goal_record_defaults():
    """GoalRecord uses sensible defaults for empty fields."""
    goal = GoalRecord(goal_id='g-002', objective='Do something')
    assert goal.status == 'proposed'
    assert goal.spec_id == ''
    assert goal.task_ids == []
    assert goal.run_ids == []
    assert goal.cost_cents == 0.0
    assert goal.memory_ids == []
    assert goal.blockers == []
    assert goal.next_gate == ''


def test_goal_store_save_and_load():
    """GoalStore persists and loads a GoalRecord correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(
            goal_id='g-save',
            objective='Test save/load',
            status='proposed',
            spec_id='spec-1',
        )
        store.save(goal)

        loaded = store.load('g-save')
        assert loaded.goal_id == 'g-save'
        assert loaded.objective == 'Test save/load'
        assert loaded.status == 'proposed'
        assert loaded.spec_id == 'spec-1'
        assert loaded.created_at != ''  # filled on save
        assert loaded.updated_at != ''


def test_goal_store_save_fills_timestamps():
    """GoalStore.save fills created_at and updated_at when empty."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-ts', objective='Timestamp test')
        assert goal.created_at == ''
        assert goal.updated_at == ''

        store.save(goal)
        assert goal.created_at != ''
        assert goal.updated_at != ''
        assert goal.created_at == goal.updated_at  # first save sets both to same


def test_goal_store_save_updates_timestamp():
    """GoalStore.save updates only updated_at on subsequent saves."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-ts2', objective='Update test')
        store.save(goal)
        first_created = goal.created_at
        first_updated = goal.updated_at

        import time

        time.sleep(0.01)  # ensure timestamp changes
        goal.status = 'active'
        store.save(goal)

        assert goal.created_at == first_created  # created_at never changes
        assert goal.updated_at != first_updated


def test_goal_store_save_rejects_invalid_status():
    """GoalStore.save raises ValueError for invalid statuses."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-bad', objective='Bad status', status='lunchtime')
        with pytest.raises(ValueError) as exc:
            store.save(goal)
        assert 'lunchtime' in str(exc.value)


def test_goal_store_list():
    """GoalStore.list returns all saved goals ordered by updated_at descending."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)

        goal_a = GoalRecord(goal_id='g-a', objective='First')
        goal_b = GoalRecord(goal_id='g-b', objective='Second')
        store.save(goal_a)
        store.save(goal_b)

        import time

        time.sleep(0.01)
        goal_a.status = 'active'
        store.save(goal_a)  # bump updated_at of g-a

        goals = store.list()
        assert len(goals) >= 2
        # Most recently updated should be first
        assert goals[0].goal_id == 'g-a'


def test_goal_store_load_missing_raises():
    """GoalStore.load raises FileNotFoundError for unknown goal_id."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        with pytest.raises(FileNotFoundError):
            store.load('nonexistent')


def test_goal_store_delete():
    """GoalStore.delete removes the goal file."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-del', objective='Delete me')
        store.save(goal)
        store.delete('g-del')

        with pytest.raises(FileNotFoundError):
            store.load('g-del')


def test_goal_store_storage_path():
    """GoalStore creates .teaagent/goals/ under the given root."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = GoalStore(root)
        goal = GoalRecord(goal_id='g-path', objective='Path test')
        store.save(goal)

        expected_path = root / '.teaagent' / 'goals' / 'g-path.json'
        assert expected_path.is_file()


def test_audit_event_goal_set():
    """AuditLogger records goal_set events with payload."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(
            goal_id='g-audit',
            objective='Audit test goal',
            status='proposed',
            spec_id='spec-xyz',
        )
        store.save(goal)
        store.record_goal_event(
            'g-audit',
            'goal_set',
            objective='Audit test goal',
            spec_id='spec-xyz',
        )

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-audit_audit.jsonl'
        assert audit_path.is_file()

        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) >= 1
        event = json.loads(lines[0])
        assert event['event_type'] == 'goal_set'
        assert event['run_id'] == 'g-audit'
        assert event['payload']['objective'] == 'Audit test goal'


def test_audit_event_goal_updated():
    """Record goal_updated with status change payload."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-upd', objective='Update me', status='proposed')
        store.save(goal)

        store.record_goal_event(
            'g-upd',
            'goal_updated',
            previous_status='proposed',
            new_status='active',
        )

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-upd_audit.jsonl'
        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        event = json.loads(lines[0])
        assert event['event_type'] == 'goal_updated'
        assert event['payload']['previous_status'] == 'proposed'
        assert event['payload']['new_status'] == 'active'


def test_audit_event_goal_completed():
    """Record goal_completed with outcome summary."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-done', objective='Finish line', status='active')
        store.save(goal)

        store.record_goal_event(
            'g-done',
            'goal_completed',
            total_runs=3,
            total_cost_cents=450.0,
            final_answer='All tests pass',
        )

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-done_audit.jsonl'
        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        event = json.loads(lines[0])
        assert event['event_type'] == 'goal_completed'
        assert event['payload']['total_runs'] == 3
        assert event['payload']['total_cost_cents'] == 450.0


def test_audit_event_goal_failed():
    """Record goal_failed with blocker information."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-fail', objective='Fail test', status='active')
        store.save(goal)

        store.record_goal_event(
            'g-fail',
            'goal_failed',
            reason='Budget exhausted',
            cost_cents=5000.0,
        )

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-fail_audit.jsonl'
        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        event = json.loads(lines[0])
        assert event['event_type'] == 'goal_failed'
        assert event['payload']['reason'] == 'Budget exhausted'


def test_audit_event_goal_blocked():
    """Record goal_blocked with blocker details."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(goal_id='g-block', objective='Blocked goal', status='active')
        store.save(goal)

        store.record_goal_event(
            'g-block',
            'goal_blocked',
            blocker='Waiting for upstream dependency v2.0',
            severity='high',
        )

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-block_audit.jsonl'
        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        event = json.loads(lines[0])
        assert event['event_type'] == 'goal_blocked'
        assert event['payload']['blocker'] == 'Waiting for upstream dependency v2.0'
        assert event['payload']['severity'] == 'high'


def test_integration_multiple_runs_same_goal():
    """Multiple runs can be linked to the same goal via run_ids."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        goal = GoalRecord(
            goal_id='g-multi',
            objective='Multi-run goal',
            status='active',
            run_ids=['run-aa', 'run-bb', 'run-cc'],
        )
        store.save(goal)

        loaded = store.load('g-multi')
        assert len(loaded.run_ids) == 3
        assert 'run-aa' in loaded.run_ids
        assert 'run-bb' in loaded.run_ids
        assert 'run-cc' in loaded.run_ids

        # Append another run
        loaded.run_ids.append('run-dd')
        loaded.cost_cents += 100.0
        store.save(loaded)

        reloaded = store.load('g-multi')
        assert len(reloaded.run_ids) == 4
        assert 'run-dd' in reloaded.run_ids
        assert reloaded.cost_cents == 100.0


def test_integration_goal_lifecycle_state_machine():
    """GoalRecord transitions through the full state machine."""
    goal = GoalRecord(goal_id='g-lifecycle', objective='Full lifecycle test')
    assert goal.status == 'proposed'

    goal.status = 'active'
    assert goal.status == 'active'

    # Active can transition to completed, failed, blocked, or abandoned
    for valid_end in ('completed', 'failed', 'blocked', 'abandoned'):
        g = GoalRecord(goal_id='g-lifecycle', objective='Test', status=valid_end)
        assert g.status == valid_end


def test_goal_record_from_dict_partial():
    """GoalRecord.from_dict handles missing keys with defaults."""
    data = {'goal_id': 'g-min', 'objective': 'Minimal goal'}
    goal = GoalRecord.from_dict(data)
    assert goal.goal_id == 'g-min'
    assert goal.objective == 'Minimal goal'
    assert goal.status == 'proposed'
    assert goal.task_ids == []
    assert goal.run_ids == []


def test_goal_record_audit_logger_standalone():
    """GoalStore.goal_audit_logger creates a working AuditLogger."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        audit = store.goal_audit_logger('g-standalone')
        audit.record('goal_set', 'g-standalone', objective='Standalone test')
        audit.record('goal_updated', 'g-standalone', new_status='active')

        audit_path = Path(tmp) / '.teaagent' / 'goals' / 'g-standalone_audit.jsonl'
        assert audit_path.is_file()
        lines = audit_path.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) == 2


def test_goal_store_list_empty():
    """GoalStore.list returns empty list for fresh store."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        assert store.list() == []


def test_evidence_bundle_goal_id():
    """RunEvidenceBundle accepts and serializes goal_id."""
    from teaagent.run_evidence import RunEvidenceBundle, build_run_evidence_bundle

    bundle = RunEvidenceBundle(run_id='run-g1', goal_id='g-001')
    data = bundle.to_dict()
    assert data['goal_id'] == 'g-001'

    # build_run_evidence_bundle passes goal_id through
    with tempfile.TemporaryDirectory() as tmp:
        # No actual run needed — it'll return early with FileNotFoundError
        bundle2 = build_run_evidence_bundle(tmp, 'nonexistent-run', goal_id='g-002')
        assert bundle2.goal_id == 'g-002'
        assert bundle2.run_id == 'nonexistent-run'


def test_goal_store_skip_corrupt_files():
    """GoalStore.list skips corrupt JSON files."""
    with tempfile.TemporaryDirectory() as tmp:
        store = GoalStore(tmp)
        # Write a valid goal
        goal = GoalRecord(goal_id='g-ok', objective='OK')
        store.save(goal)

        # Write a corrupt file
        corrupt_path = Path(tmp) / '.teaagent' / 'goals' / 'g-corrupt.json'
        corrupt_path.write_text('not valid json {{{', encoding='utf-8')

        goals = store.list()
        # Should only contain the valid goal, skipping the corrupt one
        goal_ids = {g.goal_id for g in goals}
        assert 'g-ok' in goal_ids
        # Corrupt file should be skipped (not cause crash)
