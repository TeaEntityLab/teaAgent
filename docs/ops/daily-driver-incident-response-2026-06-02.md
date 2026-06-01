# Daily-Driver Incident Response
# 2026-06-02

Use this when TeaAgent daily use causes confusing, unsafe, or trust-breaking behavior.

## Incident classes

| Class | Example | First action |
|-------|---------|--------------|
| Wrong root | Files touched in unexpected repo. | Stop writes, capture root and git status. |
| Overbroad approval | Tool ran outside expected path. | Revoke/stop, capture approval id. |
| Cost surprise | Display said zero but spend happened. | Preserve run id, check provider dashboard. |
| Undo surprise | Manual edit lost or changed. | Stop, inspect git reflog/status/stash. |
| Resume failure | Run id cannot continue. | Use `agent show` and interactive review. |
| Corrupt evidence | Run/memory unreadable. | Preserve files, do not overwrite state. |

## Response steps

1. Stop the current run if still active.
2. Capture terminal output.
3. Capture run id and approval ids.
4. Capture `git status`.
5. Copy or preserve relevant `.teaagent` state if safe.
6. Classify incident.
7. Link to ticket or create new ticket.
8. Update known issues if user-facing.

## Post-incident questions

- Did docs overpromise?
- Did tests miss the active path?
- Did approval or root scope fail?
- Did the run evidence make diagnosis easy?
- What single invariant would have prevented this?
