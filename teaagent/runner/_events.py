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

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

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

    # Planned (M1+): PLAN_RESOLVED, DECISION_RECEIVED, TOOL_CALL_APPROVED,
    # TOOL_CALL_DENIED, CONTEXT_COMPACTED, BUDGET_CHECKPOINT, ITERATION_COMPLETED,
    # FINAL_VALIDATION, RUN_PENDING_APPROVAL, RUN_CANCELLED, RECEIPT_EMITTED,
    # SESSION_START, SESSION_END, SKILL_LOAD, MODEL_ROUTE, GIT_SANDBOX_STARTED,
    # GIT_SANDBOX_RESOLVED, UNDO_PERFORMED, PRE_TOOL_USE, POST_TOOL_USE, PRE_COMPACT


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
        self._consumers: list[tuple[str, Consumer]] = []
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

    def register_consumer(self, fn: Consumer, *, name: str) -> None:
        """Register a side-effect subscriber (crash-safe).

        Consumers run after all interceptors and can never affect the run.
        Each is wrapped in try/except; exceptions are logged and isolated.

        Args:
            fn: Callable[[RunEvent], None]; never raises (exceptions caught).
            name: Human-readable name for logging/debugging.
        """
        self._consumers.append((name, fn))

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

        # Run consumers in order; each isolated from failures.
        for name, consumer in self._consumers:
            try:
                consumer(event)
            except Exception as e:
                logger.exception(
                    f'Consumer {name!r} raised during {type_.value}; continuing. '
                    f'Error: {e}'
                )
