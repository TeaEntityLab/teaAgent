"""Cost state taxonomy for run receipts and budget displays (WS3-004)."""

from __future__ import annotations

from typing import Literal, cast

CostState = Literal[
    'estimated',
    'provider_reported',
    'pending',
    'unknown',
    'unlimited',
    'unavailable',
]

CANONICAL_COST_STATES: frozenset[str] = frozenset(
    {
        'estimated',
        'provider_reported',
        'pending',
        'unknown',
        'unlimited',
        'unavailable',
    }
)


def derive_cost_state(
    *,
    cost_cents: float = 0.0,
    budget_cap_cents: int | None = None,
    provider_reported: bool = False,
    pending: bool = False,
) -> CostState:
    """Derive the display label for accumulated run cost."""
    if pending:
        return 'pending'
    if budget_cap_cents is None:
        return 'unlimited'
    if provider_reported and cost_cents > 0:
        return 'provider_reported'
    if cost_cents > 0:
        return 'estimated'
    if cost_cents == 0:
        return 'unknown'
    return 'unavailable'


def normalize_cost_state(value: str | None) -> CostState:
    """Map legacy labels (e.g. ``actual``) to canonical taxonomy."""
    if not value:
        return 'unavailable'
    normalized = value.strip().lower()
    if normalized == 'actual':
        return 'provider_reported'
    if normalized in CANONICAL_COST_STATES:
        return cast(CostState, normalized)
    return 'unavailable'
