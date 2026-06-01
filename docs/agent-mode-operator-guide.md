# Agent Mode Operator Guide
# As of 2026-06-02

Use agent mode when you want a task to run with audit logs, approval gates, and a
recoverable run record instead of a live chat loop.

## Choose a command

| Need | Command |
|------|---------|
| Run one autonomous task | `teaagent agent run "<task>"` |
| Inspect recent runs | `teaagent agent runs` |
| Show one run | `teaagent agent show <run_id>` |
| Review a run's changes | `teaagent agent interactive-review <run_id>` |
| Resume through the explicit resume surface | `teaagent agent resume <run_id>` where supported |
| Run a preflight check | `teaagent agent preflight` |

## Inspect, edit, autonomous modes

| Mode | Use when | Risk |
|------|----------|------|
| Inspect | You want analysis without writes. | Lowest operational risk. |
| Edit | You want patches but expect review. | Medium; verify diffs and tests. |
| Autonomous | You want the agent to continue through clear steps. | Highest; depends on strong approval and audit boundaries. |

## Provider and task argument order

Be explicit with tasks:

```bash
teaagent agent run "summarize the repository risks"
```

Avoid treating a run id as an argument to `agent run --background`. If your intent is
to resume or review a run, use the resume or interactive-review surface instead.

## Run lifecycle

| State | Meaning | Operator action |
|-------|---------|-----------------|
| Created | Run has a durable id. | Save the id if the task matters. |
| Running | Agent is active. | Watch approvals and summary output. |
| Pending approval | Tool call needs explicit approval. | Inspect exact tool and path scope before approving. |
| Suspended | Run stopped before full completion. | Prefer review or explicit resume. |
| Completed | Final result recorded. | Verify changed files and tests. |
| Failed | Run ended with an error. | Inspect audit events before retrying. |

## Resume rules

- Resume should restore the task, observations, pending approvals, and governance mode.
- A resume path that only accepts a run id but has no task context is not a real resume.
- If the resume command errors, use `agent show` and `interactive-review` to inspect before retrying.

## Undo rules

- Treat undo as a scoped recovery operation, not a magic reset.
- Prefer journal-backed undo where available.
- Before accepting or undoing, inspect changed files and current git status.

## Recommended operator checklist

1. Start with a clear task.
2. Keep approval mode conservative until trust is earned.
3. Record the run id.
4. Review changed files and audit evidence.
5. Run the relevant tests or smoke checklist.
6. Commit only after the run's claims and evidence agree.
