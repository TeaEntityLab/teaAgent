# TUI Daily-Driver Guide
# As of 2026-06-02

Use this guide when `teaagent tui` is your daily operator cockpit.

## Start the TUI

Recommended command from a project root:

```bash
teaagent tui --setup --root .
```

Recommended habits:

- Pass `--root .` explicitly when you care about which repository is active.
- Run from a clean or intentionally dirty git worktree so undo/recovery behavior is easy to reason about.
- Use a cheap or trusted provider while learning the surface.

## Daily loop

| Step | Command or action | Expected use |
|------|-------------------|--------------|
| 1 | `preflight` | Check local readiness before running an agent task. |
| 2 | `daily` | Run the daily-use health workflow when available. |
| 3 | `ask <question>` | Ask a scoped question against the current project. |
| 4 | `runs` | Inspect recent agent runs and ids. |
| 5 | `approvals pending` | See whether a run is blocked on approval. |
| 6 | `resume <run_id>` or `agent interactive-review <run_id>` from CLI | Continue or review after interruption, depending on the path. |

## Prompt and panel meaning

The TUI should be treated as an operator surface:

- Status panels are prompts to inspect, not proof that a run is complete.
- Cost displays are useful only after the TUI cost migration lands.
- Run ids are the durable handle for audit and recovery.
- Approval rows should be read as security boundaries, not convenience buttons.

## Safe defaults

- Prefer prompt-mode approvals for unfamiliar repositories.
- Prefer path-scoped approvals over broad grants.
- Prefer `teaagent chat` for accurate live chat cost until TICKET-12 lands.
- Prefer `teaagent agent interactive-review <run_id>` when a suspended run needs careful inspection.
- Treat `/background` in the REPL or TUI as a suspension checkpoint, not proof that work
  continues in the background.

## If something goes wrong

See [Recovery And Continuity Guide](recovery-and-continuity-guide.md) for undo, resume, and failure recovery paths.

## Known gaps

| Gap | User-facing symptom | Safer action |
|-----|---------------------|--------------|
| TUI cost not accumulated | `/cost` can remain `$0.00` | Check run summary or provider dashboard. |
| TUI undo differs from REPL undo | `/undo` may restore checkpoint/stash scope instead of journal scope | Create `/checkpoint` before risky work. |
| Saved state can override explicit root | TUI can reopen against stale root | Verify visible root after launch. |
| Controller parity incomplete | REPL and TUI chat behavior can drift | Use REPL for work requiring cost/undo precision. |

## When to switch to CLI

Switch to `teaagent chat` when the task is conversational and trust-sensitive cost or undo matters.

Switch to `teaagent agent run` when the task is non-interactive, reviewable, and should produce an audit trail.

Switch to `teaagent agent interactive-review <run_id>` when you need to inspect a run before continuing or accepting changes.
