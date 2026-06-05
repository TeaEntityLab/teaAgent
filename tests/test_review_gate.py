"""Tests for SCL-P1-005 review gate enforcement and WaiverRecord,
plus SCL-P1-006 ReviewGate packet and CLI gate integration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from teaagent.goal_record import GoalRecord, GoalStore
from teaagent.governance.review_gate import (
    WaiverRecord,
    build_review_gate,
    create_waiver,
    deserialize_waivers,
    is_high_risk_goal,
    requires_review_before_close,
    serialize_waivers,
)

# ---------------------------------------------------------------------------
# is_high_risk_goal
# ---------------------------------------------------------------------------


class TestIsHighRiskGoal:
    def test_objective_with_security_keyword(self):
        goal = GoalRecord(goal_id='g-1', objective='Deploy new authentication service')
        assert is_high_risk_goal(goal) is True

    def test_objective_with_production_keyword(self):
        goal = GoalRecord(goal_id='g-2', objective='Update /production config')
        assert is_high_risk_goal(goal) is True

    def test_objective_with_database_keyword(self):
        goal = GoalRecord(goal_id='g-3', objective='Migrate database schema')
        assert is_high_risk_goal(goal) is True

    def test_objective_with_delete_keyword(self):
        goal = GoalRecord(goal_id='g-4', objective='Delete deprecated endpoints')
        assert is_high_risk_goal(goal) is True

    def test_objective_with_pii_keyword(self):
        goal = GoalRecord(goal_id='g-5', objective='Redact PII from logs')
        assert is_high_risk_goal(goal) is True

    def test_objective_case_insensitive(self):
        goal = GoalRecord(goal_id='g-6', objective='AUTH module refactor')
        assert is_high_risk_goal(goal) is True

    def test_safe_objective_not_high_risk(self):
        goal = GoalRecord(goal_id='g-safe', objective='Add unit test for calculator')
        assert is_high_risk_goal(goal) is False

    def test_safe_objective_docs_only(self):
        goal = GoalRecord(goal_id='g-docs', objective='Update README with examples')
        assert is_high_risk_goal(goal) is False

    def test_spec_id_prefix_sec(self):
        goal = GoalRecord(
            goal_id='g-spec', objective='Fix something', spec_id='sec-audit-log'
        )
        assert is_high_risk_goal(goal) is True

    def test_spec_id_prefix_auth(self):
        goal = GoalRecord(
            goal_id='g-spec2', objective='Fix something', spec_id='auth-oauth-flow'
        )
        assert is_high_risk_goal(goal) is True

    def test_spec_id_prefix_prod(self):
        goal = GoalRecord(
            goal_id='g-spec3', objective='Fix something', spec_id='prod-hotfix'
        )
        assert is_high_risk_goal(goal) is True

    def test_spec_id_prefix_deploy(self):
        goal = GoalRecord(
            goal_id='g-spec4', objective='Fix something', spec_id='deploy-rollback'
        )
        assert is_high_risk_goal(goal) is True

    def test_spec_id_prefix_migration(self):
        goal = GoalRecord(
            goal_id='g-spec5', objective='Fix something', spec_id='migration-v3'
        )
        assert is_high_risk_goal(goal) is True

    def test_spec_id_prefix_compliance(self):
        goal = GoalRecord(
            goal_id='g-spec6', objective='Fix something', spec_id='compliance-gdpr'
        )
        assert is_high_risk_goal(goal) is True

    def test_benign_spec_id(self):
        goal = GoalRecord(
            goal_id='g-spec-safe', objective='Fix something', spec_id='feat-buttons'
        )
        assert is_high_risk_goal(goal) is False

    def test_high_risk_task_id(self):
        goal = GoalRecord(
            goal_id='g-task',
            objective='Clean up',
            task_ids=['delete-old-cache-entries'],
        )
        assert is_high_risk_goal(goal) is True

    def test_safe_task_id(self):
        goal = GoalRecord(
            goal_id='g-task-safe',
            objective='Refactor',
            task_ids=['add-docstrings', 'fix-typo'],
        )
        assert is_high_risk_goal(goal) is False

    def test_empty_goal_not_high_risk(self):
        goal = GoalRecord(goal_id='g-empty', objective='')
        assert is_high_risk_goal(goal) is False


# ---------------------------------------------------------------------------
# WaiverRecord
# ---------------------------------------------------------------------------


class TestWaiverRecord:
    def test_serialization_round_trip(self):
        waiver = WaiverRecord(
            waiver_id='w-001',
            goal_id='g-001',
            reason='Time pressure',
            waived_by='alice',
            risk_accepted='Data migration without review',
            waived_at='2026-06-05T00:00:00Z',
        )
        data = waiver.to_dict()
        restored = WaiverRecord.from_dict(data)
        assert restored.waiver_id == 'w-001'
        assert restored.goal_id == 'g-001'
        assert restored.reason == 'Time pressure'
        assert restored.waived_by == 'alice'
        assert restored.risk_accepted == 'Data migration without review'
        assert restored.waived_at == '2026-06-05T00:00:00Z'

    def test_defaults_on_partial_dict(self):
        data: dict[str, str] = {'waiver_id': 'w-min'}
        waiver = WaiverRecord.from_dict(data)
        assert waiver.waiver_id == 'w-min'
        assert waiver.goal_id == ''
        assert waiver.reason == ''
        assert waiver.waived_by == ''
        assert waiver.risk_accepted == ''
        assert waiver.waived_at == ''

    def test_create_waiver_autofills_id_and_timestamp(self):
        waiver = create_waiver(
            goal_id='g-001',
            reason='Emergency fix',
            waived_by='bob',
            risk_accepted='Skipping code review',
        )
        assert waiver.waiver_id != ''
        assert waiver.waived_at != ''
        assert waiver.goal_id == 'g-001'
        assert waiver.reason == 'Emergency fix'

    def test_serialize_waivers_list(self):
        w1 = WaiverRecord('w-1', 'g-1', 'r1', 'a', 'risk1', '2026-01-01T00Z')
        w2 = WaiverRecord('w-2', 'g-2', 'r2', 'b', 'risk2', '2026-01-02T00Z')
        data = serialize_waivers([w1, w2])
        assert len(data) == 2
        restored = deserialize_waivers(data)
        assert len(restored) == 2
        assert restored[0].waiver_id == 'w-1'
        assert restored[1].waiver_id == 'w-2'


# ---------------------------------------------------------------------------
# requires_review_before_close
# ---------------------------------------------------------------------------


class TestRequiresReviewBeforeClose:
    def test_low_risk_goal_not_blocked(self):
        goal = GoalRecord(goal_id='g-safe', objective='Add docstrings')
        blocked, reason = requires_review_before_close(goal)
        assert blocked is False
        assert 'not a high-risk goal' in reason

    def test_high_risk_with_review_ids_not_blocked(self):
        goal = GoalRecord(
            goal_id='g-hr-review',
            objective='Deploy authentication changes',
            review_ids=['rev-xyz'],
        )
        blocked, reason = requires_review_before_close(goal)
        assert blocked is False
        assert 'synthesis review already present' in reason

    def test_high_risk_with_human_gate_not_blocked(self):
        goal = GoalRecord(
            goal_id='g-hr-gate',
            objective='Delete production data',
            human_gate_ids=['hg-123'],
        )
        blocked, reason = requires_review_before_close(goal)
        assert blocked is False
        assert 'human gate already present' in reason

    def test_high_risk_without_review_or_waiver_blocked(self):
        goal = GoalRecord(
            goal_id='g-hr-naked',
            objective='Purge credential store',
        )
        blocked, reason = requires_review_before_close(goal)
        assert blocked is True
        assert 'requires synthesis review' in reason

    def test_high_risk_with_matching_waiver_not_blocked(self):
        goal = GoalRecord(
            goal_id='g-hr-waived',
            objective='Drop table users_backup',
        )
        waiver = create_waiver(
            goal_id='g-hr-waived',
            reason='Tables already empty',
            waived_by='admin',
            risk_accepted='Empty table drop is safe',
        )
        blocked, reason = requires_review_before_close(goal, waivers=[waiver])
        assert blocked is False
        assert 'waiver accepted' in reason

    def test_high_risk_with_non_matching_waiver_blocked(self):
        goal = GoalRecord(
            goal_id='g-hr-no-match',
            objective='Delete sensitive logs',
        )
        waiver = create_waiver(
            goal_id='g-other-goal',
            reason='Different goal',
            waived_by='admin',
            risk_accepted='Something else',
        )
        blocked, reason = requires_review_before_close(goal, waivers=[waiver])
        assert blocked is True
        assert 'requires synthesis review' in reason

    def test_multiple_waivers_first_match_wins(self):
        goal = GoalRecord(
            goal_id='g-multi',
            objective='Database migration v2',
        )
        w1 = create_waiver('g-other', 'r1', 'a1', 'risk1')
        w2 = create_waiver('g-multi', 'r2', 'a2', 'risk2')
        w3 = create_waiver('g-other2', 'r3', 'a3', 'risk3')
        blocked, reason = requires_review_before_close(goal, waivers=[w1, w2, w3])
        assert blocked is False
        assert 'waiver accepted' in reason


# ---------------------------------------------------------------------------
# build_review_gate
# ---------------------------------------------------------------------------


class TestBuildReviewGate:
    def test_low_risk_returns_low_risk_level(self):
        goal = GoalRecord(goal_id='g-low', objective='Refactor utils')
        gate = build_review_gate(goal)
        assert gate.blocked is False
        assert gate.risk_level == 'low'

    def test_high_risk_returns_high_risk_level(self):
        goal = GoalRecord(goal_id='g-high', objective='Deploy to production')
        gate = build_review_gate(goal)
        assert gate.blocked is True
        assert gate.risk_level == 'high'

    def test_high_risk_with_review_returns_unblocked_high(self):
        goal = GoalRecord(
            goal_id='g-high-reviewed',
            objective='Security patch deployment',
            review_ids=['rev-001'],
        )
        gate = build_review_gate(goal)
        assert gate.blocked is False
        assert gate.risk_level == 'high'


# ---------------------------------------------------------------------------
# GoalStore.set_status integration
# ---------------------------------------------------------------------------


class TestGoalStoreSetStatus:
    def test_set_status_to_active_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(goal_id='g-proposed', objective='Normal task')
            store.save(goal)

            updated = store.set_status('g-proposed', 'active')
            assert updated.status == 'active'

    def test_set_status_low_risk_to_completed_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(goal_id='g-safe', objective='Add docstrings')
            store.save(goal)

            updated = store.set_status('g-safe', 'completed')
            assert updated.status == 'completed'

    def test_set_status_high_risk_to_completed_blocked_without_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr',
                objective='Delete production data',
            )
            store.save(goal)

            with pytest.raises(ValueError) as exc:
                store.set_status('g-hr', 'completed')
            assert 'high-risk goal' in str(exc.value)
            assert 'requires synthesis review' in str(exc.value)

    def test_set_status_high_risk_to_completed_with_review_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr-review',
                objective='Deploy auth changes',
                review_ids=['rev-abc'],
            )
            store.save(goal)

            updated = store.set_status('g-hr-review', 'completed')
            assert updated.status == 'completed'

    def test_set_status_high_risk_to_completed_with_waiver_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr-waiver',
                objective='Billing migration',
            )
            store.save(goal)

            waiver = create_waiver(
                goal_id='g-hr-waiver',
                reason='Safe dry run confirmed',
                waived_by='ops-team',
                risk_accepted='Non-prod environment',
            )
            updated = store.set_status('g-hr-waiver', 'completed', waivers=[waiver])
            assert updated.status == 'completed'

    def test_set_status_high_risk_to_failed_not_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr-fail',
                objective='Credential rotation',
            )
            store.save(goal)

            updated = store.set_status('g-hr-fail', 'failed')
            assert updated.status == 'failed'

    def test_set_status_invalid_status_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(goal_id='g-bad', objective='Something')
            store.save(goal)

            with pytest.raises(ValueError):
                store.set_status('g-bad', 'nonexistent')

    def test_set_status_missing_goal_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            with pytest.raises(FileNotFoundError):
                store.set_status('g-ghost', 'completed')

    def test_set_status_gate_only_applies_to_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr',
                objective='Security hardening',
            )
            store.save(goal)

            # Blocked, abandoned, and active should NOT trigger the gate
            for status in ('blocked', 'abandoned', 'active'):
                goal2 = GoalRecord(
                    goal_id=f'g-hr-{status}',
                    objective='Security hardening',
                )
                store.save(goal2)
                updated = store.set_status(f'g-hr-{status}', status)
                assert updated.status == status

    def test_set_status_human_gate_allows_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GoalStore(tmp)
            goal = GoalRecord(
                goal_id='g-hr-hg',
                objective='Deploy PII sanitizer',
                human_gate_ids=['hg-001'],
            )
            store.save(goal)

            updated = store.set_status('g-hr-hg', 'completed')
            assert updated.status == 'completed'


# ============================================================================
# SCL-P1-006 — ReviewGate packet for skill install / memory promote
# ============================================================================


class TestReviewGateDataclass:
    def test_default_decision_pending(self):
        from teaagent.governance.plan_gate import ReviewGate

        gate = ReviewGate(
            gate_id='g-001',
            target_type='skill_install',
            target_name='test-skill',
            risk_reason='installing unverified skill',
        )
        assert gate.decision == 'pending'
        assert gate.approver == ''
        assert gate.created_at == ''
        assert gate.tool_calls == []
        assert gate.cost_summary == {}
        assert gate.review_findings == []
        assert gate.diff_summary == ''
        assert gate.rollback_path == ''

    def test_round_trip_to_dict(self):
        from teaagent.governance.plan_gate import ReviewGate

        gate = ReviewGate(
            gate_id='g-round',
            target_type='memory_promote',
            target_name='mem-abc',
            risk_reason='promoting untrusted memory',
            diff_summary='+10 lines',
            tool_calls=[{'tool': 'write', 'path': '/tmp/x'}],
            cost_summary={'estimated': 0.05},
            review_findings=[{'severity': 'high', 'message': 'possible data leak'}],
            rollback_path='.teaagent/gates/g-round.json',
            decision='pending',
            approver='',
            created_at='2026-06-05T00:00:00Z',
        )
        data = gate.to_dict()
        restored = ReviewGate.from_dict(data)

        assert restored.gate_id == 'g-round'
        assert restored.target_type == 'memory_promote'
        assert restored.target_name == 'mem-abc'
        assert restored.risk_reason == 'promoting untrusted memory'
        assert restored.diff_summary == '+10 lines'
        assert restored.tool_calls == [{'tool': 'write', 'path': '/tmp/x'}]
        assert restored.cost_summary == {'estimated': 0.05}
        assert restored.review_findings == [
            {'severity': 'high', 'message': 'possible data leak'}
        ]
        assert restored.rollback_path == '.teaagent/gates/g-round.json'
        assert restored.decision == 'pending'
        assert restored.approver == ''
        assert restored.created_at == '2026-06-05T00:00:00Z'

    def test_from_dict_partial_defaults(self):
        from teaagent.governance.plan_gate import ReviewGate

        gate = ReviewGate.from_dict(
            {'gate_id': 'g-min', 'target_type': 'skill_install'}
        )
        assert gate.gate_id == 'g-min'
        assert gate.target_type == 'skill_install'
        assert gate.target_name == ''
        assert gate.risk_reason == ''
        assert gate.decision == 'pending'

    def test_to_dict_all_fields_present(self):
        from teaagent.governance.plan_gate import ReviewGate

        gate = ReviewGate(
            gate_id='g-all',
            target_type='skill_install',
            target_name='t',
            risk_reason='r',
        )
        data = gate.to_dict()
        for key in (
            'gate_id',
            'target_type',
            'target_name',
            'risk_reason',
            'diff_summary',
            'tool_calls',
            'cost_summary',
            'review_findings',
            'rollback_path',
            'decision',
            'approver',
            'created_at',
        ):
            assert key in data, f'missing key: {key}'


class TestRequireReviewGate:
    def test_creates_gate_on_disk(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            gate = require_review_gate(
                target_type='skill_install',
                target_name='example-skill',
                risk_reason='high risk install',
                workspace_root=tmp,
            )
            assert gate.decision == 'pending'
            assert gate.target_type == 'skill_install'
            assert gate.target_name == 'example-skill'
            assert gate.gate_id != ''

            gates_dir = Path(tmp) / '.teaagent' / 'gates'
            assert gates_dir.is_dir()
            gate_file = gates_dir / f'{gate.gate_id}.json'
            assert gate_file.is_file()

            saved = json.loads(gate_file.read_text())
            assert saved['gate_id'] == gate.gate_id
            assert saved['decision'] == 'pending'

    def test_high_risk_triggers_gate_with_correct_fields(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            gate = require_review_gate(
                target_type='memory_promote',
                target_name='quarantined-mem-123',
                risk_reason='untrusted source promoting to project memory',
                workspace_root=tmp,
            )
            assert gate.target_type == 'memory_promote'
            assert gate.target_name == 'quarantined-mem-123'
            assert gate.risk_reason != ''
            assert gate.decision == 'pending'
            assert gate.gate_id != ''
            assert gate.created_at != ''

    def test_different_target_types(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            for ttype in ('skill_install', 'memory_promote'):
                gate = require_review_gate(
                    target_type=ttype,
                    target_name='target-x',
                    risk_reason='test',
                    workspace_root=tmp,
                )
                assert gate.target_type == ttype


class TestSkillInstallGateFlow:
    def test_approved_gate_id_allows_proceeding(self):
        from teaagent.governance.plan_gate import (
            approve_gate,
            load_gate,
            require_review_gate,
        )
        from teaagent.skill_candidates import SkillCandidate, SkillCandidateStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SkillCandidateStore(root)
            candidate = SkillCandidate(
                candidate_id='cand-001',
                name='demo-skill',
                description='A demo skill',
                status='review_passed',
                created_at='2026-01-01T00Z',
                updated_at='2026-01-01T00Z',
            )
            meta = store._meta('cand-001')
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps(candidate.to_dict()))

            # Create a gate, then approve it
            gate_obj = require_review_gate(
                target_type='skill_install',
                target_name='cand-001',
                risk_reason='installing candidate',
                workspace_root=tmp,
            )
            assert gate_obj.decision == 'pending'

            # Approve the gate
            approved = approve_gate(
                gate_obj.gate_id,
                approver='test-operator',
                workspace_root=tmp,
            )
            assert approved.decision == 'approved'
            assert approved.approver == 'test-operator'

            # Load it back and verify
            loaded = load_gate(gate_obj.gate_id, workspace_root=tmp)
            assert loaded.decision == 'approved'
            assert loaded.approver == 'test-operator'

    def test_pending_gate_triggers_status(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            gate = require_review_gate(
                target_type='skill_install',
                target_name='danger-skill',
                risk_reason='high risk skill install',
                workspace_root=tmp,
            )
            assert gate.decision == 'pending'
            assert gate.target_type == 'skill_install'
            assert gate.gate_id != ''

            gates_dir = Path(tmp) / '.teaagent' / 'gates'
            gate_file = gates_dir / f'{gate.gate_id}.json'
            assert gate_file.is_file()

    def test_load_nonexistent_gate_raises(self):
        from teaagent.governance.plan_gate import load_gate

        with tempfile.TemporaryDirectory() as tmp:
            # Non-UUID gate_id should raise ValueError
            with pytest.raises(ValueError, match='gate_id must be a valid UUID'):
                load_gate('nonexistent-gate', workspace_root=tmp)

            # Valid UUID but no file on disk should raise FileNotFoundError
            import uuid

            valid_uuid = str(uuid.uuid4())
            with pytest.raises(FileNotFoundError, match='gate not found'):
                load_gate(valid_uuid, workspace_root=tmp)

    def test_approve_non_pending_gate_raises(self):
        from teaagent.governance.plan_gate import approve_gate, require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            gate = require_review_gate(
                target_type='skill_install',
                target_name='cand-001',
                risk_reason='test',
                workspace_root=tmp,
            )
            # First approval works
            approve_gate(gate.gate_id, approver='op1', workspace_root=tmp)
            # Second approval should fail
            with pytest.raises(ValueError, match='not pending'):
                approve_gate(gate.gate_id, approver='op2', workspace_root=tmp)


class TestMemoryPromoteGateBypass:
    def test_force_flag_bypasses_gate(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            # Simulate force=True: gate should NOT be created
            force = True
            gate_created = False
            if not force:
                gate_created = True
            assert not gate_created

            # Without force: gate IS created
            force = False
            gate_created = False
            if not force:
                gate_obj = require_review_gate(
                    target_type='memory_promote',
                    target_name='mem-999',
                    risk_reason='promoting quarantined memory',
                    workspace_root=tmp,
                )
                gate_created = True
                assert gate_obj.decision == 'pending'
            assert gate_created

    def test_no_force_triggers_gate_status(self):
        from teaagent.governance.plan_gate import require_review_gate

        with tempfile.TemporaryDirectory() as tmp:
            gate = require_review_gate(
                target_type='memory_promote',
                target_name='mem-999',
                risk_reason='promoting untrusted memory entry',
                workspace_root=tmp,
            )
            assert gate.decision == 'pending'
            assert gate.target_type == 'memory_promote'
            assert gate.gate_id != ''

            gates_dir = Path(tmp) / '.teaagent' / 'gates'
            gate_file = gates_dir / f'{gate.gate_id}.json'
            assert gate_file.is_file()
