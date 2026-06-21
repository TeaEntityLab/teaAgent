# Daily-Driver Troubleshooting
# As of 2026-06-21

Symptom-first guide for the daily TeaAgent surfaces.

| Symptom | Likely cause | Safest next command | Reference |
|---------|--------------|---------------------|-----------|
| `teaagent chat <task>` opens but the task did not run. | Positional task forwarding has regressed or the task failed before dispatch. | Capture the output, then use `teaagent agent run "<task>"` while investigating. | TASK-DD2-001 regression guard |
| TUI `/cost` shows `$0.00` after billable work. | The provider may not return usage data, or the active adapter may have regressed. | Inspect the run summary and provider capabilities, then compare the provider dashboard. | CG-11 regression guard |
| TUI budget disagrees with provider spend. | The controller only accounts for usage returned to the current session. | Treat the provider billing statement as authoritative and preserve the run id for diagnosis. | Cost evidence contract |
| A resume command errors. | The run id is invalid, the run is not resumable, or its durable record is unavailable. | `teaagent agent show <run_id>` then `teaagent agent interactive-review <run_id>`. | AG-01 regression guard |
| `/background` does not continue work after leaving chat. | This command suspends and records a checkpoint; it does not launch detached execution. | Use the returned run id with show, resume, or interactive review. | TICKET-16 lifecycle contract |
| TUI opens in the wrong repo despite `--root`. | Explicit-root precedence has regressed. | Stop before writes, restart with `teaagent tui --root .`, and report the visible root plus command. | TASK-DD2-002 regression guard |
| `/undo` affects files outside the latest run journal. | Journal scoping has regressed; TUI must not use global checkpoint fallback. | Stop, inspect `git status`, preserve the run id, and recover through normal git review. | CG-15 regression guard |
| Approval prompt has no path. | Path scope fallback is too broad or ambiguous. | Reject and rerun with narrower scope. | PATH-GATE |
| An unknown command is sent as a task without confirmation. | The typo-confirmation gate has regressed. | Cancel the task and preserve the entered command for a bug report. | U-P1-6 regression guard |

## Fast triage flow

1. Capture the exact command and run id.
2. Run `teaagent agent show <run_id>` if a run id exists.
3. Check git status before undo or resume.
4. Check pending approvals before retrying.
5. Prefer review over continuation when state is unclear.

## Reporting a new issue

Include:

- Command entered.
- Current working directory.
- Run id.
- Provider/model.
- Permission mode.
- Whether TUI, REPL chat, or agent mode was used.
- Expected result.
- Actual result.
