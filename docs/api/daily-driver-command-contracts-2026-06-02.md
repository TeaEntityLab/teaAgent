# Daily-Driver Command Contracts
# 2026-06-02

Command-level contracts for daily surfaces.

## `teaagent chat`

- With no task: open chat normally.
- With a task: execute the task or reject visibly.
- On failure: show actionable error.
- On success: show answer and run evidence where applicable.

## `teaagent tui`

- Explicit root wins over saved state.
- Startup displays active root.
- Commands produce visible result, visible refusal, or approval prompt.
- Cost display is real or unknown.

## `teaagent agent run`

- Task argument is treated as new work, not resume.
- Run id is created and displayed.
- Approval requirements are visible.
- Final status is recorded in run evidence.

## `teaagent agent show`

- Existing run id shows summary.
- Missing run id is reported distinctly.
- Corrupt run id is reported distinctly when detectable.

## `teaagent agent interactive-review`

- Shows changed files and review options.
- Does not imply execution is continuing.
- Does not hide missing/corrupt run evidence.

## `teaagent agent resume`

- Requires stored task and observations.
- Restores approval and context state.
- Refuses clearly if the run is not resumable.
