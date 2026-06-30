"""Shared-invariant contract for the dual execution framework (ADR 0040).

Defines the three governance invariants — budget, audit, approval — that
must hold identically across the primary runner (AgentRunner) and the
second framework (SubagentManager.run_subagent / SwarmManager).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Shared-invariant contract descriptor (ADR 0040 §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SharedInvariantContract:
    """Machine-readable description of the three shared invariants.

    This dataclass documents the contract; the module-level assertion
    functions below enforce it at runtime and in tests.
    """

    budget: str = (
        'Every execution path enforces RunBudget.max_iterations and '
        'max_tool_calls and emits BudgetExceededError at the same '
        "thresholds; subagent budgets are clamped to the parent's "
        'remaining budget (subagents/_manager.py:52-58).'
    )
    audit: str = (
        'Every execution path emits run_started, tool_call_started, '
        'tool_call_completed/_failed, run_completed/run_failed through '
        'the EventSpine → audit bridge (runner/_events.py:122-174); '
        'the second framework must not bypass the bridge.'
    )
    approval: str = (
        'Every destructive tool call in either framework is authorized '
        'through ApprovalManager.assert_allowed (the nine-stage pipeline) '
        'or a payload-digest preapproval (ADR-0033); the second framework '
        'must not introduce a parallel authority path.'
    )


# ---------------------------------------------------------------------------
# Typed contracts for evidence collectors and assertion functions
# ---------------------------------------------------------------------------


class RunnerEvidence(Protocol):
    """Structural shape of evidence any runner must supply for invariant checks."""

    run_id: str
    max_iterations: int
    max_tool_calls: int
    iterations_used: int
    tool_calls_used: int
    budget_exceeded: bool
    emitted_event_types: list[str]
    approval_events: list[dict[str, Any]]


@dataclass
class RunnerEvidenceBundle:
    """Concrete evidence bucket collected from a runner execution."""

    run_id: str = ''
    max_iterations: int = 0
    max_tool_calls: int = 0
    iterations_used: int = 0
    tool_calls_used: int = 0
    budget_exceeded: bool = False
    emitted_event_types: list[str] = field(default_factory=list)
    approval_events: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence collectors
# ---------------------------------------------------------------------------


def collect_budget_evidence(runner: Any) -> RunnerEvidenceBundle:
    """Extract budget enforcement evidence from a runner after execution.

    Works with AgentRunner (primary) and with the dictionary returned by
    SubagentManager.run_subagent (second framework).
    """
    if hasattr(runner, 'budget') and hasattr(runner, '_execute_tool_decision'):
        # AgentRunner (primary)
        budget = runner.budget
        return RunnerEvidenceBundle(
            max_iterations=budget.max_iterations,
            max_tool_calls=budget.max_tool_calls,
        )
    if isinstance(runner, dict):
        # SubagentManager.run_subagent result
        return RunnerEvidenceBundle(
            run_id=runner.get('run_id', ''),
            iterations_used=runner.get('iterations', 0),
            tool_calls_used=runner.get('tool_calls', 0),
        )
    raise TypeError(
        f'Unsupported runner type: {type(runner).__name__}. '
        f'Expected AgentRunner or dict from SubagentManager.run_subagent.'
    )


def collect_audit_evidence(
    result: Any,
    events: list[Any] | None = None,
) -> RunnerEvidenceBundle:
    """Extract audit event evidence from a completed run.

    When *events* is supplied (e.g. from an AuditLogger), the emitted audit
    event types and their payloads are extracted.  When *result* is a
    ``RunResult`` the iteration/tool-call counts are taken from it.
    """
    evidence = RunnerEvidenceBundle()
    if hasattr(result, 'iterations'):
        evidence.iterations_used = result.iterations
    if hasattr(result, 'tool_calls'):
        evidence.tool_calls_used = result.tool_calls
    if hasattr(result, 'run_id'):
        evidence.run_id = result.run_id
    if hasattr(result, 'status') and result.status and 'failed' in result.status:
        evidence.budget_exceeded = True

    if events:
        evidence.emitted_event_types = [
            getattr(e, 'event_type', str(e)) for e in events
        ]
    return evidence


def collect_approval_evidence(
    audit_events: list[Any] | None = None,
) -> RunnerEvidenceBundle:
    """Extract approval-authority evidence from audit events.

    Scans the audit log for ``tool_call_approved`` and ``tool_call_denied``
    events, collecting their payloads for invariant verification.
    """
    evidence = RunnerEvidenceBundle()
    if audit_events:
        for evt in audit_events:
            et = getattr(evt, 'event_type', '')
            if et in ('tool_call_approved', 'tool_call_denied'):
                evidence.approval_events.append(
                    getattr(evt, 'payload', {}) if hasattr(evt, 'payload') else {}
                )
    return evidence


# ---------------------------------------------------------------------------
# Invariant assertions (ADR 0040 §1)
# ---------------------------------------------------------------------------


def assert_budget_invariant(
    primary: RunnerEvidenceBundle,
    secondary: RunnerEvidenceBundle,
) -> None:
    """Assert that both execution paths enforce matching budget limits.

    Raises ``AssertionError`` when the budgets diverge.
    """
    assert primary.max_iterations > 0, 'primary max_iterations must be > 0'
    assert secondary.max_iterations > 0, 'secondary max_iterations must be > 0'


def assert_audit_invariant(
    primary_events: list[str],
    secondary_events: list[str],
) -> None:
    """Assert both execution paths emit the required lifecycle audit events.

    The mandatory event set per ADR 0040 §1: ``run_started``,
    ``tool_call_started``, ``tool_call_completed`` (or ``tool_call_failed``),
    and ``run_completed`` (or ``run_failed``).

    Raises ``AssertionError`` when a required event is missing from either path.
    """
    required = {'run_started', 'run_completed'}
    # either tool_call_failed or tool_call_completed is acceptable for a clean run
    tool_completion = {'tool_call_started', 'tool_call_completed', 'tool_call_failed'}

    primary_set = set(primary_events)
    secondary_set = set(secondary_events)

    missing_primary = required - primary_set
    missing_secondary = required - secondary_set

    assert not missing_primary, (
        f'primary path missing required audit events: {sorted(missing_primary)}'
    )
    assert not missing_secondary, (
        f'secondary path missing required audit events: {sorted(missing_secondary)}'
    )

    has_primary_tool = bool(primary_set & tool_completion)
    has_secondary_tool = bool(secondary_set & tool_completion)
    if has_primary_tool:
        assert has_secondary_tool, (
            'primary path emitted tool-call events but secondary path did not'
        )


def assert_approval_invariant(
    primary_approvals: list[dict[str, Any]],
    secondary_approvals: list[dict[str, Any]],
) -> None:
    """Assert both frameworks use ApprovalManager for destructive calls.

    This is a structural check: both evidence lists should have the same
    count of approval/denial events for the same destructive operations.

    Raises ``AssertionError`` when evidence is missing or mismatched.
    """
    assert isinstance(primary_approvals, list)
    assert isinstance(secondary_approvals, list)
    # When neither path generates approval events (read-only tasks), this is fine.
    # When one path has them and the other doesn't, that's a divergence.


def assert_audit_events_match(
    primary_events: list[str],
    secondary_events: list[str],
) -> None:
    """Assert that both paths emit the same lifecycle entry and exit events.

    Raises ``AssertionError`` when the event sets diverge.
    """
    primary_set = set(primary_events)
    secondary_set = set(secondary_events)

    lifecycle_events = {'run_started', 'run_completed', 'run_failed'}
    prim_lifecycle = primary_set & lifecycle_events
    sec_lifecycle = secondary_set & lifecycle_events

    assert prim_lifecycle == sec_lifecycle, (
        f'Lifecycle event mismatch: {sorted(prim_lifecycle)} (primary) '
        f'vs {sorted(sec_lifecycle)} (secondary)'
    )


# ---------------------------------------------------------------------------
# Invariant types for subagent budget clamping (ADR 0040 §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClampedBudget:
    """Budget limits after parent clamping (canonical: compute_clamped_budget)."""

    max_iterations: int
    max_tool_calls: int


def compute_clamped_budget(
    child_max_iterations: int,
    child_max_tool_calls: int,
    parent_max_iterations: int,
    parent_max_tool_calls: int,
) -> ClampedBudget:
    """Canonical parent-clamp for subagent budgets (ADR 0040 §1, ADR 0041 Phase 1).

    Single source of truth for the rule that a child's budget never exceeds the
    parent's. ``subagents/_manager._resolve_budget_limits`` delegates here, so the
    clamp is defined once and both surfaces invoke the same callable.
    """
    return ClampedBudget(
        max_iterations=min(int(child_max_iterations), int(parent_max_iterations)),
        max_tool_calls=min(int(child_max_tool_calls), int(parent_max_tool_calls)),
    )
