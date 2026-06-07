"""SCL-P1-005 — Review gate enforcement for high-risk goal completion.

A high-risk goal cannot be closed (transitioned to 'completed') without
either a synthesis review attached (``review_ids``) or a documented
waiver (``WaiverRecord``).  This module provides:

- ``ReviewGate`` — dataclass holding gate decision and reason
- ``WaiverRecord`` — dataclass documenting accepted risk
- ``is_high_risk_goal()`` — heuristic risk classifier
- ``requires_review_before_close()`` — checks review/waiver presence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from teaagent.consensus import RiskLevel

if TYPE_CHECKING:
    from teaagent.goal_record import GoalRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# High-risk keyword patterns derived from policy.py::_is_high_risk_operation
# and teaagent consensus RiskLevel semantics.
# ---------------------------------------------------------------------------

_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    (
        '/prod',
        '/production',
        'database',
        'delete',
        'rm -rf',
        'migration',
        'deploy',
        'deployment',
        'security',
        'auth',
        'authentication',
        'permission',
        'billing',
        'payment',
        'destroy',
        'purge',
        'credential',
        'secret',
        'api key',
        'token',
        'encrypt',
        'decrypt',
        'privilege',
        'admin',
        'root',
        'sudo',
        'drop table',
        'truncate',
        'proxy',
        'pii',
        'gdpr',
        'hipaa',
        'compliance',
        'audit',
        'forensic',
        'legal',
        'financial',
        'medical',
    )
)

_HIGH_RISK_SPEC_PREFIXES: frozenset[str] = frozenset(
    (
        'sec-',
        'auth-',
        'prod-',
        'deploy-',
        'migration-',
        'compliance-',
    )
)


def _matches_high_risk_keywords(text: str) -> bool:
    """Check if *text* contains any high-risk keyword (case-insensitive)."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in _HIGH_RISK_KEYWORDS)


def _spec_id_matches_prefix(spec_id: str) -> bool:
    """Check if *spec_id* matches know high-risk prefixes."""
    lowered = spec_id.lower()
    return any(lowered.startswith(prefix) for prefix in _HIGH_RISK_SPEC_PREFIXES)


# ---------------------------------------------------------------------------
# is_high_risk_goal
# ---------------------------------------------------------------------------


def is_high_risk_goal(goal: GoalRecord) -> bool:
    """Heuristic: classify a goal as high-risk based on objective, tasks, and spec.

    Checks in order:
    1. Objective contains high-risk keywords.
    2. ``spec_id`` matches known high-risk prefixes (sec-, auth-, prod-, etc.).
    3. Any ``task_id`` contains high-risk keywords.

    Returns:
        True if any signal matches.
    """
    # 1. Objective keyword check
    if _matches_high_risk_keywords(goal.objective):
        return True

    # 2. Spec-id prefix check
    if goal.spec_id and _spec_id_matches_prefix(goal.spec_id):
        return True

    # 3. Task-ids keyword check
    return any(_matches_high_risk_keywords(tid) for tid in goal.task_ids)


# ---------------------------------------------------------------------------
# WaiverRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WaiverRecord:
    """Documented acceptance of risk for a high-risk goal without a formal review.

    When a high-risk goal must be closed but a synthesis review is not
    feasible (e.g., time pressure, trivial risk), a waiver records the
    explicit acceptance of that risk.
    """

    waiver_id: str
    goal_id: str
    reason: str
    waived_by: str
    risk_accepted: str  # free-form description of accepted risk
    waived_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            'waiver_id': self.waiver_id,
            'goal_id': self.goal_id,
            'reason': self.reason,
            'waived_by': self.waived_by,
            'risk_accepted': self.risk_accepted,
            'waived_at': self.waived_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> WaiverRecord:
        return cls(
            waiver_id=data.get('waiver_id', ''),
            goal_id=data.get('goal_id', ''),
            reason=data.get('reason', ''),
            waived_by=data.get('waived_by', ''),
            risk_accepted=data.get('risk_accepted', ''),
            waived_at=data.get('waived_at', ''),
        )


def create_waiver(
    goal_id: str,
    reason: str,
    waived_by: str,
    risk_accepted: str,
    *,
    waived_at: str = '',
) -> WaiverRecord:
    """Factory for a new WaiverRecord with auto-generated ID and timestamp."""
    from teaagent.audit import utc_now

    return WaiverRecord(
        waiver_id=str(uuid4()),
        goal_id=goal_id,
        reason=reason,
        waived_by=waived_by,
        risk_accepted=risk_accepted,
        waived_at=waived_at or utc_now(),
    )


# ---------------------------------------------------------------------------
# ReviewGate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewGate:
    """Result of checking whether a goal requires review before close."""

    blocked: bool
    reason: str
    risk_level: str  # RiskLevel value string


def requires_review_before_close(
    goal: GoalRecord,
    *,
    waivers: list[WaiverRecord] | None = None,
) -> tuple[bool, str]:
    """Check if *goal* requires a synthesis review or waiver before closing.

    A goal is blocked from completion when:
    1. It is classified as high-risk (see ``is_high_risk_goal``).
    2. It has no ``review_ids`` and no ``human_gate_ids``.
    3. No valid waiver is provided.

    Parameters
    ----------
    goal:
        The goal being evaluated for close.
    waivers:
        Optional list of waivers to check against this goal.

    Returns
    -------
    (blocked, reason):
        ``blocked`` is True when the goal cannot close yet.
        ``reason`` is a human-readable explanation.
    """
    # Only high-risk goals are gated
    if not is_high_risk_goal(goal):
        return False, 'not a high-risk goal'

    # Already has a review — can close
    if goal.review_ids:
        return False, 'synthesis review already present'

    # Human gate counts as review-equivalent
    if goal.human_gate_ids:
        return False, 'human gate already present'

    # Check for a matching waiver
    waiver_list = waivers or []
    for waiver in waiver_list:
        if waiver.goal_id == goal.goal_id:
            logger.info(
                'Goal %s: waiver accepted (waiver_id=%s, waived_by=%s)',
                goal.goal_id,
                waiver.waiver_id,
                waiver.waived_by,
            )
            return False, 'waiver accepted'

    return True, 'high-risk goal requires synthesis review or documented waiver'


def build_review_gate(
    goal: GoalRecord,
    *,
    waivers: list[WaiverRecord] | None = None,
) -> ReviewGate:
    """Build a ReviewGate result for the given goal.

    Convenience wrapper around ``requires_review_before_close`` that returns
    a structured result instead of a raw tuple.
    """
    blocked, reason = requires_review_before_close(goal, waivers=waivers)
    return ReviewGate(
        blocked=blocked,
        reason=reason,
        risk_level=RiskLevel.HIGH.value
        if is_high_risk_goal(goal)
        else RiskLevel.LOW.value,
    )


# ---------------------------------------------------------------------------
# Waiver persistence helpers
# ---------------------------------------------------------------------------


def serialize_waivers(waivers: list[WaiverRecord]) -> list[dict[str, str]]:
    """Serialize a list of waivers to plain dicts for JSON storage."""
    return [w.to_dict() for w in waivers]


def deserialize_waivers(data: list[dict[str, str]]) -> list[WaiverRecord]:
    """Deserialize a list of waiver dicts back to WaiverRecord objects."""
    return [WaiverRecord.from_dict(d) for d in data]
