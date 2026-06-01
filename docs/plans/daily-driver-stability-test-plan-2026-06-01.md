# Daily-Driver Stability Test Plan

Date: 2026-06-01

Purpose: define the test and verification shape needed before TeaAgent should be
recommended for daily TUI, chat, or agent-mode use.

## Test Strategy

Use a layered strategy:

1. Unit tests for state helpers and command parsing.
2. Handler tests for real CLI/TUI entry points.
3. Headless TUI tests for first-hour workflows.
4. Git integration tests for sandbox and undo behavior.
5. Documentation consistency tests that fail when readiness docs drift.

## Required Test Cases

### Chat Entry

| Case | Expected |
|---|---|
| `teaagent chat "do thing"` | Executes the task or returns a deliberate unsupported-syntax error. |
| `teaagent chat --from-plan plan.md` | Loads plan task or clearly rejects invalid path. |
| Missing provider with configured default | Uses config default consistently. |
| Missing provider without default | Error gives next setup action. |

### TUI Chat

| Case | Expected |
|---|---|
| Successful run with `cost_cents=123` | `/cost` reports `$1.23`; `/budget` includes the same total. |
| Two successful runs | Session cost is cumulative. |
| Explicit root with saved global state | Saved root from a previous workspace does not override the root supplied to this run. |
| Failed run | User sees failure reason and no false success summary. |
| Undo after run with journal | Restores recorded files and reports journal id/run id. |
| Undo with no journal | Says no undo is available and suggests recovery options. |
| Compact | Shows before/after observation counts and does not drop last user intent. |

### Agent Mode

| Case | Expected |
|---|---|
| Clean repo without `--git-sandbox` | Branch behavior matches documented default. |
| Clean repo with `--git-sandbox` | Sandbox branch is explicit and shown in output. |
| Dirty repo without auto-stash | Run refuses, asks, or clearly explains risk. |
| Dirty repo with auto-stash | Stash/restore behavior is audited. |
| Non-interactive run | Does not block on prompt and does not surprise users beyond documented default. |

### Background / Resume / Suspend

| Case | Expected |
|---|---|
| `/suspend` or equivalent | Saves checkpoint and states no work continues. |
| True background command | Creates active detached work and exposes attach command. |
| `attach <run_id>` | Shows active run or says run is not active. |
| `resume <run_id>` | Starts a new run from persisted context and records lineage. |

### Permissions And MCP

| Case | Expected |
|---|---|
| Unknown remote MCP tool with no annotations | Prompts before execution. |
| Remote tool claims read-only but writes in test double | Test proves registry policy blocks or requires trust override. |
| Path approval with no path | Refuses path-scoped grant or requires explicit global/tool confirmation. |
| Budget exceeded | Agent stops with remediation, not a generic failure. |
| Cost cap set to `0` | Runtime behavior matches parser help and run summary. |

### Documentation

| Case | Expected |
|---|---|
| Acceptance count validation | `docs/acceptance.md` exactly matches collected acceptance tests. |
| Help snapshot | Help text matches command grammar and lifecycle words. |
| Background/detach wording | Help does not recommend `--detach` unless the parser exposes it. |
| Risk index | Current truth docs appear before historical daily-driver docs. |

## Verification Commands

```bash
python3 -m pytest tests/test_cli_chat.py tests/test_tui.py tests/test_docs_consistency.py -q
python3 scripts/validate_docs_consistency.py
teaagent tool lint --root .
```

Add targeted tests before broad acceptance runs:

- `tests/test_cli_chat_task_entry.py` for `teaagent chat <task>`.
- `tests/test_tui_cost_ledger.py` for real cost accumulation.
- `tests/test_agent_git_sandbox_defaults.py` for branch behavior.
- `tests/test_lifecycle_copy.py` for suspend/background output.
- `tests/test_tui_state_root.py` for explicit root precedence.
- `tests/test_tui_approval_scope.py` for path approval with no path.
- `tests/test_cost_cap_semantics.py` for zero/default/unlimited budget behavior.

## Manual Smoke Script

Run in a disposable repository:

1. `teaagent --help`
2. `teaagent chat "summarize this repo"`
3. In TUI chat, run a read-only task, then `/cost`, `/budget`, `/undo`, `/compact`.
4. Run agent mode with and without `--git-sandbox`.
5. Create a dirty file and verify undo/sandbox behavior.
6. Suspend and resume a session; confirm copy matches behavior.
7. Run docs consistency validation.

## Exit Criteria

The product is stable enough for daily-user recommendation only when all high-severity
tests pass, docs consistency passes, and every remaining medium risk is explicitly
listed in the release notes.
