from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from teaagent.subagents._synthesis_review import (
    VALID_FINDING_STATES,
    ResidualRisk,
    ReviewFinding,
    ReviewFindingState,
    SynthesisReviewArtifact,
    _validate_evidence_path,
    build_synthesis_review,
    close_synthesis_review,
    record_review_closed,
    record_review_finding_proposed,
    record_review_finding_verified,
)

# ---------------------------------------------------------------------------
# ReviewFindingState
# ---------------------------------------------------------------------------


class TestReviewFindingStateEnum:
    def test_all_states_present(self) -> None:
        expected = {
            'proposed',
            'verified',
            'rejected',
            'false_positive',
            'needs_human',
            'fixed',
            'superseded',
        }
        assert set(s.value for s in ReviewFindingState) == expected

    def test_string_coercion(self) -> None:
        assert str(ReviewFindingState.PROPOSED) == 'proposed'
        assert str(ReviewFindingState.VERIFIED) == 'verified'

    def test_membership_in_valid_states(self) -> None:
        for state in ReviewFindingState:
            assert state.value in VALID_FINDING_STATES


class TestReviewFindingStateTransitions:
    def test_proposed_to_verified(self) -> None:
        assert ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.VERIFIED
        )

    def test_proposed_to_rejected(self) -> None:
        assert ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.REJECTED
        )

    def test_proposed_to_false_positive(self) -> None:
        assert ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.FALSE_POSITIVE
        )

    def test_proposed_to_needs_human(self) -> None:
        assert ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.NEEDS_HUMAN
        )

    def test_proposed_cannot_go_to_fixed(self) -> None:
        assert not ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.FIXED
        )

    def test_proposed_cannot_go_to_superseded(self) -> None:
        assert not ReviewFindingState.PROPOSED.can_transition_to(
            ReviewFindingState.SUPERSEDED
        )

    def test_verified_to_superseded(self) -> None:
        assert ReviewFindingState.VERIFIED.can_transition_to(
            ReviewFindingState.SUPERSEDED
        )

    def test_verified_to_fixed(self) -> None:
        assert ReviewFindingState.VERIFIED.can_transition_to(
            ReviewFindingState.FIXED
        )

    def test_verified_cannot_go_to_proposed(self) -> None:
        assert not ReviewFindingState.VERIFIED.can_transition_to(
            ReviewFindingState.PROPOSED
        )

    def test_rejected_back_to_proposed(self) -> None:
        assert ReviewFindingState.REJECTED.can_transition_to(
            ReviewFindingState.PROPOSED
        )

    def test_false_positive_back_to_proposed(self) -> None:
        assert ReviewFindingState.FALSE_POSITIVE.can_transition_to(
            ReviewFindingState.PROPOSED
        )

    def test_needs_human_can_go_to_verified(self) -> None:
        assert ReviewFindingState.NEEDS_HUMAN.can_transition_to(
            ReviewFindingState.VERIFIED
        )

    def test_needs_human_can_go_to_fixed(self) -> None:
        assert ReviewFindingState.NEEDS_HUMAN.can_transition_to(
            ReviewFindingState.FIXED
        )

    def test_superseded_is_terminal(self) -> None:
        for target in ReviewFindingState:
            assert not ReviewFindingState.SUPERSEDED.can_transition_to(target)


# ---------------------------------------------------------------------------
# ReviewFinding
# ---------------------------------------------------------------------------


