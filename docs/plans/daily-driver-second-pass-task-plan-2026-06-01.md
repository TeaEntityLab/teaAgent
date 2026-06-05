# Daily-Driver Second-Pass Task Plan

> Supersession note, 2026-06-05: This file is historical evidence from the
> second daily-driver review pass. The tasks were absorbed into the P0-A
> through P1-D workstreams in
> `docs/plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md`. For
> implementation status, use `docs/plans/ticket-plans/index.md`.

Date: 2026-06-01

Goal: convert the latest second-pass review into small reviewable engineering
tasks that make TeaAgent safer and more useful for daily TUI, TUI chat, and agent
mode usage.

## Definition Of Ready

A task is ready when it has a failing or missing test identified, a narrow code
surface, and a user-facing acceptance statement.

## Phase A: Stop First-Hour Trust Failures

### TASK-DD2-001: Execute Or Reject `teaagent chat <task>`

- Goal: remove silent task drop from the chat entry point.
- Scope: `teaagent/cli/_handlers/_chat.py`, `teaagent/tui/__init__.py`,
  parser tests, and handler tests.
- Acceptance Criteria:
  - `teaagent chat "task"` either executes the task before opening chat or
    exits with a clear unsupported-syntax error.
  - The test asserts the active CLI handler path, not only parser shape.
  - `--from-plan` has the same execute-or-reject contract.
- Tests:
  - Add a handler-level test with mocked `run_chat_agent` or mocked
    `TeaAgentTUI._run_agent_task`.
  - Add a CLI parser/normalization test for task/provider order.
- Risk: high, because this changes first-run behavior.
- Parallelizable: yes, if tests and implementation are split carefully.
- Human Review Required: no, unless the product chooses to reject the syntax.

### TASK-DD2-002: Keep Explicit TUI Root Explicit

- Goal: prevent global TUI state from moving the user into an old workspace.
- Scope: `teaagent/tui/__init__.py` state load/save and TUI tests.
- Acceptance Criteria:
  - If a root is passed by CLI/constructor, saved global state does not override
    it.
  - Saved root can still be used when no explicit root was supplied.
  - Help or state output makes the active root visible.
- Tests:
  - State file contains root A, construct TUI with root B, run load, assert root B.
  - No explicit root path, saved root A, assert root A is restored.
- Risk: high for daily safety, moderate compatibility risk.
- Parallelizable: yes.
- Human Review Required: no.

### TASK-DD2-003: Make TUI Cost Real

- Goal: make `/cost`, `/budget`, and run summaries come from one cost ledger.
- Scope: `teaagent/tui/__init__.py`, `teaagent/chat_session_controller.py`
  if routing TUI through the controller, and TUI tests.
- Acceptance Criteria:
  - One successful run with `cost_cents=123` makes `/cost` show `$1.23`.
  - Two successful runs accumulate cost.
  - Failed runs do not report false success or fake spend.
  - Budget remaining uses the same session total.
- Tests:
  - Add a direct `_run_agent_task()` mocked-result test.
  - Add a command-flow test that runs a task then `cost` and `budget`.
- Risk: high, because cost visibility is a core trust feature.
- Parallelizable: partly; tests can be written before implementation.
- Human Review Required: no.

## Phase B: Repair Branch, Undo, And Permission Contracts

### TASK-DD2-004: Define And Enforce Git Sandbox Semantics

- Goal: make branch switching match the flag, config, and docs.
- Scope: `teaagent/cli/_agent_parsers.py`, `teaagent/cli/_handlers/_agent.py`,
  git sandbox tests, CLI docs.
- Acceptance Criteria:
  - The product chooses one contract: opt-in sandbox, auto sandbox by default, or
    prompt/consent sandbox by default.
  - The `--git-sandbox` flag and docs match that contract.
  - The initialized sandbox object is preserved through merge, discard, keep,
    rollback, and stash restore.
  - Output names the original branch and sandbox branch.
- Tests:
  - Clean repo with and without flag.
  - Dirty repo with and without auto-stash.
  - Non-interactive stdin.
  - Merge prompt uses a non-null original branch.
- Risk: high; branch movement is scary for users.
- Parallelizable: no, because behavior and docs must move together.
- Human Review Required: yes for default behavior.

### TASK-DD2-005: Reject Path Approval When No Path Exists

- Goal: prevent path-scoped approval from silently becoming global approval.
- Scope: `teaagent/tui/__init__.py`,
  `teaagent/ergonomics/_approval_grants.py`, approval tests.
- Acceptance Criteria:
  - Choosing path approval with no path prints a clear refusal.
  - A global/tool-wide grant requires a separate explicit confirmation or option.
  - Tests prove empty path globs are not created by the path option.
- Tests:
  - TUI approval request with no path and answer `p`.
  - Approval store check for grant with no path globs.
