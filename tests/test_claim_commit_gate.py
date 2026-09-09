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


def test_claim_with_updated_trailer_naming_change_passes() -> None:
    """A commit that really edits the roadmap can declare that truthfully.

    Before 2026-09-09 the only accepted token was ``unchanged``, so a commit
    that restated horizon rows had to assert something false to pass the gate.
    """
    msg = (
        'Complete Horizon H4 policy wiring\n\n'
        'Roadmap-Status: updated G3/G4 restated from Complete to Partial\n'
    )
    assert not validate_claim_commit_message(msg)


def test_claim_with_bare_updated_trailer_still_fails() -> None:
    """``updated`` must name what changed, otherwise it is a content-free escape."""
    msg = 'Complete Horizon H4 policy wiring\n\nRoadmap-Status: updated\n'
    assert validate_claim_commit_message(msg)