class TestReviewFinding:
    def test_construction_minimal(self) -> None:
        f = ReviewFinding(
            finding_id='f-001',
            state=ReviewFindingState.PROPOSED,
            severity='high',
            category='security',
            message='Hardcoded secret detected',
            evidence_path='src/config.py',
        )
        assert f.finding_id == 'f-001'
        assert f.state == ReviewFindingState.PROPOSED
        assert f.severity == 'high'
        assert f.category == 'security'
        assert f.message == 'Hardcoded secret detected'
        assert f.evidence_path == 'src/config.py'
        assert f.superseded_by is None

    def test_construction_with_superseded_by(self) -> None:
        f = ReviewFinding(
            finding_id='f-002',
            state=ReviewFindingState.SUPERSEDED,
            severity='medium',
            category='functional',
            message='Obsolete check',
            evidence_path='src/main.py',
            superseded_by='f-003',
        )
        assert f.superseded_by == 'f-003'

    def test_to_dict(self) -> None:
        f = ReviewFinding(
            finding_id='f-001',
            state=ReviewFindingState.PROPOSED,
            severity='high',
            category='security',
            message='XSS vector',
            evidence_path='src/ui.py',
        )
        d = f.to_dict()
        assert d['finding_id'] == 'f-001'
        assert d['state'] == 'proposed'
        assert d['severity'] == 'high'
        assert d['category'] == 'security'
        assert d['message'] == 'XSS vector'
        assert d['evidence_path'] == 'src/ui.py'
        assert 'superseded_by' not in d

    def test_to_dict_with_superseded_by(self) -> None:
        f = ReviewFinding(
            finding_id='f-002',
            state=ReviewFindingState.SUPERSEDED,
            severity='low',
            category='style',
            message='Naming',
            evidence_path='src/util.py',
            superseded_by='f-003',
        )
        d = f.to_dict()
        assert d['superseded_by'] == 'f-003'

    def test_from_dict_minimal(self) -> None:
        d = {
            'finding_id': 'f-001',
            'state': 'proposed',
            'severity': 'medium',
            'category': 'performance',
            'message': 'N+1 query',
            'evidence_path': 'db.py:42',
        }
        f = ReviewFinding.from_dict(d)
        assert f.finding_id == 'f-001'
        assert f.state == ReviewFindingState.PROPOSED
        assert f.message == 'N+1 query'

    def test_from_dict_with_superseded_by(self) -> None:
        d = {
            'finding_id': 'f-002',
            'state': 'superseded',
            'severity': 'low',
            'category': 'style',
            'message': 'Old',
            'evidence_path': 'x.py',
            'superseded_by': 'f-003',
        }
        f = ReviewFinding.from_dict(d)
        assert f.superseded_by == 'f-003'

    def test_from_dict_invalid_state_raises(self) -> None:
        d = {'finding_id': 'f', 'state': 'bogus', 'severity': 'low',
             'category': 'style', 'message': 'm', 'evidence_path': 'x'}
        with pytest.raises(ValueError, match='Invalid finding state'):
            ReviewFinding.from_dict(d)

    def test_from_dict_missing_state_defaults_to_proposed(self) -> None:
        d = {'finding_id': 'f', 'severity': 'low', 'category': 'style',
             'message': 'm', 'evidence_path': 'x'}
        f = ReviewFinding.from_dict(d)
        assert f.state == ReviewFindingState.PROPOSED

    def test_serialization_roundtrip(self) -> None:
        f = ReviewFinding(
            finding_id='f-001',
            state=ReviewFindingState.PROPOSED,
            severity='critical',
            category='security',
            message='SQL injection',
            evidence_path='src/api.py',
            superseded_by='f-999',
        )
        d = f.to_dict()
        raw = json.dumps(d, sort_keys=True)
        loaded = json.loads(raw)
        f2 = ReviewFinding.from_dict(loaded)
        assert f2.finding_id == f.finding_id
        assert f2.state == f.state
        assert f2.severity == f.severity
        assert f2.category == f.category
        assert f2.message == f.message
        assert f2.evidence_path == f.evidence_path
        assert f2.superseded_by == f.superseded_by


# ---------------------------------------------------------------------------
# ResidualRisk
# ---------------------------------------------------------------------------


class TestResidualRisk:
    def test_construction(self) -> None:
        r = ResidualRisk(
            description='No test coverage for legacy module',
            severity='medium',
            mitigation='Manual QA gate before release',
            accepted=True,
        )
        assert r.description == 'No test coverage for legacy module'
        assert r.severity == 'medium'
        assert r.mitigation == 'Manual QA gate before release'
        assert r.accepted is True

    def test_default_not_accepted(self) -> None:
        r = ResidualRisk(
            description='Risk',
            severity='low',
            mitigation='None',
        )
        assert r.accepted is False

    def test_to_dict(self) -> None:
        r = ResidualRisk(
            description='d', severity='high', mitigation='m', accepted=True
        )
        d = r.to_dict()
        assert d == {'description': 'd', 'severity': 'high',
                     'mitigation': 'm', 'accepted': True}

    def test_from_dict(self) -> None:
        d = {'description': 'd', 'severity': 'medium', 'mitigation': 'm',
             'accepted': False}
        r = ResidualRisk.from_dict(d)
        assert r.description == 'd'
        assert r.severity == 'medium'
        assert r.mitigation == 'm'
        assert r.accepted is False

    def test_serialization_roundtrip(self) -> None:
        r = ResidualRisk(description='X', severity='high', mitigation='Y',
                         accepted=True)
        raw = json.dumps(r.to_dict(), sort_keys=True)
        loaded = json.loads(raw)
        r2 = ResidualRisk.from_dict(loaded)
        assert r2 == r


