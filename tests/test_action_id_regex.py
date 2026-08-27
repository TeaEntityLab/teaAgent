"""Guard: action-ID regex must match double-digit IDs (G-P2-10 regression).

The original ``[0-9]`` pattern silently failed on ``G-P2-10`` because the
``\b`` word boundary sits between ``1`` and ``0``.  This test pins the fix
(``[0-9]+``) so a future narrowing cannot re-break double-digit IDs.
"""

from __future__ import annotations

from scripts.check_action_register_link import ACTION_ID_PATTERN as _CAP
from scripts.check_review_institution_gate import ACTION_ID_PATTERN as _RIG


def test_action_id_pattern_matches_double_digit_ids() -> None:
    """G-P2-10 and beyond must match — the bug that motivated this test."""
    assert _CAP.search('Action: G-P2-10'), (
        'check_action_register_link must match G-P2-10'
    )
    assert _RIG.search('Action: G-P2-10'), (
        'check_review_institution_gate must match G-P2-10'
    )


def test_action_id_pattern_matches_single_digit_ids() -> None:
    """Single-digit IDs remain matched after the ``[0-9]+`` change."""
    for pat in (_CAP, _RIG):
        assert pat.search('Action: S-P0-1')
        assert pat.search('Action: A-P1-3')
        assert pat.search('Action: U-P2-5')


def test_action_id_pattern_rejects_invalid_prefixes() -> None:
    """Non-action prefixes must not match."""
    for pat in (_CAP, _RIG):
        assert not pat.search('Action: X-P0-1')
        assert not pat.search('Action: S-P3-1')
        assert not pat.search('Action: G-P2-')


def test_action_id_pattern_rejects_bare_numbers() -> None:
    """A bare number without the prefix must not match."""
    for pat in (_CAP, _RIG):
        assert not pat.search('10')
        assert not pat.search('P2-10')
