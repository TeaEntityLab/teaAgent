# ADR 0025: Shared ChatSessionController for Chat Surfaces

## Status

Accepted and Implemented - 2026-06-04

- **REPL (`teaagent chat`):** Implemented.
- **TUI (`teaagent tui`):** Implemented through `ChatSessionController`.
- **Remaining product hardening:** full REPL-originated suspend-to-resume
  rehydration and broader CLI/TUI journey parity tests are tracked outside this
  ADR.

## Context

TeaAgent exposes the chat agent through two interactive surfaces — the CLI REPL
(`teaagent/cli/_handlers/chat_repl.py`) and the TUI (`teaagent/tui/__init__.py`) — plus
the non-interactive agent runner. The two interactive surfaces independently
re-implemented task execution, result handling, cost tracking, and undo. This
divergence produced a family of correctness defects documented in the 2026-06-01
daily-driver review (CG-01…CG-10):

1. **Result handling** — the REPL compared a `RunResult` to `0` (`if result != 0`), so
   every task reported failure and the answer was never printed (CG-01).
2. **Destructive undo** — the REPL `/undo` ran `git checkout -- .`, destroying all
   uncommitted work, while the TUI used a surgical mechanism (CG-02).
3. **Fabricated cost** — both surfaces displayed cost that was either a `+= 10`
   placeholder or a counter that was never incremented (CG-03).
4. **Dishonest suspension** — `/background` silently switched git branches and bypassed
   the audit chain (CG-09, CG-10).

The root cause (CG-05) was the absence of a single execution path: a fix applied to one
surface left the other wrong, and behavior drifted continuously.

## Decision

Introduce `teaagent/chat_session_controller.py` defining `ChatSessionController`,
`SessionState`, and `ExecutionResult` as the single execution path for chat tasks across
interactive surfaces. Surfaces become I/O adapters; the controller owns the
governance-relevant behavior.

### Core Components

#### 1. `ChatSessionController.execute_task`
- Sets up audit + `UndoJournal` (or accepts injected ones).
- Runs `run_chat_agent`, persists the run, saves the undo journal if it has entries.
- Handles result display: prints `final_answer.content` on `completed`, else the error
  (CG-01).
- Accumulates real cost: `session_state.session_cost_cents += result.cost_cents` (CG-03).
- Appends the turn to `session_state.observations` (CG-04).

#### 2. `ChatSessionController.undo_last_run`
- Routes undo through `UndoJournal.restore()` — surgical, run-scoped — replacing
  `git checkout -- .` (CG-02).

#### 3. `SessionState`
- Single mutable carrier for `session_cost_cents`, `observations`, `compaction_count`,
  `targeted_files`, shared between controller and surface.

**Files:**
- `teaagent/chat_session_controller.py`
- `teaagent/cli/_handlers/chat_repl.py`
- `teaagent/tui/__init__.py`

**Features:**
- One result-handling, cost, and undo implementation for the REPL and TUI.
- Honest, audited suspension (`audit.record('session_suspended', …)`, no branch switch)
  retained in `chat_repl.py` (CG-09/CG-10).

## Rationale

A single execution path is the only durable fix for drift: it converts "remember to fix
both surfaces" into "fix it once." It also concentrates the governance-critical behavior
(audit, undo, cost) where it can be tested in isolation, independent of terminal I/O.

## Implementation

Implemented for the REPL in the 2026-06-01 fix batch and for the TUI by the
Phase 0 daily-driver repair passes completed on 2026-06-04. The current status
page records CG-11, CG-12, CG-13, CG-15, and TASK-DD2-013 as fixed or
regression-guarded. TUI command-path tests now cover controller-backed cost
accumulation and undo behavior.

## Consequences

### Positive
- REPL and TUI result/cost/undo behavior share one governed execution path.
- New chat behavior added to the controller benefits both interactive surfaces.
- Governance behavior is unit-testable without a TTY.

### Remaining Risks

- Full REPL-originated suspend-to-resume rehydration remains a separate Phase 2
  task. The current honest path is `teaagent agent interactive-review <run_id>`.
- CLI/TUI parity should keep moving from unit-level command tests into
  cross-surface journey tests for session, cost, approval, undo, and memory.
- Future surface-specific features must call the controller instead of
  reintroducing direct `run_chat_agent` execution.

## Alternatives Considered

- **Fix each surface in place (no shared module).** Rejected — this is what produced the
  drift (CG-05); it does not prevent recurrence.
- **Make the TUI a thin wrapper over the REPL.** Rejected — the TUI's richer rendering
  (run-summary, JSON mode, streaming, chat-session persistence) is a deliberate surface
  difference; flattening it would regress UX. The chosen design lets the surface keep
  rendering while delegating execution (`emit_answer=False` in the migration spec).

## References

- ADR 0012 (Reduce Tight Coupling in chat_agent.py) — related coupling concern.
- ADR 0023 (Strict Plan-Before-Write) — governance behavior the controller must preserve.
- `docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md` (CG-11…CG-16).
- `docs/specs/daily-driver-tui-controller-migration-spec-2026-06-01.md` (migration).
- `docs/analysis/daily-driver-surface-parity-matrix-2026-06-01.md` (parity evidence).
- `docs/daily-driver-current-status.md` (current daily-driver truth).