# ---------------------------------------------------------------------------
# SynthesisReviewArtifact
# ---------------------------------------------------------------------------


class TestSynthesisReviewArtifact:
    def test_construction_minimal(self) -> None:
        s = SynthesisReviewArtifact(
            review_id='sr-001',
            target_run_id='run-1',
            target_goal_id='goal-1',
            reviewer_role='oracle',
        )
        assert s.review_id == 'sr-001'
        assert s.target_run_id == 'run-1'
        assert s.target_goal_id == 'goal-1'
        assert s.reviewer_role == 'oracle'
        assert s.recommended_gate_state == 'request_changes'
        assert s.findings == []
        assert s.residual_risk == []

    def test_construction_full(self) -> None:
        findings = [
            ReviewFinding(
                finding_id='f-001', state=ReviewFindingState.PROPOSED,
                severity='high', category='security',
                message='Issue', evidence_path='src/x.py',
            ),
        ]
        risks = [
            ResidualRisk(description='R', severity='low',
                         mitigation='M', accepted=True),
        ]
        s = SynthesisReviewArtifact(
            review_id='sr-001',
            target_run_id='run-1',
            target_goal_id='goal-1',
            reviewer_role='human',
            model_route_id='route-1',
            files_reviewed=['a.py', 'b.py'],
            commands_reviewed=['pytest'],
            tests_reviewed=['test_a.py'],
            findings=findings,
            residual_risk=risks,
            recommended_gate_state='approve',
        )
        assert len(s.findings) == 1
        assert len(s.residual_risk) == 1
        assert s.recommended_gate_state == 'approve'
        assert s.files_reviewed == ['a.py', 'b.py']
        assert s.commands_reviewed == ['pytest']
        assert s.tests_reviewed == ['test_a.py']

    def test_invalid_gate_state_raises(self) -> None:
        with pytest.raises(ValueError, match='Invalid gate state'):
            SynthesisReviewArtifact(
                review_id='sr',
                target_run_id='r',
                target_goal_id='g',
                reviewer_role='subagent',
                recommended_gate_state='bogus',
            )

    def test_to_dict(self) -> None:
        s = SynthesisReviewArtifact(
            review_id='sr-001',
            target_run_id='run-1',
            target_goal_id='goal-1',
            reviewer_role='subagent',
            files_reviewed=['f.py'],
            findings=[
                ReviewFinding(
                    finding_id='f1', state=ReviewFindingState.VERIFIED,
                    severity='medium', category='functional',
                    message='msg', evidence_path='f.py',
                ),
            ],
            residual_risk=[
                ResidualRisk(description='r', severity='low',
                             mitigation='m', accepted=False),
            ],
            recommended_gate_state='reject',
        )
        d = s.to_dict()
        assert d['review_id'] == 'sr-001'
        assert d['recommended_gate_state'] == 'reject'
        assert len(d['findings']) == 1
        assert len(d['residual_risk']) == 1
        assert d['findings'][0]['state'] == 'verified'

    def test_from_dict(self) -> None:
        d = {
            'review_id': 'sr-002',
            'target_run_id': 'run-2',
            'target_goal_id': 'goal-2',
            'reviewer_role': 'oracle',
            'model_route_id': 'r-1',
            'files_reviewed': ['x.py'],
            'commands_reviewed': ['cmd'],
            'tests_reviewed': ['test_x.py'],
            'findings': [
                {
                    'finding_id': 'f1',
                    'state': 'proposed',
                    'severity': 'critical',
                    'category': 'security',
                    'message': 'SQLi',
                    'evidence_path': 'db.py',
                },
            ],
            'residual_risk': [
                {
                    'description': 'risk',
                    'severity': 'high',
                    'mitigation': 'mit',
                    'accepted': True,
                },
            ],
            'recommended_gate_state': 'request_changes',
            'created_at': '2025-01-01T00:00:00',
        }
        s = SynthesisReviewArtifact.from_dict(d)
        assert s.review_id == 'sr-002'
        assert s.reviewer_role == 'oracle'
        assert s.model_route_id == 'r-1'
        assert len(s.findings) == 1
        assert s.findings[0].finding_id == 'f1'
        assert s.findings[0].state == ReviewFindingState.PROPOSED
        assert len(s.residual_risk) == 1
        assert s.residual_risk[0].accepted is True

    def test_serialization_roundtrip(self) -> None:
        s = SynthesisReviewArtifact(
            review_id='sr-001',
            target_run_id='run-1',
            target_goal_id='goal-1',
            reviewer_role='human',
            model_route_id='route-1',
            files_reviewed=['a.py'],
            commands_reviewed=['pytest'],
            tests_reviewed=['test_a.py'],
            findings=[
                ReviewFinding(
                    finding_id='f1', state=ReviewFindingState.PROPOSED,
                    severity='critical', category='security',
                    message='vuln', evidence_path='a.py',
                ),
            ],
            residual_risk=[
                ResidualRisk(
                    description='uncovered', severity='medium',
                    mitigation='manual QA', accepted=True,
                ),
            ],
            recommended_gate_state='approve',
        )
        raw = json.dumps(s.to_dict(), sort_keys=True)
        loaded = json.loads(raw)
        s2 = SynthesisReviewArtifact.from_dict(loaded)
        assert s2.review_id == s.review_id
        assert s2.recommended_gate_state == s.recommended_gate_state
        assert len(s2.findings) == len(s.findings)
        assert s2.findings[0].evidence_path == 'a.py'
        assert len(s2.residual_risk) == len(s.residual_risk)

    def test_roundtrip_asdict_compatible(self) -> None:
        import dataclasses

        s = SynthesisReviewArtifact(
            review_id='sr',
            target_run_id='r',
            target_goal_id='g',
            reviewer_role='subagent',
            files_reviewed=['f.py'],
            findings=[
                ReviewFinding(
                    finding_id='f1', state=ReviewFindingState.PROPOSED,
                    severity='low', category='style',
                    message='msg', evidence_path='f.py',
                ),
            ],
        )
        d1 = s.to_dict()
        d2 = dataclasses.asdict(s)
        d2['findings'] = [
            {
                **f,
                'state': f['state'].value if hasattr(f['state'], 'value') else f['state'],
            }
            for f in d2['findings']
        ]
        d2['residual_risk'] = [
            {k: v for k, v in r.items()} for r in d2['residual_risk']
        ]
        assert d1['review_id'] == d2['review_id']
        assert d1['recommended_gate_state'] == d2['recommended_gate_state']


