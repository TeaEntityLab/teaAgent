"""WDC-002 acceptance: three-concept onboarding happy path."""

from __future__ import annotations

from teaagent.governance.conversation_ux import (
    CORE_ONBOARDING_CONCEPTS,
    stranger_concept_count,
)


def test_three_concept_onboarding_happy_path() -> None:
    assert CORE_ONBOARDING_CONCEPTS == ('ask', 'approve', 'undo')
    assert stranger_concept_count(include_advanced=False) == 3
