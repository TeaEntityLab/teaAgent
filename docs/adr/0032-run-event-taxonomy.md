# ADR 0032: Run Event Taxonomy and Event Spine

## Status

Accepted — owner-approved 2026-06-13 (unblocks M1: AuditLogger as consumer)

## Date

2026-06-13

## Context

Three parallel half-systems currently handle run-lifecycle events, making it difficult to reason about governance, audit, and receipts as a unified concern:

1. **Audit strings** (`audit.record('run_started', ...)` etc.) — scattered call sites, implicit taxonomy of event names, consumed by receipts and evidence.
2. **HookRegistry** (teaagent/hooks.py) — Claude-Code-compatible hook events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, SubagentStop, SessionEnd), wired only at the tool boundary, carries veto semantics via HookError.
3. **ContextBus** (teaagent/context_bus.py) — separate event mechanism for deltas.

Meanwhile, every governance gate (approval, budget, plan, tool policy) is inlined in AgentRunner (runner/_core.py), which creates a gravity well and makes testing governance independently difficult. The control-loop ownership map (docs/architecture/control-loop-ownership-map-2026-06-11.md) identifies this as a core architectural pain point.

## Decision

Introduce a typed **run-lifecycle event spine** with explicit event taxonomy and two subscriber classes:

### 1. RunEvent Type System

Define a `RunEventType(str, Enum)` whose members are seeded from:
- The union of existing audit event names (run_started, iteration_started, tool_call_completed, tool_call_failed, context_compacted, validation_started)
- The run-lifecycle taxonomy from harness-first-direction §6.3 (plan_resolved, decision_received, tool_call_requested, budget_checkpoint, context_compacted, iteration_completed, final_validation, run_completed, run_failed, run_pending_approval, run_cancelled, receipt_emitted, session_start, session_end, etc.)

Minimal M0 set for this spike:
- `RUN_STARTED` — run begins
- `ITERATION_STARTED` — iteration loop begins
- `TOOL_CALL_REQUESTED` — tool call requested (before gates)
- `TOOL_CALL_COMPLETED` — tool call succeeded
- `TOOL_CALL_FAILED` — tool call errored
- `RUN_COMPLETED` — run ends successfully
- `RUN_FAILED` — run ends in failure

(Extendable; the full taxonomy is defined in this ADR and documented in code comments.)

### 2. Event Spine Architecture

**RunEvent dataclass** (frozen, immutable):
```
type: RunEventType
run_id: str
payload: Mapping[str, Any]  # typed payload; structure per event type
seq: int  # monotonic sequence number per spine instance
```

**EventSpine class** (sync-first, in-process, deterministic):
```
register_interceptor(fn, *, name: str) -> None
  # Callable[[RunEvent], None]; may raise to veto
  # Interceptors run in registration order before consumers
  # Exceptions propagate (veto semantics)

register_consumer(fn, *, name: str, critical: bool = False) -> None
  # Callable[[RunEvent], None]; isolated by default
  # Consumers run after interceptors
  # Exceptions are caught, logged, and isolated unless critical=True
  # Critical consumers propagate to preserve required durability boundaries

emit(type_: RunEventType, run_id: str, payload: Mapping[str, Any]) -> None
  # Fire an event: run interceptors in order, then consumers
  # If any interceptor raises, propagate immediately (no further subscribers run)
  # If any non-critical consumer raises, log and continue
  # If any critical consumer raises, propagate
  # Return normally on success or after isolated consumer failure
```

### 3. Subscriber Semantics

**Interceptors:**
- Represent governance gates (plan validation, approval, budget, policy)
- Run in declared order before any consumer sees the event
- May raise any exception (converted to DenialReasonCode if ToolPermissionError or similar)
- Exception from interceptor halts the spine (veto)
- Used to enforce hard constraints

**Consumers:**
- Represent audit, receipt building, evidence, ContextBus, webhook sinks
- Run after all interceptors complete
- Each wrapped in try/except by default (exception logged via logging module)
- Non-critical consumers never affect the run (crash-safe)
- Critical consumers may propagate when their side effect is part of the
  required safety boundary, such as compliance-mode audit durability
- Used for side effects and derived state

### 4. HookRegistry Alignment

Existing Claude-Code hook names (SessionStart, PreToolUse, PostToolUse, etc.) remain the public `teaagent/hooks.py` API. The spine taxonomy includes semantically equivalent typed hook-observability events (for example, `PRE_TOOL_USE`) so later integration can bridge the public hook API without changing hook names.

### 5. Compliance with ADR 0030

New code lives inside the existing `teaagent/runner/` package (teaagent/runner/_events.py) — no new root module. The module freeze is respected.

## Rationale

- **Single contract**: One typed enum replaces three implicit taxonomies; claim-testable, refactorable, and extensible.
- **Determinism**: Sync-first, in-process, no threads — deterministic for tests, safe for receipts.
- **Veto clarity**: Interceptor ordering and exception semantics are explicit, enabling governance gates to be extracted without rewriting the runner.
- **Gradual migration**: Dual-write (M0) allows the old audit.record() paths to coexist with new events, so the migration is strangler-safe.
- **Test leverage**: Lifecycle tests can assert event sequences instead of implementation internals, decoupling tests from runner refactors.

