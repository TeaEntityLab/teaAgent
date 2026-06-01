# Daily-Driver UX Contract Drift

Date: 2026-06-01

Purpose: document places where TeaAgent's words, flags, or displays promise a
different behavior than the code currently delivers.

## UX Contract Principle

For daily users, a command-line agent should be boringly literal:

- If a command accepts a task, it should run the task or reject it.
- If a cost is shown, it should be real.
- If a permission says path-scoped, it should not become global.
- If a command says background, work should continue after exit.
- If a root is supplied, commands should target that root.
- If a branch can change, the user should know before it changes.

## Drift Register

| ID | Contract promised | Current drift | User harm | Fix direction |
|---|---|---|---|---|
| UXD-001 | `teaagent chat <task>` accepts a task. | The task can be dropped because the active handler opens TUI chat without initial task support. | First command feels broken or ignored. | Execute initial task or reject syntax. |
| UXD-002 | TUI `/cost` shows session cost. | The value is not incremented after `_run_agent_task()`. | Users cannot judge spend. | Share the controller ledger or update TUI ledger. |
| UXD-003 | `--git-sandbox` is opt-in. | Agent mode can start sandboxing without that flag. | Branch surprise and confusing merge prompts. | Define and enforce default. |
| UXD-004 | A saved TUI state helps resume work. | Saved global root can override the explicit current workspace. | Commands may hit the wrong project. | Make explicit root higher priority than global state. |
| UXD-005 | Path approval scopes to a path. | Missing path creates a grant with no path globs, which matches all paths. | Narrow approval becomes broad authority. | Refuse path approval without a path. |
| UXD-006 | Background means continued execution. | Suspension helper says no background work, caller/help still use background/detach language inconsistently. | Users may exit expecting work to continue. | Separate suspend checkpoint from background worker. |
| UXD-007 | `0` cost cap has one meaning. | Parser says default budget, runtime treats zero as no cap, summaries can report default. | Users misconfigure cost safety. | Pick one semantic and test it. |
| UXD-008 | Undo means one recovery action. | TUI help and dispatch mix run-journal undo and checkpoint restore. | Users cannot predict recovery scope. | Rename checkpoint restore and keep undo run-scoped. |

## Words To Reserve

| Word | Should mean | Should not mean |
|---|---|---|
| `chat` | Interactive conversation, optionally with an initial executed task. | A shell that silently discards an accepted task. |
| `run` | One autonomous task with visible result, cost, audit, and recovery state. | A hidden branch/state transition. |
| `background` | A detached active worker that can be listed and attached. | A saved checkpoint where no work continues. |
| `suspend` | Save current session state for later manual resume. | Detached execution. |
| `resume` | Start a new run from persisted context or previous run state. | Attach to a live process. |
| `attach` | Stream or inspect an active or persisted run by run id. | Re-run a task. |
| `undo` | Restore files from a run-scoped undo journal. | Restore an unrelated checkpoint. |
| `checkpoint` | Explicit local state snapshot. | General undo. |

## Daily-Use Copy Rules

1. Every command that can change branch prints the current branch and target branch
   before changing state.
2. Every command that saves state but does not continue execution says "no work is
   running after this command."
3. Every approval prompt says the exact grant scope before accepting the response.
4. Every cost display says whether it is actual, estimated, unavailable, or
   unlimited.
5. Every command that uses saved state prints the active root.

## Highest-Priority UX Tests

- `teaagent chat "task"` executes or rejects.
- TUI with explicit root B does not load saved root A.
- Path-scoped approval with no path does not create a global grant.
- Help text has no `--detach` references unless parser exposes that flag.
- `/background` and `/suspend` have different words and different behavior.
- `/cost` changes after a mocked run result with nonzero cost.

## Decision

Do not market TUI chat or agent mode as daily-ready until the drift register is
resolved or each remaining drift has an explicit known-gap note in release docs.

