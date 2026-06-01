# Daily-Driver Surface Parity Matrix
# 2026-06-01

**Purpose.** Make CG-12 (TUI never adopted `ChatSessionController`) *legible* as a single
table: for every daily behavior, what each surface does today, and whether they agree.
"Agree?" = do REPL and TUI give the user the same outcome for the same action. This is
the evidence base for the parity contract in
`daily-driver-tui-controller-migration-spec-2026-06-01.md`.

Surfaces: **REPL** = `teaagent chat` (`cli/_handlers/chat_repl.py`, via
`ChatSessionController`). **TUI** = `teaagent tui` (`tui/__init__.py`, direct
`run_chat_agent`). **Agent** = `teaagent agent run` (non-interactive, not chat).

| Behavior | REPL (chat_repl.py) | TUI (tui/__init__.py) | Agree? | Finding |
|---|---|---|:---:|---|
| Result handling | controller branches on `status`, prints `final_answer` (`:576` / controller `:162`) | branches on `status`, prints `final_answer` (`:958`) | ✅ | CG-01 (both fixed) |
| Session cost `/cost` | `session_state.session_cost_cents += result.cost_cents` (controller `:168`) | `_session_cost_cents` **never incremented** → always $0.00 (`:186` read-only) | ❌ | **CG-11** |
| Cost source of truth | controller `SessionState` | private `self._session_cost_cents` | ❌ | **CG-12** |
| Undo model | `UndoJournal.restore()` (surgical, controller `:182`) | git-stash `_restore_checkpoint` (`:641-708`) | ❌ | **CG-15** |
| Undo when nothing recoverable | "Nothing to undo" (controller `:192`) | "no checkpoint to restore" (`:646`) | ⚠️ wording | CG-15 |
| `/compact` | real `handle_compact` on synced observations (`:622`) | real `compact_chat_history` (`:712`) | ✅ | CG-04 / CG-07 (both fixed) |
| Clear-screen on prompt | n/a (line-oriented) | no clear (`:209`, CG-06 fix) | ✅ | CG-06 (fixed) |
| Suspend / background | honest copy + real `audit.record` (`:129,144`) | `_handle_background` prints a hint only (`:717`) | ⚠️ divergent | CG-09/10 (REPL fixed; TUI minimal) |
| Streaming output | via `config.on_chunk` | via `config.on_chunk` (`:903`) | ✅ | — |
| Approval handler | via `config` | via `config.approval_handler` (`:905`) | ✅ | — |
| Model routing | runtime model in config | `route_model(...)` (`:866`) | ⚠️ TUI-only | (feature, not bug) |
| Run-summary render | none (plain answer) | `format_run_summary` (`:960`) | ⚠️ TUI-only | (richer, not a bug) |
| Persists chat session | no | yes (`ChatSession` save `:956`) | ⚠️ TUI-only | (feature) |
| Calls `run_chat_agent` | indirectly (controller) | **directly** (`:890`, deprecation warning) | ❌ | **CG-12** |

**Legend.** ✅ same outcome · ❌ materially different (bug-class divergence) · ⚠️ differs
by design or wording (not a correctness bug, but track for consistency).

## Reading the matrix

- **Three ❌ rows are bugs** — all are downstream of the single root cause CG-12 (the TUI
  bypasses the controller): cost accumulation, cost source-of-truth, and undo model.
  Closing TICKET-12 collapses all three.
- **⚠️ rows are deliberate surface differences** (the TUI is the richer cockpit) — these
  are fine, but the migration spec preserves them via `emit_answer=False` so delegation
  doesn't flatten the TUI into the REPL.
- **Suspend** is asymmetric: the REPL has the full honest+audited flow (CG-09/10), the
  TUI only prints a hint. Not a correctness bug, but a candidate to unify later.

## Invariant to enforce (post-TICKET-12)

> Every ❌ row becomes ✅; every ⚠️ row stays ⚠️ *only* in the rendering column.

Guard with `test_chat_surface_parity` (see migration spec §4).

## Cross-references
- Root finding: `daily-driver-third-pass-postfix-audit-2026-06-01.md` (CG-11/12/15).
- Fix design: `daily-driver-tui-controller-migration-spec-2026-06-01.md`.