## Implementation

### Phase M0 (this ADR, this spike)

1. Define `RunEventType(str, Enum)` and `RunEvent` dataclass in teaagent/runner/_events.py.
2. Define `EventSpine` class with register_interceptor, register_consumer, emit semantics.
3. Add optional `event_spine: EventSpine | None` parameter to AgentRunner (default: fresh spine, no subscribers).
4. At existing audit.record call sites, **dual-write**: emit corresponding RunEvent (audit calls unchanged).
5. Lifecycle tests assert the event sequence for the five-minute-proof scenario.
6. Acceptance tier stays green.

### Future Phases (M1–M6)

| Step | Change | Invariant |
| --- | --- | --- |
| M1 | AuditLogger becomes a consumer (serializes RunEvents to JSONL) | Byte-equivalent audit on proof scenario |
| M2 | Receipts/evidence fold over event stream | Receipt completeness guaranteed structurally |
| M3 | Plan gate moves to interceptor | Same denials, same reason codes |
| M4 | Approval and budget gates to interceptors | Same semantics, extracted from runner |
| M5 | HookRegistry re-homed onto spine; public hook API documented | Existing hook tests pass via aliases |
| M6 | ContextBus + webhook sinks consume spine; inline emission paths deleted | No orphaned eventing modules |

### Realized architecture (M1–M7, completed 2026-06-13)

The phases above were the *proposal*. Executed parity-first and assessed against
the code at each step, the migration converged on a **narrower, sound** outcome —
recorded here as the durable contract (see the per-phase work-logs under
`docs/work-log/` and the plan `docs/plans/adr-0032-m1-m6-work-plan-2026-06-13.md`):

- **M1** — done as proposed: `AuditLogger` is an `EventSpine` consumer
  (`register_audit_consumer`), byte-equivalent on the proof scenario.
- **M2** — re-scoped to **taxonomy-only**: every evidence/decision audit event is
  typed in `RunEventType` and mapped both directions; the reader surfaces them
  from the audit JSONL. (Emit-site migration deferred.)
- **M3** — **plan gate moved to an interceptor** (the one gate that fit), landed
  shadow→enforce in two commits with a reason-code parity oracle.
- **M4** — **approval and budget enforcement STAY INLINE.** Both are
  runtime-stateful (approval: live JIT/session state + handler + auto-mode-
  swappable policy; budget: mutable dedup sets + an interactive `on_prompt`
  side-effect handler + multi-point evolving-cost checks). Forcing them into a
  pure interceptor-on-event was a regression risk invisible to unit parity tests.
  Their observability still reaches the fold via typed audit events.
- **M5** — **hook OBSERVABILITY** is typed onto the spine; **hook EXECUTION stays
  in the tool-dispatch layer** (`teaagent/tools.py`) because PreToolUse/PostToolUse
  mutate in-flight args/results, and the session-lifecycle hooks are unwired.
  *Scope note (review F1, RESOLVED 2026-06-14): the 5 hook audit events are typed
  and now folded into evidence via `RunEvidenceBundle.hook_activity` +
  `extract_hook_activity` — hook veto/mutation appears in the bundle/receipt and
  folds through the typed stream.*
- **M6** — **evidence/receipts fold over the typed stream** (`build_evidence_from_events`,
  now the production path inside `build_run_evidence_bundle`). Fixed a real
  lossiness gap (typed `RunEvent` now carries `created_at`).
- **M7** — **guard + document (this section).** "ContextBus + webhook consume the
  spine; delete inline eventing" was **not** done: it is a regression or vacuous.

**The realized invariant (M7), enforced by `scripts/validate_event_spine_wiring.py`
and `tests/test_event_spine_wiring.py`:**

```
EventSpine.emit ──(register_audit_consumer, M1)──▶ AuditLogger.record
                                                         │
                                add_sink fan-out: webhook, OTel, …
```

- `EventSpine` (`teaagent/runner/_events.py`) is **the** typed run-lifecycle path.
- `AuditLogger` (`teaagent/audit.py`) is the **complete event record and the sink
  hub**, and a spine consumer since M1. Governance events that stay inline
  (approval, budget, hooks) are written via `audit.record` — that **is** the
  record, not redundant inline eventing to delete.
- **Webhook / OTel are audit *sinks***, not direct spine consumers — a direct
  consumer would see only the spine-emitted subset (a coverage regression).
- `ContextBus` and the integration `RunEventStream` are **unwired in production**;
  they are not lifecycle buses. The guard's allowlist names every sanctioned
  event-delivery surface. The taxonomy-closure check proves no `RunEventType` is
  orphaned from the audit record.
