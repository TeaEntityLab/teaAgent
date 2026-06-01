# Daily-Driver Second Pass After Code Improvements

Date: 2026-06-01

Scope: current repo state after recent code improvements, focused on daily TUI,
TUI chat, `teaagent chat`, and `agent run` behavior.

## Purpose

This addendum captures facts discovered after the earlier June 1 review package.
Some findings are now fixed or narrowed, but several daily-driver risks remain
active because the improved code path is not always the path users actually run.

## Improved Or Fixed Facts

| Area | Current fact | Evidence | Remaining concern |
|---|---|---|---|
| Controller-backed chat | `ChatSessionController` now records cost, observations, and undo journals. | `teaagent/chat_session_controller.py:161`, `teaagent/chat_session_controller.py:168`, `teaagent/chat_session_controller.py:182` | The default `teaagent chat` handler does not route through this controller directly. |
| Chat REPL suspension helper | `chat_repl.py` no longer creates and switches to a suspension branch. It emits a `session_suspended` audit event and says the checkpoint is not background execution. | `teaagent/cli/_handlers/chat_repl.py:105`, `teaagent/cli/_handlers/chat_repl.py:125`, `teaagent/cli/_handlers/chat_repl.py:140` | The REPL caller still prints conflicting background language. |
| Controller-backed undo | The controller path restores `UndoJournal` entries instead of using a blanket git checkout fallback. | `teaagent/chat_session_controller.py:182` | TUI command-dispatched undo still has split help and unreachable checkpoint semantics. |
| TUI compact | TUI compact is implemented for saved chat sessions. | `teaagent/tui/__init__.py:720` | It still needs a user-visible kept/dropped preview before daily readiness claims. |
| TUI split pane | The old "clear screen every prompt" concern is stale. | `teaagent/tui/__init__.py:364` | Large terminals still get an auto-rendered state panel every prompt, which can be noisy. |
| Acceptance count | `docs/acceptance.md` currently says 432 collected and 432 passed. | `docs/acceptance.md:24`, `docs/acceptance.md:144` | The guard checks only the passed marker, not the headline collected count. |

## Still Active High-Risk Facts

### DD-SP-001: `teaagent chat <task>` Still Drops The Initial Task

The parser accepts a task-first chat grammar, but `chat_command()` delegates to
`run_tui(chat=True)` without forwarding `args.task`, and `run_tui()` has no
initial-task parameter.

Evidence:

- `teaagent/cli/_agent_parsers.py:61` defines task-first chat arguments.
- `teaagent/cli/_handlers/_chat.py:538` implements the active chat handler.
- `teaagent/tui/__init__.py:1195` defines `run_tui()` without `initial_task`.

User impact: a first-hour user can run `teaagent chat "summarize this repo"` and
land in an interactive shell without the task being executed. That is a trust
failure, not just a missing feature.

### DD-SP-002: TUI Cost Is Still Display-Only After Real Runs

TUI receives `result.cost_cents` and includes it in the run summary, but it does
not add that value to `_session_cost_cents`. `/cost` and `/budget` can therefore
stay at zero after paid model calls.

Evidence:

- `teaagent/tui/__init__.py:186` initializes `_session_cost_cents`.
- `teaagent/tui/__init__.py:743` displays `_session_cost_cents`.
- `teaagent/tui/__init__.py:890` calls `run_chat_agent()` directly.
- `teaagent/tui/__init__.py:934` passes `result.cost_cents` into summaries.

User impact: the primary daily surface can show false spending information.

### DD-SP-003: Agent Git Sandbox Contract Is Still Unsafe

The parser exposes `--git-sandbox` as if sandboxing is opt-in, but
`_execute_agent_task()` creates and starts `GitBranchSandbox` whenever a git repo
is available under consent/non-interactive logic. It also creates the sandbox as
`pending`, then re-creates a new object with `result.run_id` for merge prompts,
losing `_original_branch` and stash state.

Evidence:

- `teaagent/cli/_agent_parsers.py:141` documents `--git-sandbox`.
- `teaagent/cli/_handlers/_agent.py:505` creates the sandbox unconditionally.
- `teaagent/cli/_handlers/_agent.py:518` auto-starts in always/non-interactive paths.
- `teaagent/cli/_handlers/_agent.py:712` re-creates a new sandbox object.

User impact: agent mode can surprise users by switching branches, then give
confusing merge/rollback prompts.

### DD-SP-004: Explicit TUI Root Can Be Overwritten By Global State

TUI stores state globally under `~/.teaagent/tui_state.json`. `_load_tui_state()`
loads and applies the saved `root` over the constructor/root argument. This means
running TUI in project B can silently reopen project A if project A was saved in
global state.

Evidence:

- `teaagent/tui/__init__.py:1093` uses a global user state path.
- `teaagent/tui/__init__.py:1107` overwrites `self.root` from saved state.
- `teaagent/tui/__init__.py:324` loads state during `run()`.

User impact: daily users can issue commands against the wrong workspace.

## New Medium-Risk Facts

### DD-SP-005: Cost-Cap Default Semantics Are Contradictory

The parser says `0 uses default budget`, `RunBudget` treats `<= 0` as no cost
cap, and agent summaries can fall back to `RunBudget().max_estimated_cost_cents`.

Evidence:

- `teaagent/cli/_agent_parsers.py:122` documents the flag.
- `teaagent/budget.py:36` treats `<= 0` as no cap.
- `teaagent/chat_agent.py:523` passes `0` through because it is `>= 0`.
- `teaagent/cli/_handlers/_agent.py:934` reports a default budget when arg is zero.

User impact: cost safety language is not reliable enough for daily usage.

### DD-SP-006: TUI Path Approval Can Become Global Approval

When the TUI approval prompt asks for path-scoped approval, choosing `p` without
an extractable path creates a session grant with no `path_globs`. Empty path
globs match all paths.

Evidence:

- `teaagent/tui/__init__.py:1011` handles path-scoped approval.
- `teaagent/tui/__init__.py:1032` grants without `path_globs` when no path exists.
- `teaagent/ergonomics/_approval_grants.py:154` treats no path globs as match all.

User impact: a user asking for a narrow path grant can silently grant a broader
session permission.

### DD-SP-007: Background And Detach Vocabulary Still Disagree

The codebase currently has at least three lifecycle words for related behaviors:
`background`, `suspend`, and `detach`. `--background` is the parser flag, while
some help text recommends `--detach`, which is not exposed on the agent parser.

Evidence:

- `teaagent/cli/_agent_parsers.py:286` defines `--background`.
- `teaagent/cli/_handlers/chat_repl.py:145` recommends `--detach`.
- `teaagent/tui/__init__.py:111` recommends `--detach`.
- `docs/cli.md:117` documents `--background`.

User impact: users may copy a command that does not exist or misunderstand
whether work continues after exit.

## Decision

Request changes before claiming daily-driver readiness. The improvements are
real, but the active risks are concentrated exactly where daily users enter the
product: first chat command, TUI cost state, root/workspace selection, permissions,
and branch lifecycle.

## Immediate Documentation Follow-Up

- Treat this file as newer than the earlier current-truth audit.
- Keep older findings only when they are still code-true.
- Update task planning around the user-facing entry points, not the internally
  improved but partially disconnected helper paths.