- Risk: medium security and UX risk.
- Parallelizable: yes.
- Human Review Required: yes if global grant behavior changes.

### TASK-DD2-006: Split `undo` From `checkpoint restore`

- Goal: make recovery language predictable.
- Scope: TUI help, `teaagent/tui/_commands.py`, `TeaAgentTUI._handle_undo`,
  CLI undo docs.
- Acceptance Criteria:
  - `undo [run_id]` means run-journal undo.
  - `checkpoint restore` or another explicit command means checkpoint rollback.
  - TUI dispatch has no unreachable undo branch.
  - Help text has one primary recovery story.
- Tests:
  - Command-dispatched `undo` with journal.
  - Command-dispatched `undo` without journal.
  - Checkpoint restore uses the checkpoint path.
- Risk: medium.
- Parallelizable: yes.
- Human Review Required: no.

## Phase C: Normalize Lifecycle And Cost Semantics

### TASK-DD2-007: Replace `--detach` References Or Implement Alias

- Goal: remove background command drift.
- Scope: TUI help, chat REPL output, docs, parser alias if chosen.
- Acceptance Criteria:
  - Every help surface uses either `--background` or a real `--detach` alias.
  - `/background` and `/suspend` copy distinguishes active work from checkpoints.
  - Tests assert no help surface recommends a nonexistent flag.
- Tests:
  - Snapshot or text tests for TUI help, chat help, CLI docs snippets.
- Risk: medium.
- Parallelizable: yes.
- Human Review Required: no.

### TASK-DD2-008: Choose One Meaning For Cost Cap Zero

- Goal: make `0`, default budget, and unlimited budget unambiguous.
- Scope: parser help, `RunBudget`, `ChatAgentConfig`, run summary, docs.
- Acceptance Criteria:
  - `0` is documented and implemented as exactly one of:
    - unlimited/no cap, or
    - use configured default.
  - Run summary reports the real effective cap.
  - TUI and CLI use the same language.
- Tests:
  - Parser help text test.
  - Budget preflight test for zero.
  - Run summary effective-cap test.
- Risk: medium.
- Parallelizable: yes after the decision.
- Human Review Required: yes for product semantics.

### TASK-DD2-009: Retire Or Quarantine Stale Chat REPL Code

- Goal: make tests and runtime target the same implementation.
- Scope: `teaagent/cli/_handlers/_chat.py`,
  `teaagent/cli/_handlers/chat_repl.py`, imports, tests.
- Acceptance Criteria:
  - There is one canonical chat execution path.
  - Stale placeholder-cost and fallback-undo code is removed or unreachable by
    construction.
  - Tests fail if the CLI imports the old path.
- Tests:
  - Import-path test for `chat_command`.
  - Coverage or direct assertion that canonical controller is used.
- Risk: medium.
- Parallelizable: no if deleting code; yes if first adding import guards.
- Human Review Required: yes before deletion.

## Phase D: Strengthen Proof

### TASK-DD2-010: Expand Docs Consistency Count Guard

- Goal: make `docs/acceptance.md` harder to drift.
- Scope: `tests/acceptance/test_docs_acceptance_count_accuracy.py`,
  `scripts/validate_docs_consistency.py`, docs.
- Acceptance Criteria:
  - Both `Current acceptance test count: N tests collected` and ``N passed``
    match pytest collection.
  - Failure message names the generator command.
- Tests:
  - Unit test around sample docs text.
  - Existing acceptance count test.
- Risk: low.
- Parallelizable: yes.
- Human Review Required: no.

### TASK-DD2-011: Replace Weak Headless TUI Smoke Tests

- Goal: turn no-throw checks into daily-driver proof.
- Scope: `tests/acceptance/test_headless_tui.py`.
- Acceptance Criteria:
  - Tests assert output payloads, active root, cost state, session persistence,
    and command dispatch.
  - The pty helper either drives stdin/stdout or is renamed to avoid false
    confidence.
- Tests:
  - Headless command sequences for help, daily, chat task, cost, undo, and exit.
- Risk: low.
- Parallelizable: yes.
- Human Review Required: no.

## Recommended Execution Order

1. TASK-DD2-001
2. TASK-DD2-002
3. TASK-DD2-003
4. TASK-DD2-004
5. TASK-DD2-005
6. TASK-DD2-007
7. TASK-DD2-008
8. TASK-DD2-006
9. TASK-DD2-009
10. TASK-DD2-010
11. TASK-DD2-011

## Definition Of Done

- All high-risk tasks have tests that hit the same entry point users run.
- Help text and docs no longer recommend nonexistent flags.
- TUI shows the root, cost, budget, and recovery state truthfully.
- Agent mode branch behavior is explicit before work starts.
- Docs consistency validation passes.

