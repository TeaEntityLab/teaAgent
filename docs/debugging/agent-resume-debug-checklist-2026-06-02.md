# Agent Resume Debug Checklist
# 2026-06-02

Checklist for suspend, resume, background, and review bugs.

## Identify the lifecycle word

Record whether the UI said:

- Running
- Suspended
- Background
- Resume
- Review
- Undo

Then verify whether runtime state matches that word.

## Run-store checks

- Does the run id exist?
- Is there a `run_started` event?
- Is the original task stored?
- Are observations or context stored?
- Are pending approvals stored?
- Is the terminal status clear?

## Command checks

- Does `agent show <run_id>` work?
- Does `interactive-review <run_id>` work?
- Does explicit resume work?
- Did `agent run --background <run_id>` accidentally start a new task?

## Evidence checks

- Did the audit log record suspension?
- Did it record approval state?
- Did it record changed files?
- Did it record whether work kept running?

## Fix direction

- If review works but resume fails, improve run-store rehydration.
- If output advertises broken commands, fix wording first.
- If run id is treated as task, add parser/handler guard.
