# Daily-Driver Fix Log
# Started 2026-06-02

This chronological log should be updated after daily-driver fixes land. It is not a
replacement for commit history; it records product-facing behavior and proof.

## 2026-06-02 observed working-tree changes

| Item | Behavior | Proof still needed |
|------|----------|--------------------|
| TASK-DD2-001 | `chat_command()` forwards `args.task` into `run_tui(initial_task=...)`; TUI executes it before prompt loop. | Parser/handler/TUI tests and manual smoke. |
| TICKET-12 Step A | TUI adds `result.cost_cents` into `_session_cost_cents`. | Active TUI cost test and budget display parity. |

## Future entry template

```md
## YYYY-MM-DD <ticket id>

- Behavior changed:
- Files changed:
- User-facing docs updated:
- Automated verification:
- Manual smoke:
- Remaining risks:
- Follow-up ticket:
```

## Logging rule

If a fix affects trust-sensitive behavior, include both the code change and the evidence
that users can observe.
