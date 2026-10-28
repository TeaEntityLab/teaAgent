# ADR 0032: Run Event Taxonomy and Event Spine

## Status

Accepted and Implemented — owner-approved 2026-06-13; M0-M7 migration closed
2026-06-14. The realized contract below supersedes the proposed M1-M6 phase
shape where they differ.

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

### Original Proposed Phases (M1–M6)

| Step | Change | Invariant |
| --- | --- | --- |
| M1 | AuditLogger becomes a consumer (serializes RunEvents to JSONL) | Byte-equivalent audit on proof scenario |
| M2 | Receipts/evidence fold over event stream | Receipt completeness guaranteed structurally |
| M3 | Plan gate moves to interceptor | Same denials, same reason codes |
| M4 | Approval and budget gates to interceptors | Same semantics, extracted from runner |
| M5 | HookRegistry re-homed onto spine; public hook API documented | Existing hook tests pass via aliases |
| M6 | ContextBus + webhook sinks consume spine; inline emission paths deleted | No orphaned eventing modules |

### Realized architecture (M1–M7, completed 2026-06-14)

The phases above were the *proposal*. Executed parity-first and assessed against
the code at each step, the migration converged on a **narrower, sound** outcome —
recorded here as the durable contract (see the per-phase work-logs under
`docs/work-log/` and the plan `docs/plans/adr-0032-m1-m6-work-plan-2026-06-13.md`):

| Original decision intent | Realized result |
| --- | --- |
| One typed, deterministic run-lifecycle contract | Preserved: `EventSpine` is synchronous and ordered; `RunEventType` closes over evidence-bearing audit events. |
| Audit and evidence derive from that contract without compatibility loss | Preserved: audit is a critical-capable spine consumer; production evidence folds persisted audit through typed `RunEvent`s. |
| Extract governance only when parity proves unchanged behavior | Narrowed deliberately: the plan gate moved; stateful approval and budget enforcement remained inline. |
| Avoid competing lifecycle buses and unsafe side-effect relocation | Preserved: webhook/OTel remain audit sinks; ContextBus and `RunEventStream` remain distinct, unwired surfaces guarded by an allowlist. |

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
- [ADR 0009: 5-Loop Governance System](0009-5-loop-governance-system.md)

## Full Event Taxonomy (M0 + Planned)

