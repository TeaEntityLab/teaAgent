from __future__ import annotations

from teaagent.subagents._synthesis_review import (
    ReviewFinding,
    ReviewFindingState,
    SynthesisReviewArtifact,
    find_repeated_findings,
    suppress_repeated,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    finding_id: str,
    category: str = 'security',
    evidence_path: str = 'src/x.py',
    severity: str = 'high',
    message: str = '',
    state: ReviewFindingState = ReviewFindingState.PROPOSED,
    superseded_by: str | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        state=state,
        severity=severity,
        category=category,
        message=message or f'Finding {finding_id}',
        evidence_path=evidence_path,
        superseded_by=superseded_by,
    )


def _make_review(
    review_id: str = 'sr-1',
    findings: list[ReviewFinding] | None = None,
) -> SynthesisReviewArtifact:
    return SynthesisReviewArtifact(
        review_id=review_id,
        target_run_id='run-1',
        target_goal_id='goal-1',
        reviewer_role='oracle',
        findings=findings or [],
    )


# ---------------------------------------------------------------------------
# find_repeated_findings
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_same_category_and_evidence_is_superseded(self) -> None:
        existing = [
            _make_finding('f-old', category='security', evidence_path='src/x.py')
        ]
        new = [_make_finding('f-new', category='security', evidence_path='src/x.py')]

        result = find_repeated_findings(existing, new)

        assert result == {'f-new': 'superseded'}

    def test_same_category_different_evidence_is_still_active(self) -> None:
        existing = [
            _make_finding('f-old', category='security', evidence_path='src/x.py')
        ]
        new = [_make_finding('f-new', category='security', evidence_path='src/y.py')]

        result = find_repeated_findings(existing, new)

        assert result == {'f-new': 'still_active'}

    def test_same_evidence_different_category_is_still_active(self) -> None:
        existing = [
            _make_finding('f-old', category='security', evidence_path='src/x.py')
        ]
        new = [_make_finding('f-new', category='performance', evidence_path='src/x.py')]

        result = find_repeated_findings(existing, new)

        assert result == {'f-new': 'still_active'}


class TestMultipleFindings:
    def test_multiple_repeats_and_non_repeats(self) -> None:
        existing = [
            _make_finding('e1', category='security', evidence_path='a.py'),
            _make_finding('e2', category='style', evidence_path='b.py'),
            _make_finding('e3', category='functional', evidence_path='c.py'),
        ]
        new = [
            _make_finding(
                'n1', category='security', evidence_path='a.py'
            ),  # repeat of e1
            _make_finding(
                'n2', category='style', evidence_path='z.py'
            ),  # no match (evidence differs)
            _make_finding(
                'n3', category='functional', evidence_path='c.py'
            ),  # repeat of e3
            _make_finding(
                'n4', category='security', evidence_path='d.py'
            ),  # no match (evidence differs)
        ]

        result = find_repeated_findings(existing, new)

        assert result == {
            'n1': 'superseded',
            'n2': 'still_active',
            'n3': 'superseded',
            'n4': 'still_active',
        }

    def test_first_existing_match_wins(self) -> None:
        existing = [
            _make_finding('e1', category='security', evidence_path='x.py'),
            _make_finding('e2', category='security', evidence_path='x.py'),
        ]
        new = [_make_finding('n1', category='security', evidence_path='x.py')]

        result = find_repeated_findings(existing, new)

        assert result == {'n1': 'superseded'}