# ---------------------------------------------------------------------------
# build_synthesis_review
# ---------------------------------------------------------------------------


class TestBuildSynthesisReview:
    def test_build_minimal(self) -> None:
        artifact = build_synthesis_review(
            target_run_id='run-1',
            target_goal_id='goal-1',
        )
        assert artifact.review_id
        assert artifact.target_run_id == 'run-1'
        assert artifact.target_goal_id == 'goal-1'
        assert artifact.reviewer_role == 'subagent'
        assert artifact.findings == []

    def test_build_from_subagent_review(self) -> None:
        subagent_review = {
            'review_id': 'rev-1',
            'parent_run_id': 'parent-1',
            'child_run_id': 'child-1',
            'created_at': '2025-01-01T00:00:00',
            'isolation': 'worktree',
            'patch_path': 'p.patch',
            'status_path': 's.status',
            'changed_files': ['README.md', 'src/main.py'],
        }
        artifact = build_synthesis_review(
            subagent_review=subagent_review,
            target_goal_id='goal-1',
        )
        assert artifact.review_id.startswith('rev-1')
        assert artifact.target_run_id == 'child-1'
        assert artifact.files_reviewed == ['README.md', 'src/main.py']

    def test_build_with_supplemental_findings(self) -> None:
        finding = ReviewFinding(
            finding_id='f-001', state=ReviewFindingState.PROPOSED,
            severity='high', category='security',
            message='Hardcoded secret', evidence_path='config.py',
        )
        artifact = build_synthesis_review(
            target_run_id='run-1',
            target_goal_id='goal-1',
            supplemental_findings=[finding],
            files_reviewed=['config.py'],
            residual_risk=[
                ResidualRisk(description='r', severity='low',
                             mitigation='m', accepted=False),
            ],
            recommended_gate_state='reject',
        )
        assert len(artifact.findings) == 1
        assert artifact.findings[0].finding_id == 'f-001'
        assert len(artifact.residual_risk) == 1
        assert artifact.recommended_gate_state == 'reject'

    def test_build_explicit_files_override_subagent(self) -> None:
        subagent_review = {
            'review_id': 'rev-1',
            'parent_run_id': 'p',
            'child_run_id': 'c',
            'created_at': '2025-01-01T00:00:00',
            'isolation': 'worktree',
            'patch_path': 'p.patch',
            'status_path': 's.status',
            'changed_files': ['old.py'],
        }
        artifact = build_synthesis_review(
            subagent_review=subagent_review,
            files_reviewed=['new.py', 'other.py'],
        )
        assert artifact.files_reviewed == ['new.py', 'other.py']


