# Daily-Driver Debug Playbook
# 2026-06-02

Use this when a daily-driver surface behaves differently from the docs.

## First capture

Collect:

- Exact command.
- Current working directory.
- Run id.
- Provider/model.
- Permission mode.
- Surface: TUI, REPL chat, or agent mode.
- Git status before and after.
- Terminal output.

## Debug order

1. Reproduce with the smallest task.
2. Identify the active command path.
3. Check whether a stale implementation path is involved.
4. Check run/audit evidence.
5. Add or run a path-level test.
6. Update docs only after behavior is understood.

## Common suspects

| Symptom | Suspect |
|---------|---------|
| Task accepted but nothing happens | Parser/handler/TUI initial-task handoff. |
| Cost remains zero | TUI ledger or display path. |
| Wrong repo root | Saved TUI state overwrote explicit root. |
| Resume fails | RunStore lacks task/observations for the suspended run. |
| Approval too broad | Path extraction or matcher semantics. |
| Daily hides old state | Corrupt memory/run JSON skipped silently. |

## Debugging principle

Do not debug from the final answer alone. Debug from command path, run id, audit events,
diffs, and tests.
