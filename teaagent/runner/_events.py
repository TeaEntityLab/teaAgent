"""Run-lifecycle event spine and taxonomy.

This module implements the unified event backbone for the TeaAgent runner,
as defined in ADR 0032. Every governance decision and audit fact is derived
from the typed RunEvent stream.

Event types cover the full run lifecycle:
- RUN_STARTED, ITERATION_STARTED, TOOL_CALL_REQUESTED, TOOL_CALL_COMPLETED,
  TOOL_CALL_FAILED, RUN_COMPLETED, RUN_FAILED (M0 spike set)
- Plus planned events: PLAN_RESOLVED, DECISION_RECEIVED, TOOL_CALL_APPROVED,
  TOOL_CALL_DENIED, CONTEXT_COMPACTED, BUDGET_CHECKPOINT, ITERATION_COMPLETED,
  FINAL_VALIDATION, RUN_PENDING_APPROVAL, RUN_CANCELLED, RECEIPT_EMITTED,
  SESSION_START, SESSION_END, SKILL_LOAD, MODEL_ROUTE, GIT_SANDBOX_STARTED,
  GIT_SANDBOX_RESOLVED, UNDO_PERFORMED, PRE_TOOL_USE, POST_TOOL_USE, PRE_COMPACT
  (extended in M1+; see ADR 0032 for the full taxonomy).

The EventSpine is sync-first, in-process, and deterministic: no threads, no queues.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from teaagent.audit import AuditLogger

logger = logging.getLogger(__name__)


class RunEventType(str, Enum):
    """Typed enumeration of run-lifecycle events.

    Each event type carries a specific payload structure; see RunEvent and ADR 0032.
    """

    # M0 set (5-minute-proof scenario)
    RUN_STARTED = 'run_started'
    ITERATION_STARTED = 'iteration_started'
    TOOL_CALL_REQUESTED = 'tool_call_requested'
    TOOL_CALL_COMPLETED = 'tool_call_completed'
    TOOL_CALL_FAILED = 'tool_call_failed'
    RUN_COMPLETED = 'run_completed'
    RUN_FAILED = 'run_failed'

    # M2 evidence-event taxonomy (ADR 0032 §16): the event types the evidence
    # bundle reads, so the reader can surface them from the audit JSONL.
    # Mapping/reader only — emit-site migration is deferred (see §16).
    MODEL_ROUTE = 'model_route'
    GIT_SANDBOX_STARTED = 'git_sandbox_started'
    GIT_SANDBOX_RESOLVED = 'git_sandbox_resolved'
    SKILL_ACTIVATED = 'skill_activated'
    SKILL_LIFECYCLE_TRANSITION = 'skill_lifecycle_transition'
    TEST_RUN = 'test_run'
    UNDO_APPLIED = 'undo_applied'
    PROVENANCE_COLLECTED = 'provenance_collected'
    TOOL_CALL_STARTED = 'tool_call_started'
    TOOL_USE = 'tool_use'
    TOOL_CALL_APPROVED = 'tool_call_approved'
    TOOL_CALL_DENIED = 'tool_call_denied'
    TOOL_CALL_PENDING_APPROVAL = 'tool_call_pending_approval'
    TOOL_ERROR = 'tool_error'
    APPROVAL_REQUESTED = 'approval_requested'
    APPROVAL_GRANTED = 'approval_granted'
    APPROVAL_DENIED = 'approval_denied'
    RUN_CANCELLED = 'run_cancelled'
    RUN_PENDING_APPROVAL = 'run_pending_approval'

    # M5 hook-observability taxonomy (ADR 0032 M5, owner decision 2026-06-13):
    # the audit events emitted by the HookRegistry bridge in the tool-dispatch
    # layer (teaagent/tools.py). Typed + mapped so the M6 fold can surface hook
    # veto/mutation activity FROM the audit JSONL. Mapping/reader only — hook
    # *execution* stays in the dispatch layer (it mutates in-flight args/results,
    # so it is not a pure spine interceptor; see the M5 assessment work-log).
    TOOL_HOOK_PRE_MUTATION = 'tool_hook_pre_mutation'
    TOOL_HOOK_PRE_MUTATION_BLOCKED = 'tool_hook_pre_mutation_blocked'
    TOOL_HOOK_VETOED = 'tool_hook_vetoed'
    TOOL_HOOK_POST_MUTATION = 'tool_hook_post_mutation'
    TOOL_HOOK_POST_FAILED = 'tool_hook_post_failed'

    # Planned (later phases): PLAN_RESOLVED, DECISION_RECEIVED,
    # CONTEXT_COMPACTED, BUDGET_CHECKPOINT, ITERATION_COMPLETED,
    # FINAL_VALIDATION, RECEIPT_EMITTED, SESSION_START, SESSION_END,
    # PRE_TOOL_USE, POST_TOOL_USE, PRE_COMPACT


@dataclass(frozen=True)
class RunEvent:
    """Immutable run-lifecycle event.

    Each event carries a type, run identifier, monotonic sequence number,
    and typed payload (mapping of event-specific data).
    """

    type: RunEventType
    run_id: str
    payload: Mapping[str, Any]
    seq: int


# Subscriber protocol aliases for type hints
Interceptor = Callable[[RunEvent], None]
Consumer = Callable[[RunEvent], None]

# ---------------------------------------------------------------------------
# RunEvent → audit event mapping (ADR 0032 M1)
# ---------------------------------------------------------------------------

_RUN_EVENT_TO_AUDIT_EVENT_TYPE: dict[RunEventType, str] = {
    RunEventType.RUN_STARTED: 'run_started',
    RunEventType.ITERATION_STARTED: 'iteration_started',
    RunEventType.TOOL_CALL_REQUESTED: 'tool_call_requested',
    RunEventType.TOOL_CALL_COMPLETED: 'tool_call_completed',
    RunEventType.TOOL_CALL_FAILED: 'tool_call_failed',
    RunEventType.RUN_COMPLETED: 'run_completed',
    RunEventType.RUN_FAILED: 'run_failed',
    # M2 evidence-event taxonomy (§16) — mapping only; not yet spine-emitted.
    RunEventType.MODEL_ROUTE: 'model_route',
    RunEventType.GIT_SANDBOX_STARTED: 'git_sandbox_started',
    RunEventType.GIT_SANDBOX_RESOLVED: 'git_sandbox_resolved',
    RunEventType.SKILL_ACTIVATED: 'skill_activated',
    RunEventType.SKILL_LIFECYCLE_TRANSITION: 'skill_lifecycle_transition',
    RunEventType.TEST_RUN: 'test_run',
    RunEventType.UNDO_APPLIED: 'undo_applied',
    RunEventType.PROVENANCE_COLLECTED: 'provenance_collected',
    RunEventType.TOOL_CALL_STARTED: 'tool_call_started',
    RunEventType.TOOL_USE: 'tool_use',
    RunEventType.TOOL_CALL_APPROVED: 'tool_call_approved',
    RunEventType.TOOL_CALL_DENIED: 'tool_call_denied',
    RunEventType.TOOL_CALL_PENDING_APPROVAL: 'tool_call_pending_approval',
    RunEventType.TOOL_ERROR: 'tool_error',
    RunEventType.APPROVAL_REQUESTED: 'approval_requested',
    RunEventType.APPROVAL_GRANTED: 'approval_granted',
    RunEventType.APPROVAL_DENIED: 'approval_denied',
    RunEventType.RUN_CANCELLED: 'run_cancelled',
    RunEventType.RUN_PENDING_APPROVAL: 'run_pending_approval',
    # M5 hook-observability taxonomy — mapping only; hook execution stays in
    # the tool-dispatch layer (teaagent/tools.py), not spine-emitted.
    RunEventType.TOOL_HOOK_PRE_MUTATION: 'tool_hook_pre_mutation',
    RunEventType.TOOL_HOOK_PRE_MUTATION_BLOCKED: 'tool_hook_pre_mutation_blocked',
    RunEventType.TOOL_HOOK_VETOED: 'tool_hook_vetoed',
    RunEventType.TOOL_HOOK_POST_MUTATION: 'tool_hook_post_mutation',
    RunEventType.TOOL_HOOK_POST_FAILED: 'tool_hook_post_failed',
}


def run_event_to_audit_event_type(event_type: RunEventType) -> str:
    """Map a ``RunEventType`` to the legacy audit event type string.

    Returns the event type string that ``AuditLogger.record()`` expects.

    Raises:
        ValueError: If the event type is not yet mapped (planned M1+ events).
    """
    audit_type = _RUN_EVENT_TO_AUDIT_EVENT_TYPE.get(event_type)
    if audit_type is None:
        raise ValueError(
            f'RunEventType {event_type!r} has no audit event mapping yet. '
            f'Supported: {list(_RUN_EVENT_TO_AUDIT_EVENT_TYPE)}'
        )
    return audit_type


# Inverse mapping: audit event type string to RunEventType
_AUDIT_EVENT_TO_RUN_EVENT_TYPE: dict[str, RunEventType] = {
    v: k for k, v in _RUN_EVENT_TO_AUDIT_EVENT_TYPE.items()
}


def audit_event_to_run_event_type(audit_type: str) -> RunEventType | None:
    """Map an audit event type string to a ``RunEventType``, or None if unmapped.

    Legacy and unmapped audit event types (e.g. 'tool_call_started', 'model_route',
    'git_sandbox_started') return None and are safely skipped by the reader.

    Args:
        audit_type: The audit event type string (from JSONL entry).

    Returns:
        The corresponding RunEventType, or None if not in the M0 set.
    """
    return _AUDIT_EVENT_TO_RUN_EVENT_TYPE.get(audit_type)


class EventSpine:
    """Synchronous, in-process event bus for run-lifecycle events.

    Subscribers are ordered: interceptors (may veto by raising) run first,
    then consumers (crash-safe, exceptions logged and isolated).

    Determinism: no threads, no async, no queues. Safe for testing and
    receipt derivation.
    """

    def __init__(self) -> None:
        """Initialize an empty spine with no subscribers."""
        self._interceptors: list[tuple[str, Interceptor]] = []
        self._consumers: list[tuple[str, Consumer, bool]] = []
        self._seq = 0

    def register_interceptor(self, fn: Interceptor, *, name: str) -> None:
        """Register a governance gate (may veto by raising).

        Interceptors run in registration order and may raise any exception
        to veto the event. Exception propagates immediately (no further
        subscribers run).

        Args:
            fn: Callable[[RunEvent], None]; may raise to veto.
            name: Human-readable name for logging/debugging.
        """
        self._interceptors.append((name, fn))

    def register_consumer(
        self, fn: Consumer, *, name: str, critical: bool = False
    ) -> None:
        """Register a side-effect subscriber (crash-safe by default).

        Consumers run after all interceptors and can never affect the run.
        Each is wrapped in try/except; exceptions are logged and isolated.

        When *critical* is ``True``, exceptions from this consumer propagate
        instead of being isolated. Use for subscribers whose failure must
        halt the run (e.g. compliance-mode audit durability).

        Args:
            fn: Callable[[RunEvent], None].
            name: Human-readable name for logging/debugging.
            critical: If ``True``, exceptions propagate (not isolated).
        """
        self._consumers.append((name, fn, critical))

    def emit(
        self, type_: RunEventType, run_id: str, payload: Mapping[str, Any]
    ) -> None:
        """Fire a typed run event through the spine.

        Increments monotonic sequence, runs interceptors (may raise/veto),
        then runs consumers (isolated from failures).

        Args:
            type_: The event type.
            run_id: The run identifier.
            payload: Event-specific data (immutable mapping).

        Raises:
            Any exception raised by an interceptor (veto semantics).
        """
        self._seq += 1
        event = RunEvent(type=type_, run_id=run_id, payload=payload, seq=self._seq)

        # Run interceptors in order; exception halts spine (veto).
        for _name, interceptor in self._interceptors:
            try:
                interceptor(event)
            except Exception:
                # Interceptor veto: propagate immediately.
                raise

        # Run consumers in order; isolated from failures by default.
        for name, consumer, critical in self._consumers:
            try:
                consumer(event)
            except Exception as e:
                if critical:
                    raise
                logger.exception(
                    f'Consumer {name!r} raised during {type_.value}; continuing. '
                    f'Error: {e}'
                )


def read_run_events_from_audit(
    entries: Iterable[Mapping[str, Any]],
) -> list[RunEvent]:
    """Convert audit JSONL entries to typed RunEvents.

    Iterates over audit event dicts (already-parsed from JSONL), converts
    those with mapped event types to RunEvents, and skips legacy/unmapped
    event types. Sequence numbers are 1-based and monotonic over yielded events.

    Redaction is preserved: payloads are passed through as-is from the audit
    entries without reconstruction or un-redaction.

    Args:
        entries: An iterable of audit event dicts (from parsed JSONL lines).
                 Expected keys: event_type, run_id, payload.

    Returns:
        A list of RunEvent objects in order, with seq 1..N monotonic.
    """
    events: list[RunEvent] = []
    seq = 0

    for entry in entries:
        audit_type = entry.get('event_type')
        if audit_type is None:
            continue
        run_event_type = audit_event_to_run_event_type(audit_type)

        # Skip entries whose event_type does not map to RunEventType
        if run_event_type is None:
            continue

        seq += 1
        run_id = entry.get('run_id', '')
        payload = entry.get('payload', {})

        # Construct a RunEvent with the mapped type, run_id, payload, and seq.
        event = RunEvent(
            type=run_event_type,
            run_id=run_id,
            payload=payload,
            seq=seq,
        )
        events.append(event)

    return events


def read_run_events_from_jsonl(path: str | Path) -> list[RunEvent]:
    """Read a JSONL audit file and convert it to RunEvents.

    Opens the file, parses each non-empty line as JSON, delegates to
    read_run_events_from_audit, and returns the typed event list.

    Tolerates blank lines and preserves redaction.

    Args:
        path: Path to the JSONL audit file.

    Returns:
        A list of RunEvent objects extracted from the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If a non-empty line is not valid JSON.
    """
    path_obj = Path(path) if isinstance(path, str) else path
    entries: list[Mapping[str, Any]] = []

    with open(path_obj, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                # Tolerate blank lines
                continue
            entries.append(json.loads(line))

    return read_run_events_from_audit(entries)


def register_audit_consumer(spine: EventSpine, audit: AuditLogger) -> None:
    """Register an ``AuditLogger`` as an ``EventSpine`` consumer (ADR 0032 M1).

    The consumer maps each ``RunEvent`` to the legacy audit event type string
    and calls ``audit.record()``.

    If the audit logger is in compliance mode, the consumer is registered as
    *critical*, so that ``AuditDurabilityError`` propagates and halts the run.

    Args:
        spine: The event spine to subscribe to.
        audit: The audit logger to drive from RunEvents.
    """

    is_compliance = getattr(audit, '_compliance_mode', False)

    def _audit_consumer(event: RunEvent) -> None:
        try:
            audit_type = run_event_to_audit_event_type(event.type)
        except ValueError:
            logger.warning(
                'Skipping audit for unmapped event %s (seq=%d)',
                event.type.value,
                event.seq,
            )
            return
        audit.record(audit_type, event.run_id, **dict(event.payload))

    spine.register_consumer(
        _audit_consumer,
        name='audit_logger',
        critical=bool(is_compliance),
    )
