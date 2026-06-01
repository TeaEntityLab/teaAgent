# Recovery And Continuity Guide
# As of 2026-06-02

This guide answers one question: "I need to stop, recover, continue, or revert. What is
the least surprising path?"

## Resume vs attach vs interactive review

| Situation | Prefer | Why |
|-----------|--------|-----|
| You have a run id and want to inspect changes | `teaagent agent interactive-review <run_id>` | Review is the most reliable current path. |
| You have a suspended run and the resume path is known-good | `teaagent agent resume <run_id>` | Intended continuity path when task context is stored. |
| You only want to see metadata | `teaagent agent show <run_id>` | Read-only and low risk. |
| You want a live TUI cockpit | `teaagent tui --root .` | Useful for status, approvals, and run listing. |

## Undo vs checkpoint restore

| Operation | Scope | Safer when |
|-----------|-------|------------|
| Chat `/undo` | Last run's touched files through undo journal. | You need to preserve unrelated manual edits. |
| TUI `/undo` today | Checkpoint/stash-style recovery path. | You intentionally created a checkpoint and understand the scope. |
| Git manual revert | Whatever you select. | You need precise human-controlled recovery. |

## Background vs suspend

Current recommended wording:

- "Suspended" means the run stopped and left a record.
- "Background" should mean work continues somewhere else.
- If a path does not continue work, do not describe it as background execution.

Operator rule: if a command prints a run id, inspect it with `agent show` before assuming
work is still running.

## Pending approval

When blocked on approval:

1. Read the tool name.
2. Read the exact input and path scope.
3. Approve only the exact call you understand.
4. Prefer rejecting and rerunning with narrower scope when the request is broad.

## Known broken or risky paths

| Path | Status | Safer alternative |
|------|--------|-------------------|
| `teaagent agent run --background <run_id>` | Can treat run id as a task. | `teaagent agent interactive-review <run_id>` |
| TUI `/cost` as spend truth | Known display gap. | Run summary or provider dashboard. |
| TUI `/undo` as journal undo | Not yet parity. | `teaagent chat` `/undo` or manual git review. |
| `teaagent chat <task>` | Needs execute/reject fix. | Use `teaagent agent run "<task>"` or REPL prompt after launch. |

## Continuity acceptance criteria

A continuity feature is daily-driver ready only when:

- The user sees one canonical command for the current state.
- The run id maps to a stored task and observations.
- Pending approvals survive the transition.
- The command either continues safely or refuses clearly.
- The audit log records the transition.
