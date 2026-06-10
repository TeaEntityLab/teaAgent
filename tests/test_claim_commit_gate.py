"""WDB-002 claim-commit gate fixtures."""

from __future__ import annotations

from scripts.validate_claim_commit import validate_claim_commit_message


def test_claim_without_roadmap_trailer_fails() -> None:
    msg = 'Complete Horizon H4 policy wiring'
    errors = validate_claim_commit_message(msg)
    assert errors


def test_claim_with_unchanged_trailer_passes() -> None:
    msg = (
        'Complete Horizon H4 policy wiring\n\n'
        'Roadmap-Status: unchanged\n'
        'Constraint: docs only\n'
        'Tested: unit\n'
        'Confidence: high\n'
    )
    assert not validate_claim_commit_message(msg)


def test_non_claim_message_passes() -> None:
    assert not validate_claim_commit_message('fix: approval prompt wording')
