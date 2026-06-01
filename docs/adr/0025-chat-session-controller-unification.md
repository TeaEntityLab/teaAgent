# ADR 0025: Shared ChatSessionController for Chat Surfaces

## Status

Accepted and Implemented (Partial) - 2026-06-01

- **REPL (`teaagent chat`):** Implemented.
- **TUI (`teaagent tui`):** Not yet migrated (see Consequences → Outstanding).

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
- `teaagent/chat_session_controller.py` (new, ~229 lines)
- `teaagent/cli/_handlers/chat_repl.py` (initial-task path and REPL loop now call
  `controller.execute_task`; `/undo` calls `controller.undo_last_run`)

**Features:**
- One result-handling, cost, and undo implementation for the REPL.
- Honest, audited suspension (`audit.record('session_suspended', …)`, no branch switch)
  retained in `chat_repl.py` (CG-09/CG-10).

## Rationale

A single execution path is the only durable fix for drift: it converts "remember to fix
both surfaces" into "fix it once." It also concentrates the governance-critical behavior
(audit, undo, cost) where it can be tested in isolation, independent of terminal I/O.

## Implementation

Implemented for the REPL in the 2026-06-01 fix batch. Verified by the third-pass audit
(`docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md`): CG-01/02/03(REPL)/
04/09/10 confirmed fixed against current HEAD.

## Consequences

### Positive
- REPL result/cost/undo are correct and governed.
- New chat behavior added to the controller benefits the REPL automatically.
- Governance behavior is unit-testable without a TTY.

### Negative / Outstanding
- **The TUI was not migrated** and still calls `run_chat_agent` directly
  (`tui/__init__.py:890`). Consequently the controller's guarantees do **not** reach the
  always-on surface:
  - CG-11: TUI `/cost` always shows `$0.00` (counter never incremented).
  - CG-12: the divergence the controller was meant to end is still active for the TUI.
  - CG-15: TUI `/undo` uses git-stash while the REPL uses `UndoJournal`.
- **`execute_task` swallows `(AttributeError, TypeError)`** to detect test mocks
  (`:143-159`), which can silently hide a real undo-journal save failure (CG-13).

The migration path is specified in
`docs/specs/daily-driver-tui-controller-migration-spec-2026-06-01.md` (TICKET-12); the
parity contract is the enforcement mechanism.

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
