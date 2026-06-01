# Recovery Recipes
# 2026-06-02

Recipes for stopping, inspecting, resuming, or undoing work.

## Recipe: I have a run id and feel unsure

```bash
teaagent agent show <run_id>
teaagent agent interactive-review <run_id>
```

Do this before resume or undo.

## Recipe: I need to preserve my manual edits

1. Run `git status`.
2. Identify files changed by you vs the agent.
3. Prefer journal-backed undo when available.
4. Avoid checkpoint restore if unrelated edits are present.

## Recipe: The TUI says background

Treat it as suspended unless you can prove work is still running.

Next command:

```bash
teaagent agent show <run_id>
```

## Recipe: Resume failed

1. Do not retry blindly.
2. Inspect `agent show`.
3. Inspect run/audit files if available.
4. Use interactive review if changed files exist.
5. File the run id under TICKET-16 follow-up.

## Recipe: Approval got too broad

1. Reject or revoke.
2. Restart with narrower permission mode.
3. Ask for a plan that lists exact paths.

## Recipe: Cost looks impossible

1. Check run summary.
2. Check provider dashboard.
3. Treat false zero as a display issue.
4. Add active-path test before closing the issue.