class TestEdgeCases:
    def test_no_existing_findings_all_still_active(self) -> None:
        existing: list[ReviewFinding] = []
        new = [
            _make_finding('n1', category='security', evidence_path='x.py'),
            _make_finding('n2', category='style', evidence_path='y.py'),
        ]

        result = find_repeated_findings(existing, new)

        assert result == {'n1': 'still_active', 'n2': 'still_active'}

    def test_no_new_findings_empty_result(self) -> None:
        existing = [_make_finding('e1', category='security', evidence_path='x.py')]
        new: list[ReviewFinding] = []

        result = find_repeated_findings(existing, new)

        assert result == {}

    def test_no_findings_at_all(self) -> None:
        result = find_repeated_findings([], [])
        assert result == {}

    def test_no_repeats_when_categories_differ(self) -> None:
        existing = [
            _make_finding('e1', category='security', evidence_path='x.py'),
            _make_finding('e2', category='style', evidence_path='x.py'),
            _make_finding('e3', category='performance', evidence_path='x.py'),
        ]
        new = [_make_finding('n1', category='functional', evidence_path='x.py')]

        result = find_repeated_findings(existing, new)

        assert result == {'n1': 'still_active'}

    def test_empty_category_and_evidence_match(self) -> None:
        existing = [_make_finding('e1', category='', evidence_path='')]
        new = [_make_finding('n1', category='', evidence_path='')]

        result = find_repeated_findings(existing, new)

        assert result == {'n1': 'superseded'}


# ---------------------------------------------------------------------------
# suppress_repeated
# ---------------------------------------------------------------------------


class TestSuppressRepeated:
    def test_returns_review_unchanged(self) -> None:
        new_finding = _make_finding('n1', category='security', evidence_path='x.py')
        review = _make_review('sr-1', findings=[new_finding])

        result = suppress_repeated(review, [])

        assert result is review
        assert result.review_id == 'sr-1'
        assert len(result.findings) == 1

    def test_with_existing_reviews_does_not_mutate(self) -> None:
        existing_finding = _make_finding(
            'e1', category='security', evidence_path='x.py'
        )
        existing_review = _make_review('sr-old', findings=[existing_finding])
        new_finding = _make_finding('n1', category='security', evidence_path='x.py')
        new_review = _make_review('sr-new', findings=[new_finding])

        result = suppress_repeated(new_review, [existing_review])

        assert result.review_id == 'sr-new'
        assert result.findings[0].finding_id == 'n1'
        assert result.findings[0].superseded_by is None
        assert existing_review.findings[0].state == ReviewFindingState.PROPOSED

    def test_multiple_existing_reviews(self) -> None:
        existing1 = _make_review(
            'sr-old1',
            findings=[
                _make_finding('e1', category='security', evidence_path='a.py'),
            ],
        )
        existing2 = _make_review(
            'sr-old2',
            findings=[
                _make_finding('e2', category='style', evidence_path='b.py'),
            ],
        )
        new_review = _make_review(
            'sr-new',
            findings=[
                _make_finding('n1', category='security', evidence_path='a.py'),
                _make_finding('n2', category='style', evidence_path='c.py'),
            ],
        )

        result = suppress_repeated(new_review, [existing1, existing2])

        assert result.review_id == 'sr-new'
        assert len(result.findings) == 2


# ---------------------------------------------------------------------------
# Integration: full repeat suppression workflow
# ---------------------------------------------------------------------------


class TestSuppressionWorkflow:
    def test_mark_existing_as_superseded(self) -> None:
        existing = [
            _make_finding(
                'e1',
                category='security',
                evidence_path='x.py',
                state=ReviewFindingState.VERIFIED,
            ),
        ]
        new = [
            _make_finding('n1', category='security', evidence_path='x.py'),
        ]

        actions = find_repeated_findings(existing, new)
        assert actions == {'n1': 'superseded'}

        superseded_by_id = new[0].finding_id
        updated_existing = ReviewFinding(
            finding_id=existing[0].finding_id,
            state=ReviewFindingState.SUPERSEDED,
            severity=existing[0].severity,
            category=existing[0].category,
            message=existing[0].message,
            evidence_path=existing[0].evidence_path,
            superseded_by=superseded_by_id,
        )
        assert updated_existing.state == ReviewFindingState.SUPERSEDED
        assert updated_existing.superseded_by == 'n1'
        assert updated_existing.finding_id == 'e1'

    def test_verified_to_superseded_transition_valid(self) -> None:
        assert ReviewFindingState.VERIFIED.can_transition_to(
            ReviewFindingState.SUPERSEDED
        )

    def test_superseded_finding_is_terminal(self) -> None:
        for target in ReviewFindingState:
            assert not ReviewFindingState.SUPERSEDED.can_transition_to(target)
