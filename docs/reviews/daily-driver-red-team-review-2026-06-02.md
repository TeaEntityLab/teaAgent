# Daily-Driver Red-Team Review
# 2026-06-02

Adversarial review of daily-driver assumptions.

## Attack the happy path

| Assumption | Challenge |
|------------|-----------|
| The user knows the active root. | Saved state can change it. |
| The cost display is close enough. | A false zero changes spending behavior. |
| Approval prompts are understandable. | Missing path makes approval meaningless. |
| Resume will work if a command is printed. | RunStore may not have task context. |
| Tests passing means TUI works. | Helper tests can bypass command path. |
| Corrupt state is rare. | Rare state corruption is exactly when cockpit honesty matters. |

## Red-team scenarios

1. Launch TUI in repo B after saved state from repo A.
2. Run two costed TUI tasks and compare `/cost` to run summary.
3. Try approving a file path that has a confusing suffix sibling.
4. Corrupt one run JSONL and check daily output.
5. Pin an absolute path outside the workspace.
6. Trigger suspend and follow every printed command.

## Expected product behavior

The product should refuse, warn, or show degraded health before a user is surprised.
