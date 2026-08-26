# TUI Daily-Driver Guide
# As of 2026-06-21

> **Claim class:** User guide — operational steps for the TUI daily loop.
>
> **Owns:** Commands, safe defaults, and recovery pointers for TUI operators.
>
> **Does not own:** Roadmap horizons (`roadmap-status.md`), ticket execution
> steps (`plans/ticket-plans/index.md`), or historical review prose in dated analysis files.
>
> **Review trigger:** TUI operator loop or recovery pointers change.
> **Last reviewed:** 2026-08-26 (reviewed against EFX-002 ambient-warning and fail-closed approvals; no drift found — cockpit warnings surface harness-health lines automatically)

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
- Cost displays reflect session spend via `ChatSessionController` after TICKET-12.
- Run ids are the durable handle for audit and recovery.
- Approval rows should be read as security boundaries, not convenience buttons.

## Safe defaults

- Prefer prompt-mode approvals for unfamiliar repositories.
- Prefer path-scoped approvals over broad grants.
- Use `/cost` and `/budget` for controller-backed session figures; confirm the
  provider exposes usage data before treating either value as a billing total.
- Prefer `teaagent agent interactive-review <run_id>` when a suspended run needs careful inspection.
- Treat `/background` in the REPL or TUI as a suspension checkpoint, not proof that work
  continues in the background.

## If something goes wrong

See [Recovery And Continuity Guide](recovery-and-continuity-guide.md) for undo, resume, and failure recovery paths.

## Operational limits

| Limit | Current behavior | Operator action |
|-----|------------------|-----------------|
| Provider omits usage data | Controller cost can remain unavailable or incomplete | Check the run summary and provider dashboard before making billing claims. |
| Journal has no eligible run | `/undo` reports `nothing to undo` and does not fall back to a global checkpoint | Select an explicit run id or recover through normal git review. |
| Background command vocabulary | `/background` suspends and records a checkpoint; it does not promise detached execution | Use the returned run id with show, resume, or interactive review. |
| Explicit root required for operator certainty | `--root` takes precedence over saved state | Keep passing `--root .` and verify the visible root before writes. |

## When to switch to CLI

Switch to `teaagent chat` when a line-oriented conversational workflow is more useful
than the cockpit panels.

Switch to `teaagent agent run` when the task is non-interactive, reviewable, and should produce an audit trail.

Switch to `teaagent agent interactive-review <run_id>` when you need to inspect a run before continuing or accepting changes.
