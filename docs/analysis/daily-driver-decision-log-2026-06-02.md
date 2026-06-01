# Daily-Driver Decision Log
# 2026-06-02

This file records product and engineering decisions that should be made before the next
daily-driver implementation batch.

## Decisions

| ID | Decision | Recommended default | Why | Human gate |
|----|----------|---------------------|-----|------------|
| DQ-2026-001 | What should `teaagent chat <task>` do? | Execute the task in TUI/REPL-compatible initial-task flow. | User intent is clear from the positional argument. | No |
| DQ-2026-002 | If initial task execution is not ready, what then? | Reject with a clear message. | Silent drop is worse than lack of feature. | No |
| DQ-2026-003 | Which root wins: explicit CLI root or saved TUI state? | Explicit CLI root. | Direct command arguments must be authoritative. | No |
| DQ-2026-004 | What should TUI show when cost is unavailable? | `unknown` or "not wired" state. | False zero misleads. | No |
| DQ-2026-005 | Should TUI cost stop-gap land before full controller migration? | Yes. | One small line can reduce user harm while migration continues. | No |
| DQ-2026-006 | Should TUI undo keep old checkpoint behavior? | Only if named as checkpoint restore. | Same label for different scope is unsafe. | Yes |
| DQ-2026-007 | Should `ChatSessionController` be the only chat execution source? | Yes. | Prevents surface drift. | No |
| DQ-2026-008 | How should mock/test handling work in controller code? | Explicit dependency injection/protocols. | Exception-based mock detection hides real bugs. | No |
| DQ-2026-009 | Should `agent run --background <run_id>` be accepted? | No; refuse and suggest resume/review. | Run id as task is dangerous confusion. | No |
| DQ-2026-010 | What does `background` mean? | Work continues outside foreground UI. | Words must encode real lifecycle. | No |
| DQ-2026-011 | What does `suspend` mean? | Work stopped with a durable record. | Different from background execution. | No |
| DQ-2026-012 | What does `resume` require? | Stored task, observations, approvals, and run context. | Otherwise it is not continuity. | No |
| DQ-2026-013 | Should stale chat paths remain after migration? | Quarantine or delete with tests. | Dead paths attract stale tests. | Yes |
| DQ-2026-014 | Should approval with no path be allowed? | No for write/destructive tools. | Scope is the approval's safety boundary. | Yes |
| DQ-2026-015 | Should cost cap value `0` mean zero spend or unlimited? | Document and enforce one meaning. | Ambiguity breaks budget trust. | Yes |
| DQ-2026-016 | Should new docs keep growing? | Only when they create operator clarity or implementation tickets. | Docs saturation is now a real risk. | No |
| DQ-2026-017 | What is the release gate for TUI daily-driver claims? | Manual smoke plus path-level tests. | Interactive surfaces need human-observable proof. | No |
| DQ-2026-018 | What is the release gate for agent mode continuity? | A run id resumes with task and observations rehydrated. | Run id must be a continuity handle. | No |

## Rejected defaults

| ID | Rejected option | Reason |
|----|-----------------|--------|
| RD-001 | Keep accepting `teaagent chat <task>` silently. | Violates no-silent-success. |
| RD-002 | Keep false `$0.00` until full migration. | Continues a trust bug even after known diagnosis. |
| RD-003 | Treat background and suspend as synonyms. | Users make different operational choices based on these words. |
| RD-004 | Preserve stale tests because they are passing. | Passing helper tests can hide runtime failure. |
| RD-005 | Add a second agent framework for these fixes. | Project architecture says the harness stays thin. |

## Decision review cadence

Revisit this log after:

- TICKET-12 lands.
- TICKET-16 lands.
- The TUI root and chat positional task fixes land.
- Any release note claims daily-driver readiness.
