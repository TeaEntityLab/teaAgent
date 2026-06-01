# Daily-Driver UX Survey: TUI, Chat, Agent Mode

Date: 2026-06-01

Goal: assess whether TeaAgent is reasonable for daily use by a developer who wants one
reliable terminal companion for quick questions, edit-test loops, and longer agent runs.

## UX Principles

1. The command a user types must do the obvious thing.
2. Every agent action needs a visible owner: foreground chat, background run, suspended
   checkpoint, or resumed run.
3. Trust-sensitive facts must not vary by surface: cost, approval scope, branch, undo
   availability, and last run status.
4. Recovery must be faster than panic.
5. Helpful automation must stop before it becomes surprise authority.

## First-Hour Journey

### Journey A: New User Opens TUI

Expected:

- Setup status is visible.
- Provider/model state is clear.
- The user sees the next useful command.
- Cost/budget and permission mode are not hidden.

Risks:

- TUI setup seeds `daily_cost_cap_cents=0`, which needs clear meaning.
- The state panel is terminal-size gated; small terminals may hide the "cockpit"
  experience described in docs.
- Help text has duplicate/conflicting undo meanings.

### Journey B: User Runs `teaagent chat "fix this"`

Expected:

- The task runs immediately or the CLI explains why it cannot.
- Provider/model defaults are applied consistently.
- The user sees answer, changed files, cost, and undo affordance.

Risks:

- The parser accepts a task for chat, but runtime `chat_command` delegates to TUI without
  forwarding that task.
- Tests cover parsing and controller behavior more than the real `teaagent chat <task>`
  entry point.

### Journey C: User Uses TUI Chat For Repeated Tasks

Expected:

- Each run appends to session context.
- Cost increments after each run.
- Undo applies to the latest run and is previewable or clearly scoped.

Risks:

- TUI calls `run_chat_agent` directly instead of the shared `ChatSessionController`.
- TUI receives `result.cost_cents` but does not update `_session_cost_cents`.
- TUI undo dispatch is journal-first, while help also describes checkpoint undo.

### Journey D: User Runs Agent Mode In A Git Repo

Expected:

- `--git-sandbox` controls whether sandbox branching happens.
- If the project auto-sandboxes, the CLI says that up front and why.
- Non-interactive runs do not surprise-switch branches.

Risks:

- Agent mode initializes and starts `GitBranchSandbox` when available even without the
  `--git-sandbox` flag.
- Non-interactive auto-enablement can be useful, but the flag and docs currently make it
  look opt-in.

### Journey E: User Leaves Work For Later

Expected:

- `suspend` means saved state, no active work.
- `background` means work continues.
- `attach` means observe/control active work.
- `resume` means start again from persisted context.

Risks:

- `/background` calls suspension code but later prints "converted to background task".
- Suggested continuation command includes a run id after `--background`, but parser treats
  `--background` as a boolean flag.

## Severity Matrix

| ID | Severity | Risk | Daily-use failure |
|---|---|---|---|
| UX-001 | High | Chat task accepted then dropped. | First command appears ignored. |
| UX-002 | High | TUI cost ledger is not updated. | Budget/cost display becomes untrustworthy. |
| UX-003 | High | Agent git sandbox auto-starts without flag alignment. | Branch state changes unexpectedly. |
| UX-004 | High | CLI/TUI/chat execution paths diverge. | Fixes and tests protect the wrong surface. |
| UX-005 | Medium | Background/suspend wording conflicts. | User exits expecting work to continue. |
| UX-006 | Medium | Undo vocabulary conflicts. | User hesitates to let the agent edit. |
| UX-007 | Medium | Permission onboarding mixes safety and friction. | Users choose overly broad authority just to reduce prompts. |
| UX-008 | Medium | TUI cockpit contract is under-specified. | Docs promise a cockpit while tests mostly assert line output. |
| UX-009 | Low | Stale docs remain easy to read as current truth. | Planning reopens fixed issues and misses active ones. |

## UX Contract To Write Into Product Docs

For every daily surface, document these fields:

| Field | TUI | TUI chat | CLI chat | Agent mode |
|---|---|---|---|---|
| Current provider/model | Required | Required | Required | Required |
| Permission mode | Required | Required | Required | Required |
| Branch/sandbox state | Required when in git repo | Required when in git repo | Required when in git repo | Required |
| Session/run cost | Required | Required | Required | Required |
| Daily budget/cap | Required if configured | Required if configured | Required if configured | Required if configured |
| Last run status | Required | Required | Required | Required |
| Undo availability | Required | Required | Required | Required |
| Background/suspend state | Optional | Required when invoked | Required when invoked | Required |
| Active skills/rules/memory | Required | Required | Required | Required |

## UX Survey Conclusion

The product can become a useful daily companion, but only after the command grammar and
state model are unified. The most valuable next UX work is not a prettier TUI; it is
making the same truth appear everywhere.

