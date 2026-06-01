# Daily-Driver Hardening Plan — TUI / Chat / Agent
# 2026-06-01

**Goal (Why).** Make teaagent trustworthy as a *daily driver* in its three operator
surfaces, by fixing the code-level defects found in
`docs/analysis/daily-driver-code-grounded-ux-findings-2026-06-01.md`. Trust, not
capability, is the limiting factor for adoption (2026-05-31 survey, Stack Overflow
2025: "willing but reluctant").

**Scope (What).** Behavioral correctness of `teaagent chat`, the TUI, and the shared
agent run path. **Out of scope:** new features, new surfaces (IDE/desktop/cloud — see
the May-31 roadmap), model/provider work.

**Done (acceptance).** Every item below has a falsifiable test. The phase is "done"
when its tests pass in CI and a manual smoke (`teaagent chat`, `teaagent tui`) shows
the corrected behavior.

**Sequencing rationale.** P1-3 (shared controller) is listed in Phase 2, but P0-1 and
P0-2 are *also* implementable directly in `chat_repl.py` without waiting for the
refactor. Ship the P0 fixes first (small, safe, high-impact), then do the refactor so
the fixes stop diverging (CG-05).

---

## Phase 0 — P0 correctness (ship first, no refactor required)

### P0-1 — REPL displays answers and reports status correctly  (fixes CG-01)
- **Change.** In `chat_repl.py` interactive loop (~`:816-827`), replace
  `if result != 0:` with status-based handling mirroring the initial-task path
  (`:557-560`) and the TUI (`tui/__init__.py:859-861`):
  print `result.final_answer.content` on `result.status == 'completed'`, print a real
  error on other statuses, and append the turn to `session_context`.
- **Acceptance.**
  - New test `tests/.../test_chat_repl_displays_answer.py`: drive `run_chat_repl` with
    a stub adapter returning a known `final_answer`; assert the answer text appears in
    captured stdout and that no "Task failed" line is printed on success.
  - Negative test: a `RunResult` with `status='failed'` prints a failure line
    *with the error message*, not a `RunResult` repr.
- **Falsifiability.** If a successful task still prints "Task failed", the fix is wrong.

### P0-2 — REPL undo cannot destroy un-agented work  (fixes CG-02)
- **Change.** Remove the `git checkout -- .` calls (`chat_repl.py:418` and the
  fallback `:789-799`). Route `/undo` through the run's `UndoJournal` (as the TUI/agent
  path does) or restore only checkpoint-captured files. If nothing is recoverable,
  print a clear "nothing to undo" instead of reverting the worktree.
- **Acceptance.**
  - New test: seed the worktree with a manual edit to file A, run a task that edits
    file B, call `/undo`; assert A is unchanged and only B is reverted.
  - Test that `/undo` with no checkpoint and no journal is a no-op (worktree byte-identical before/after).
- **Falsifiability.** If any file the agent did not write is modified by `/undo`, the
  fix is wrong.

---

## Phase 1 — P1 trust & accuracy

### P1-1 — Real cost/budget accounting  (fixes CG-03)
- **Change.** After each run in both surfaces, increment the session cost from
  `result.cost_cents` (REPL `:825` placeholder removed; TUI `_run_agent_task` updates
  `self._session_cost_cents`). Surface `input_tokens` / `output_tokens` and, where the
  adapter reports it, cached-token counts. Label the number as server-reported
  (per Hermes #504 / Delta D-1).
- **Acceptance.** Stub adapter reports `cost_cents=137`; after one task `/cost` shows
  `$1.37` (not `$0.00`, not `$0.10`); after two tasks shows the sum. Same assertion in
  TUI via injected `input_fn`/`output_fn`.

### P1-2 — Operator-visible compaction acts on real history  (fixes CG-04)
- **Change.** Record each turn into `session_context['observations']` in the loop
  (coupled to P0-1). Make `/clear` and `/compact` operate on populated history.
- **Acceptance.** Run 3 tasks, assert `len(observations) == 3`; `/compact` reports
  `tokens_saved > 0` and a retained-count consistent with the compactor config;
  `/clear` resets to 0.

### P1-3 — Shared `ChatSessionController`  (fixes CG-05)
- **Change.** Extract result-handling, cost accounting, undo scope, session memory, and
  effort/budget into one controller consumed by both `run_chat_repl` and
  `TeaAgentTUI`. Surfaces retain only input/output. Fold P0-1, P0-2, P1-1, P1-2 into
  the controller so they cannot diverge again.
- **Acceptance.** Parity test parametrized over both surfaces: same stubbed task →
  same status, same displayed answer, same cost, same undo scope. (Directly satisfies
  survey gap **F-ECO-010** "CLI/TUI parity for the same run state".)

### P1-4 — TUI panel stops destroying scrollback  (fixes CG-06)
- **Change.** Replace the per-prompt `\033[2J\033[H` clear + vertical "panels" with
  either (a) a prompt_toolkit full-screen `Application` with a fixed state region and a
  scrollable, never-cleared chat buffer, or (b) make the state panel an opt-in `state`
  command and drop auto-activation. Do **not** auto-clear on large terminals.
- **Acceptance.** Test that handling a command followed by rendering does not emit a
  clear-screen sequence in default operation; manual check on a ≥120×30 terminal that
  prior answers/approvals remain visible after the next prompt.

---

## Phase 2 — P2 consistency

### P2-1 — One undo vocabulary  (fixes CG-07, CG-08)
- **Change.** After P1-3, make `UndoJournal` the single operator-facing `undo`; rename
  the git-stash mechanism to `checkpoint restore`. Wire TUI `compact` to the shared
  compactor (removes the CG-07 stub). Update help text in both surfaces and
  `docs/USAGE.md` / `docs/cli.md` to describe exactly one undo and what it reverts.
- **Acceptance.** Help text in TUI, REPL, and docs all describe the same undo scope;
  `compact` no longer prints "not yet implemented"; doc-lint passes.

---

## Verification matrix

| Item | Fixes | Test artifact | Survey theme closed |
|---|---|---|---|
| P0-1 | CG-01 | `test_chat_repl_displays_answer` | UX-F4, UX-F5 |
| P0-2 | CG-02 | `test_chat_repl_undo_scope` | UX-F4 |
| P1-1 | CG-03 | `test_session_cost_real` (both surfaces) | UX-F1, UX-F6 |
| P1-2 | CG-04 | `test_repl_compaction_real_history` | UX-F3 |
| P1-3 | CG-05 | `test_chat_surface_parity` | F-ECO-010 |
| P1-4 | CG-06 | `test_tui_no_clear_screen` | UX-F3 / Delta D-2 |
| P2-1 | CG-07, CG-08 | `test_undo_vocabulary` + doc-lint | UX-F4 |

## Estimated effort `[inference]`

- Phase 0: small (two localized edits + two tests). Highest impact-to-effort.
- Phase 1: P1-1/P1-2 small once P0-1 lands; P1-3 medium (refactor); P1-4 medium
  (genuine TUI layout work).
- Phase 2: small (rename + docs).

## Risks of *doing* this work

Tracked in `docs/analysis/daily-driver-risk-register-2026-06-01.md`. Headline: the
P1-3 refactor touches both daily surfaces at once — gate it behind the parity test and
keep P0 fixes shippable independently so a refactor slip never blocks the P0s.
</content>