- A third check (review F2) AST-discovers the audit `event_type` literals the
  evidence extractors read (`run_evidence.py`, `proof_of_use.py`) and asserts
  each is in `RunEventType` — so the M6 FOLD-T002 cutover (which drops unmapped
  types) can never silently lose evidence as extractors evolve.
- *Guard scope (review F3, narrowed 2026-06-14): the orphan-bus check keys on
  high-signal method names (`register_consumer`, `register_interceptor`,
  `add_sink`, `on_event`, `publish_delta`, `subscribe_deltas`) **plus the
  `subscribe`+`emit` pub/sub pair** (so the `RunEventStream` shape is now caught).
  It remains a heuristic — a bus using entirely novel naming could still evade
  it — but it catches every shape that occurs in-tree and forces a conscious
  allowlist decision. The F2 discovery similarly resolves `==`/`in` against
  string literals and module-level `frozenset`/`set` constants; exotic dynamic
  lookups are out of scope.*

**Lesson:** the spine's realized value is the **typed read side** (evidence →
receipts) and a single typed lifecycle path — not wholesale relocation of
runtime-stateful enforcement. The plan gate was the one gate that genuinely
belonged on the spine.

## Consequences

**Positive:**
- Unified event contract enables incremental gate extraction without rewriting AgentRunner.
- Governance gates become testable independently via lifecycle assertions.
- Receipts/audit can be derived from a single immutable event stream (M2+), eliminating synthetic-vs-real gaps.
- Hook ordering and error semantics are explicit and stable for the public API.

**Negative:**
- M0 dual-write adds ~5 lines per call site (acceptable; temporary until M1).
- EventSpine is new infrastructure; must be proven correct before gates migrate to interceptors.
- Full governance-gate extraction (M3–M4) is multi-phase and requires consecutive landing without behavioral changes (per stop-rule in strategy doc §6.4).

## Alternatives Considered

1. **Extend HookRegistry instead of creating EventSpine**: HookRegistry is Claude-Code-specific and tool-boundary-scoped; the spine covers the full run lifecycle and cannot be scoped to tools. Separate design avoids conflating concerns.

2. **Async event sink**: Async sinks (queue-based consumers) would enable webhook delivery and distributed audit. Rejected at M0 for determinism: tests must not depend on timing. Async can be added at M2+ if friction evidence justifies it.

3. **Fold events into context/observations**: Events would become observation slots instead of a separate spine. Rejected: observations are model-visible; governance events must be opaque to the model and ordered by the harness.

## References

- [Harness-First Direction §6](../strategy/harness-first-direction-2026-06-13.md#6-core-architecture-one-event-spine-gates-as-interceptors)
- [Control-Loop Ownership Map §6.1](../architecture/control-loop-ownership-map-2026-06-11.md)
- [ADR 0030: Root-Module Freeze](0030-root-module-freeze.md)
- [ADR 0009: 5-Loop Governance System](0009-five-loop-governance.md)

## Full Event Taxonomy (M0 + Planned)

```
RUN_STARTED              # Run begins; payload: run_id, task, model, etc.
SESSION_START            # Session begins; equivalent public hook: SessionStart
PLAN_RESOLVED            # Plan loaded/validated
ITERATION_STARTED        # Iteration loop begins
DECISION_RECEIVED        # Model returns a decision (tool call or final answer)
TOOL_CALL_REQUESTED      # Tool call identified (before gates)
TOOL_CALL_APPROVED       # Approval gate approved
TOOL_CALL_DENIED         # Approval gate denied
TOOL_CALL_COMPLETED      # Tool call succeeded
TOOL_CALL_FAILED         # Tool call errored
CONTEXT_COMPACTED        # Context compaction occurred
BUDGET_CHECKPOINT        # Budget check (not veto; informational)
ITERATION_COMPLETED      # Iteration loop ends
FINAL_VALIDATION         # Final answer validation
RUN_COMPLETED            # Run ends successfully
RUN_FAILED               # Run ends in failure
RUN_PENDING_APPROVAL     # Run paused for approval
RUN_CANCELLED            # Run cancelled by user
RECEIPT_EMITTED          # Receipt finalized
SESSION_END              # Session ends; equivalent public hook: SessionEnd
SKILL_LOAD               # Skill loaded
MODEL_ROUTE              # Model routed (provider selection)
GIT_SANDBOX_STARTED      # Sandbox workspace initialized
GIT_SANDBOX_RESOLVED     # Sandbox resolved/cleaned
UNDO_PERFORMED           # Undo action executed
PRE_TOOL_USE             # Hook observability: before tool execution; public hook: PreToolUse
POST_TOOL_USE            # Hook observability: after tool execution; public hook: PostToolUse
PRE_COMPACT              # Hook observability: before context compaction; public hook: PreCompact
```

The M0 spike covers RUN_STARTED, ITERATION_STARTED, TOOL_CALL_REQUESTED, TOOL_CALL_COMPLETED, TOOL_CALL_FAILED, RUN_COMPLETED, RUN_FAILED. Extended events are added in later phases as gates migrate.