```
RUN_STARTED              # Run begins; payload: run_id, task, model, origin (owner|agent|fixture|synthetic|unknown; default unknown — never silently 'owner'), etc.
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

---

## Amendment A1 (Accepted 2026-10-27): Background Lifecycle Events

> **Amendment status: Accepted by the owner on 2026-10-27; implementation pending.**
> This amendment does not change the Status of ADR 0032 above, which remains
> "Accepted and Implemented". The owner's answers to the A1.7 questions are
> recorded there; the payloads and tests below already reflect them.

### A1.1 Context

BG-001 §3.5 (`docs/specs/background-lifecycle-acceptance-spec-2026-07-11.md`)
requires the two background lifecycle transitions to join the ADR 0032 taxonomy.
Today they exist only as mutable fields on the background JSON record
(`submitted` at `start()`, `stopped_at` / `stop_signal` at `stop()`). Those
fields are overwritten on every read or stop, so the record cannot prove when a
background run was submitted or how often and when it was stopped. A repeated
`stop` converges on the first record and leaves no history. The
`BackgroundRunStore` writes nothing to any audit chain today.

The background child is an ordinary `teaagent agent run` process. It mints its
own `run_id` at startup, and the background argv builder
(`build_agent_run_command`) never passes one in. The parent that submits or
stops a background run has no run of its own. Any emit site must account for
both facts.

### A1.2 Decision

**Event names.** Two new `RunEventType` members, with serialized values that
match the existing activation test
`tests/lifecycle/test_background_lifecycle_spec.py::test_background_event_taxonomy_activates`:

| Member | Serialized `event_type` |
| --- | --- |
| `RunEventType.BACKGROUND_SUBMITTED` | `background_submitted` |
| `RunEventType.BACKGROUND_STOPPED` | `background_stopped` |

**Payloads.** All payload values are JSON-safe. Unknown keys are not permitted.

`background_submitted` is emitted once, after the record file is persisted:

| Key | Type | Meaning |
| --- | --- | --- |
| `background_id` | str | uuid4 hex, as in the record |
| `child_run_id` | null | Always `null` at submit: the child mints its run id later. Backfilled only in the record, never here. |
| `pid` | int | Pid of the detached child |
| `started_at` | str | ISO-8601 UTC, same value as the record |
| `command_digest` | str | `sha256` hex of `json.dumps(command)` (the full argv, including the task text). The digest is one-way, so the task text is not written to the chain. |
| `label` | str or null | Record label, if any |

`background_stopped` is emitted once, on the first transition in `stop()`,
after the stop record is persisted:

| Key | Type | Meaning |
| --- | --- | --- |
| `background_id` | str | As above |
| `child_run_id` | str or null | The child run id if the record had backfilled it at stop time, otherwise `null` |
| `pid` | int | Pid that was signalled (or found dead) |
| `stop_signal` | `"SIGTERM"` or `"SIGKILL"` | The signal recorded by `stop()` (see §6 of BG-001 for the accepted race) |
| `stopped_at` | str | ISO-8601 UTC, same value as the record |
| `exit_code` | int or null | Exit code known to `get()` at stop time, else `null` |
| `exit_code_derived` | bool | `true` only when `exit_code` is the U-P1-17 stand-in (a completed run's `0`). Never persisted to the record. |

Rules that follow from these payloads:

- `alive` is not a payload key. It is always false after a stop, and the record already says so.
- A stop on an already-dead process still emits (BG-001 §3.6: the stop is recorded without raising).
- A repeated `stop` on a stopped record returns early and emits nothing. The first stop's event is the only one.

**Emitting process.** The parent CLI process that performs the transition:

- `background_submitted`: the process that calls `BackgroundRunStore.start()`
  (`agent run --background`, the automation tick, the deprecated ultrawork
  wrapper).
- `background_stopped`: the process that calls `BackgroundRunStore.stop()`.
  This is a different process from the child, and the child may have been
  SIGKILLed before it could write anything.

**Destination (the choice this amendment makes).** A dedicated, append-only,
hash-chained file in the same tenant-scoped directory as the records:
`<BackgroundRunStore.dir>/lifecycle-<sha256(workspace root)[:12]>.jsonl`, written
through `AuditLogger(path=...)`. The `<h>` suffix is the first 12 hex chars of
sha256 of the resolved workspace root, so each workspace has its own chain and
HMAC key (A1.7, owner decision 2026-10-27). The envelope `run_id` is the synthetic value
`background:<background_id>`. Rationale:

1. The schema requires a non-empty `run_id` on every event, and no parent run
   exists. The synthetic namespace gives each background record one stable,
   known-at-submit identifier that the envelope can carry.
2. The submit event must survive even if the child never starts, and the stop
   event must survive the child being SIGKILLed. A file the parent owns
   satisfies both. A child-owned log does not.
3. The file is a new state boundary. It keeps background lifecycle out of
   every run's chain and out of the workspace-wide chain, so run evidence
   folds (`build_evidence_from_events`) are unaffected.
4. Concurrent writers (submit in one process, stop in another) are already
   handled by `AuditLogger.record`, which reads the chain tip under the file
   lock (the 2026-10-23 tip-resync fix). This amendment relies on that fix
   and does not add a second lock.

**Ordering and failure.** Persist the record first, then emit. The record
remains the operational source of truth, and an emit failure cannot make
`stop()` report failure. In compliance mode a failed emit raises. Outside
compliance mode the failure is logged at ERROR with the category and the
`background_id`, and the gap is accepted and visible (open question Q4).

**What does not change.** `BackgroundRunRecord` fields (the BG-001 pinned
protocol), the record file format, `background list/show`, the cockpit, and
`exit_code` semantics. The derived `orphaned` state is not an event.

### A1.3 Schema change

- `RunEventType` (`teaagent/runner/_events.py`): add the two members. Add
  matching entries to `_RUN_EVENT_TO_AUDIT_EVENT_TYPE`. The taxonomy-closure
  check in `scripts/validate_event_spine_wiring.py` requires a lossless mapping
  for every member and fails otherwise.
- `docs/audit-event.schema.json`: **no change.** The schema has no `enum` for
  `event_type` (it is `{"type": "string", "minLength": 1}`). The two new names
  are valid as written, so the schema-sync gate (G6) is satisfied by
  confirming the schema is unchanged. The owner's brief expected enum
  additions there; they do not exist, and this amendment does not add one.
- `docs/audit-events.md` lists event types. It needs a two-row addition in the
  same change, and it is the only doc table to update.

### A1.4 Compatibility

- Additive. No existing event type is renamed, removed, or re-shaped.
- Readers that ignore unknown `event_type` values are unaffected. The schema
  accepts any non-empty string.
- Run-level readers (`run_store`, evidence folds, receipts) never open
  the workspace lifecycle file (`lifecycle-<h>.jsonl`), so they see no new events.
- Rollback: stop emitting and revert the enum members and mapping entries.
  The workspace lifecycle file (`lifecycle-<h>.jsonl`) stays on disk. It is a valid chain, and nothing reads it.
  No migration is needed.
- Downgrade: an older build ignores the file entirely.

### A1.5 Rejected alternatives

1. **Emit into the child run's log** (`RunStore.run_path(run_id)`). Rejected.
   At submit there is no `run_id`, and the child may never start. At stop the
   child is already dead, and the stopper writing into the child's chain mixes
   two owners in one chain. It also breaks the run's own evidence and receipt
   boundary.
2. **Child emits `background_submitted` via a new argv flag** (for example
   `--background-id`). Rejected. It couples the argv builder to the event,
   makes the submit record depend on the child reaching its startup code, and
   misattributes a parent decision to the child.
3. **Keep deriving the events from the record** (status quo). Rejected by
   BG-001 §3.5. The record is mutable, `stop` is idempotent by overwrite, and
   history is lost.
4. **Write into the workspace-wide or `pending-*.jsonl` run audit.** Rejected.
   The shared workspace chain would couple background lifecycle to unrelated
   writers. `RunStore.audit_logger(None)` creates a new file per call, so it
   gives no stable chain.
5. **A new `background.*` event namespace or a separate schema file.** Rejected.
   It breaks ADR 0032's single taxonomy and the schema's free-string
   convention.
6. **Full command in the payload.** Rejected for the default. The spec (§6)
   and this amendment record a digest only; no readable command summary is
   written (owner decision Q3, 2026-10-27).

### A1.6 Exact test list (to be written with the implementation; none in this change)

Existing test to activate (its `skipif` is removed once the members exist):

1. `tests/lifecycle/test_background_lifecycle_spec.py::test_background_event_taxonomy_activates`

New file `tests/test_background_lifecycle_events.py`:

2. `test_start_emits_background_submitted_after_record_persisted`
3. `test_submitted_payload_keys_are_exact` (keys == the table in A1.2)
4. `test_submitted_run_id_is_null_at_submit`
5. `test_command_digest_is_sha256_of_argv_and_excludes_task_text`
6. `test_submitted_payload_has_no_readable_command` (digest only, Q3)
7. `test_stop_emits_background_stopped_on_first_transition`
8. `test_repeated_stop_emits_no_second_event`
9. `test_stop_on_dead_process_still_emits_background_stopped` (BG-001 §3.6)
10. `test_stopped_exit_code_derived_true_only_for_completed_stand_in` (U-P1-17)
11. `test_stopped_exit_code_null_for_reaped_failed_run` (U-P1-17 regression)
12. `test_envelope_run_id_is_background_namespace_and_non_empty`
13. `test_envelope_run_id_never_collides_with_minted_run_ids`
14. `test_lifecycle_chain_verifies_strict_with_submit_and_stop_from_two_loggers`
    (same pattern as `tests/test_audit_chain_tip_resync.py`)
15. `test_readonly_store_emits_nothing`
16. `test_record_persist_failure_emits_nothing`
17. `test_emit_failure_compliance_mode_raises`
18. `test_emit_failure_outside_compliance_logs_and_returns`
19. `test_tenant_scoped_lifecycle_path_under_tenant_dir`
20. `test_run_evidence_fold_unchanged_without_background_events` (golden)

Existing gates that must stay green:

21. `scripts/validate_event_spine_wiring.py` (taxonomy closure)
22. `scripts/check_audit_schema_conformance.py` and
    `tests/test_audit_schema_conformance.py` (schema unchanged)
23. `tests/lifecycle/test_background_lifecycle_spec.py` (all other tests)
24. `tests/test_background_run.py`, `tests/test_background_unified.py`,
    `tests/test_background_exit_code_fallback.py`

### A1.7 Owner decisions (2026-10-27)

- **Q1 Destination — decided: dedicated `lifecycle.jsonl`.** The events go to
  the hash-chained `<BackgroundRunStore.dir>/lifecycle.jsonl`, not the child
  run's log. (Name superseded by the owner decision below: the file is now
  `lifecycle-<h>.jsonl`, one per workspace.)
- **Q2 Synthetic envelope id — follows from Q1.** `background:<background_id>`
  is the envelope `run_id` of the dedicated chain as drafted. Not asked
  separately; raise it at implementation review if a different id is wanted.
- **Q3 Command info — decided: digest only.** `command_digest` (sha256 of the
  argv) is the only command field; there is no `command_summary`.
- **Q4 Emit failure — decided: persist then emit; log the gap, no retry.** Outside
  compliance mode a failed emit is logged at ERROR and not re-emitted (no
  duplicates); compliance mode still raises.
- **Q5 Placement — decided: amend ADR 0032** (this section), not a new ADR.
- **Q6 Spec wording — follows from Q1.** BG-001 §3.5 says the events are
  "consumed by audit like all spine events"; with the separate chain, that
  wording is edited in the implementation change.
- **Owner decision 2026-10-27 — payload key `child_run_id`.** The A1.2 payload
  key `run_id` is renamed `child_run_id` in both `background_submitted` and
  `background_stopped`. The envelope `run_id` stays `background:<background_id>`.
  With no `run_id` payload key, `AuditLogger.record(event_type, run_id,
  **payload)` is called normally. The private `_LifecycleAuditLogger` subclass
  and its `_apply_audit_level` override are removed. `AuditLogger` is unchanged.
- **Owner decision 2026-10-27 — per-workspace lifecycle file.** The file is
  `<BackgroundRunStore.dir>/lifecycle-<sha256(workspace root)[:12]>.jsonl`
  (`lifecycle_log_path`), not one shared `lifecycle.jsonl`. `AuditLogger` keys
  its HMAC chain by file stem, so a per-workspace stem gives each workspace its
  own chain key. A single shared file would make every workspace's chain verify
  against one key.
- **Q7 Readers — out of scope.** Whether `background list/show` or the cockpit
  shows lifecycle history is not decided here.