# ---------------------------------------------------------------------------
# close_synthesis_review — evidence validation
# ---------------------------------------------------------------------------


class TestCloseSynthesisReview:
    def test_clean_review_no_errors(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'main.py').write_text('code')

            finding = ReviewFinding(
                finding_id='f1', state=ReviewFindingState.VERIFIED,
                severity='medium', category='functional',
                message='ok', evidence_path='src/main.py',
            )
            review = SynthesisReviewArtifact(
                review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
                reviewer_role='oracle', findings=[finding],
                recommended_gate_state='approve',
            )
            errors = close_synthesis_review(review, workspace_root=root)
            assert errors == []

    def test_missing_evidence_path(self) -> None:
        finding = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='high', category='security',
            message='no evidence', evidence_path='',
        )
        review = SynthesisReviewArtifact(
            review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
            reviewer_role='subagent', findings=[finding],
        )
        errors = close_synthesis_review(review)
        assert len(errors) == 1
        assert 'no evidence_path' in errors[0]

    def test_unresolvable_evidence_path(self) -> None:
        finding = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='high', category='security',
            message='bad path', evidence_path='nonexistent/file.txt',
        )
        review = SynthesisReviewArtifact(
            review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
            reviewer_role='subagent', findings=[finding],
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            errors = close_synthesis_review(review, workspace_root=root)
            assert len(errors) == 1
            assert 'cannot be resolved' in errors[0]

    def test_audit_event_id_is_valid_format(self) -> None:
        finding = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='medium', category='functional',
            message='audit ref', evidence_path='run-abc:42',
        )
        review = SynthesisReviewArtifact(
            review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
            reviewer_role='subagent', findings=[finding],
        )
        errors = close_synthesis_review(review)
        assert errors == []

    def test_artifact_path_under_teaagent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / '.teaagent' / 'subagent-reviews'
            artifact_dir.mkdir(parents=True)
            evidence_file = artifact_dir / 'evidence.json'
            evidence_file.write_text('{}')

            finding = ReviewFinding(
                finding_id='f1', state=ReviewFindingState.PROPOSED,
                severity='medium', category='functional',
                message='artifact ref',
                evidence_path='.teaagent/subagent-reviews/evidence.json',
            )
            review = SynthesisReviewArtifact(
                review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
                reviewer_role='subagent', findings=[finding],
            )
            errors = close_synthesis_review(review, workspace_root=root)
            assert errors == []

    def test_invalid_gate_state_caught(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'x.py').write_text('code')

            finding = ReviewFinding(
                finding_id='f1', state=ReviewFindingState.PROPOSED,
                severity='low', category='style',
                message='ok', evidence_path='x.py',
            )
            review = SynthesisReviewArtifact(
                review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
                reviewer_role='subagent', findings=[finding],
                recommended_gate_state='approve',
            )
            review.recommended_gate_state = 'bogus'
            errors = close_synthesis_review(review, workspace_root=root)
            assert any('gate_state' in e for e in errors)

    def test_multiple_errors_aggregated(self) -> None:
        f1 = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='high', category='security',
            message='no path', evidence_path='',
        )
        f2 = ReviewFinding(
            finding_id='f2', state=ReviewFindingState.PROPOSED,
            severity='medium', category='functional',
            message='bad path', evidence_path='no/such/file',
        )
        review = SynthesisReviewArtifact(
            review_id='sr-1', target_run_id='run-1', target_goal_id='g1',
            reviewer_role='subagent', findings=[f1, f2],
        )
        errors = close_synthesis_review(review)
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# _validate_evidence_path edge cases
# ---------------------------------------------------------------------------


