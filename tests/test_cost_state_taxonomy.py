"""WS3-004 cost state taxonomy tests."""

from __future__ import annotations

from teaagent.cost_state import (
    CANONICAL_COST_STATES,
    derive_cost_state,
    normalize_cost_state,
)


def test_canonical_states_include_ws3_labels() -> None:
    for label in ('estimated', 'provider_reported', 'pending', 'unknown'):
        assert label in CANONICAL_COST_STATES


def test_derive_cost_state_matrix() -> None:
    assert derive_cost_state(pending=True, budget_cap_cents=100) == 'pending'
    assert derive_cost_state(budget_cap_cents=None) == 'unlimited'
    assert (
        derive_cost_state(cost_cents=10, budget_cap_cents=100, provider_reported=True)
        == 'provider_reported'
    )
    assert derive_cost_state(cost_cents=10, budget_cap_cents=100) == 'estimated'
    assert derive_cost_state(cost_cents=0, budget_cap_cents=100) == 'unknown'


def test_normalize_legacy_actual_label() -> None:
    assert normalize_cost_state('actual') == 'provider_reported'
    assert normalize_cost_state('estimated') == 'estimated'
    assert normalize_cost_state('bogus') == 'unavailable'
