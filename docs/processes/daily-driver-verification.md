# Daily-Driver Verification Process
# 2026-06-02

Use this process before claiming a TUI, chat, or agent-mode daily-driver issue is fixed.

## Verification order

1. Identify the user-visible claim.
2. Identify the active command path.
3. Add or run an automated test for that path.
4. Run a manual smoke step if terminal behavior is involved.
5. Update known issues and current status.
6. Link the proof from the ticket plan or fix log.

## Required checks by surface

| Surface | Automated proof | Manual proof |
|---------|-----------------|--------------|
| `teaagent chat` | Parser/handler/controller tests. | REPL visible answer, cost, undo. |
| `teaagent tui` | Headless TUI command tests. | Terminal prompt, panel, command output. |
| `teaagent agent run` | CLI handler/run-store/audit tests. | Run id, summary, changed files. |
| Approvals | Approval manager and CLI/TUI prompt tests. | Exact scope is understandable. |
| Resume/review | Run-store rehydration tests. | Human can continue or review from run id. |

## Fresh workspace side-effect check

For commands advertised as dry-run or read-only:

1. Create a fresh temp workspace.
2. Snapshot file tree.
3. Run the command.
4. Snapshot file tree again.
5. Fail if `.teaagent` or other state appears without explicit initialization wording.

## Evidence wording

Use these terms consistently:

- `Claimed`: agent or docs say it happened.
- `Observed`: logs or files show it happened.
- `Verified`: test or manual smoke proved it.
- `Not tested`: no direct proof yet.

## Release gate

Do not mark a daily-driver item fixed if any of these are true:

- The test bypasses the public path.
- The docs still warn about the supposedly fixed behavior.
- The terminal output uses stale lifecycle wording.
- The run evidence cannot be found by run id.
- The fix changes approval, root, cost, or undo behavior without human review.