class TestValidateEvidencePath:
    def test_empty_string_fails(self) -> None:
        assert not _validate_evidence_path('', Path('.'))

    def test_whitespace_only_fails(self) -> None:
        assert not _validate_evidence_path('   ', Path('.'))

    def test_audit_event_format_without_colon_fails(self) -> None:
        # Must be run_id:event_index format
        assert not _validate_evidence_path('run_abc_42', Path('.'))

    def test_nonexistent_path_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert not _validate_evidence_path('no/such/path.py', root)

    def test_existing_file_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'real.py').write_text('')
            assert _validate_evidence_path('real.py', root)


# ---------------------------------------------------------------------------
# Audit event helpers
# ---------------------------------------------------------------------------


class TestAuditEventHelpers:
    def test_record_review_finding_proposed(self) -> None:
        mock = MagicMock()
        finding = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='high', category='security',
            message='vuln', evidence_path='x.py',
        )
        record_review_finding_proposed(mock, 'run-1', finding)
        mock.record.assert_called_once()
        call_kwargs = mock.record.call_args.kwargs
        assert call_kwargs['finding_id'] == 'f1'
        assert call_kwargs['severity'] == 'high'
        assert mock.record.call_args.args[0] == 'review_finding_proposed'

    def test_record_review_finding_verified(self) -> None:
        mock = MagicMock()
        finding = ReviewFinding(
            finding_id='f2', state=ReviewFindingState.VERIFIED,
            severity='medium', category='functional',
            message='checked', evidence_path='y.py',
        )
        record_review_finding_verified(mock, 'run-1', finding)
        mock.record.assert_called_once()
        call_kwargs = mock.record.call_args.kwargs
        assert call_kwargs['state'] == 'verified'
        assert mock.record.call_args.args[0] == 'review_finding_verified'

    def test_record_review_closed(self) -> None:
        mock = MagicMock()
        review = SynthesisReviewArtifact(
            review_id='sr-1', target_run_id='r-1', target_goal_id='g-1',
            reviewer_role='oracle', recommended_gate_state='approve',
            findings=[
                ReviewFinding(
                    finding_id='f1', state=ReviewFindingState.VERIFIED,
                    severity='low', category='style',
                    message='m', evidence_path='z.py',
                ),
            ],
            residual_risk=[
                ResidualRisk(description='r', severity='medium',
                             mitigation='mit', accepted=True),
            ],
        )
        record_review_closed(mock, 'run-1', review, error_count=0)
        mock.record.assert_called_once()
        call_kwargs = mock.record.call_args.kwargs
        assert call_kwargs['review_id'] == 'sr-1'
        assert call_kwargs['finding_count'] == 1
        assert call_kwargs['residual_risk_count'] == 1
        assert call_kwargs['recommended_gate_state'] == 'approve'
        assert call_kwargs['error_count'] == 0
        assert mock.record.call_args.args[0] == 'review_closed'


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_review_finding_is_frozen(self) -> None:
        import dataclasses

        f = ReviewFinding(
            finding_id='f1', state=ReviewFindingState.PROPOSED,
            severity='low', category='style', message='m', evidence_path='x',
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.finding_id = 'new'  # type: ignore[misc]

    def test_residual_risk_is_frozen(self) -> None:
        import dataclasses

        r = ResidualRisk(description='d', severity='low', mitigation='m')
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.description = 'new'  # type: ignore[misc]
