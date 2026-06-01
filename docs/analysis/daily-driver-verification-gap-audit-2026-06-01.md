# Daily-Driver Verification Gap Audit

Date: 2026-06-01

Purpose: identify where existing tests give confidence and where they mostly test
helpers, display plumbing, or stale paths rather than daily-driver behavior.

## Verification Summary

The repo has strong test volume and current acceptance counts appear up to date,
but daily-driver confidence is uneven. The main gap is not "no tests"; it is that
some tests assert parser shape, helper behavior, or no-throw smoke paths while the
real user entry points still diverge.

## Current Evidence

| Surface | Evidence that helps | Gap that remains |
|---|---|---|
| `teaagent chat` | Parser accepts task-first chat syntax in tests. | No test proves the active handler executes or rejects the supplied initial task. |
| Controller-backed REPL | `chat_repl.py` tests exercise cost, undo, suspension, provider/model commands. | The active `chat_command` import is from `_chat.py`, not `chat_repl.py`. |
| TUI run | Tests assert budget config is passed to `run_chat_agent`. | Tests do not assert `_session_cost_cents` changes after a run result. |
| Agent git sandbox | Primitive `GitBranchSandbox` tests exist. | CLI-level tests do not prove default branch behavior with and without `--git-sandbox`. |
| Acceptance docs | `docs/acceptance.md` currently has 432 collected and 432 passed. | Count guard checks the passed marker but not the headline collected marker. |
| Headless TUI | Many commands are smoke-tested. | Several tests assert true/no exception rather than user-visible state or persistence. |

## High-Value Missing Tests

### VG-001: Active Chat Entry Initial Task

Test name proposal: `test_chat_command_initial_task_executes_or_rejects`

Assertions:

- Build the real CLI args for `teaagent chat "summarize"`.
- Call the actual `chat_command` path.
- Assert either a mocked run receives `summarize` or output says positional tasks
  are unsupported.
- Assert the command does not silently open a blank chat shell.

### VG-002: TUI Cost Ledger

Test name proposal: `test_tui_run_updates_session_cost_and_budget`

Assertions:

- Mock `run_chat_agent` to return `cost_cents=123`.
- Run a TUI task through command dispatch.
- Run `cost` and `budget`.
- Assert `$1.23` appears and remaining budget reflects the same total.

### VG-003: TUI Explicit Root Beats Saved Root

Test name proposal: `test_tui_explicit_root_not_overwritten_by_global_state`

Assertions:

- Write a fake TUI state file with root A.
- Construct TUI with root B.
- Load state.
- Assert root B is still active when root was explicit.

### VG-004: Agent Sandbox CLI Contract

Test name proposal: `test_agent_run_git_sandbox_default_contract`

Assertions:

- In a clean temp git repo, run agent handler with no `--git-sandbox`.
- Assert branch behavior matches the chosen documented contract.
- Repeat with `--git-sandbox`.
- Assert the same initialized sandbox object supplies original branch and stash
  state for merge/discard/keep.

### VG-005: Approval Path Without Path

Test name proposal: `test_tui_path_approval_without_path_does_not_grant_global`

Assertions:

- Create an approval request with no path argument.
- Answer `p`.
- Assert no broad grant is registered.
- Assert output asks for explicit tool/global approval if that is supported.

### VG-006: Lifecycle Help Flag Consistency

Test name proposal: `test_lifecycle_help_does_not_reference_missing_detach_flag`

Assertions:

- Scan TUI help, chat REPL help, and docs snippets.
- If parser has `--background` but no `--detach`, assert no help recommends
  `--detach`.
- If `--detach` is added as an alias, assert parser and docs both include it.

### VG-007: Acceptance Count Headline Guard

Test name proposal: `test_acceptance_doc_collected_count_matches_pytest_collect`

Assertions:

- Parse `Current acceptance test count: N tests collected`.
- Parse ``N passed``.
- Assert both equal pytest collection.

## Weak Tests To Reclassify

These tests still have value as smoke tests, but should not be treated as daily
readiness proof:

- `tests/acceptance/test_headless_tui.py:81` setup availability only asserts the
  handler returns true.
- `tests/acceptance/test_headless_tui.py:19` names a pty helper, but the helper
  does not drive commands through the pty.
- Tests that manually set `_session_cost_cents` prove formatting, not run
  accounting.
- Parser tests for chat task shape prove grammar, not execution.

## Verification Policy Update

For daily-driver claims, every critical behavior should have at least one test in
each category:

1. Parser or command grammar.
2. Runtime handler path.
3. User-visible output.
4. Persisted state or audit evidence when state changes.

If a test covers only one category, docs should call it a unit or smoke test, not
readiness evidence.

## Recommended Command Set

Use this focused command set for the next implementation pass:

```bash
python3 -m pytest tests/test_cli_chat.py tests/test_tui.py tests/acceptance/test_headless_tui.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
python3 scripts/validate_docs_consistency.py
teaagent tool lint --root .
```

Add git sandbox CLI integration tests before running broad acceptance, because
branch behavior needs isolated temp repositories and careful cleanup.

