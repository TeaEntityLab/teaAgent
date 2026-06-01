# Agent Mode Recipes
# 2026-06-02

Practical recipes for `teaagent agent` daily use.

## Recipe: Inspect without writes

```bash
teaagent agent run "inspect current docs risks without editing" --permission-mode prompt
```

Expected:

- No write tools approved unless you explicitly approve them.
- Final answer separates findings from assumptions.
- Audit evidence exists for any tool calls.

## Recipe: Edit a narrow docs area

```bash
teaagent agent run "update the daily-driver troubleshooting doc for TUI cost caveats" --permission-mode prompt
```

Approve only the target docs path.

## Recipe: Review a run

```bash
teaagent agent show <run_id>
teaagent agent interactive-review <run_id>
```

Use this when:

- A run was interrupted.
- The final answer sounds broader than the diff.
- You need to inspect changed files before accepting.

## Recipe: Retry after provider failure

1. Save the run id.
2. Inspect `agent show`.
3. Check whether any files changed.
4. Retry with the same task only after confirming state.

## Recipe: Do not resume by accident

Do not use:

```bash
teaagent agent run --background <run_id>
```

Use review or the explicit resume surface instead.

## Recipe: Finish a task

A run is done only when:

- Final answer and changed files agree.
- Approval log is understandable.
- Tests or manual smoke prove the claim.
- Known-issues/current-status docs are updated if user behavior changed.
