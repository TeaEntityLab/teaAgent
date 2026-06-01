# Daily-Driver Release Gates
# 2026-06-02

Release gates for changes that affect TUI, chat, or agent mode.

## Required gates

| Gate | Required proof |
|------|----------------|
| Command path | Test drives parser/handler/runtime path. |
| User text | Help/docs/output match behavior. |
| Cost | Display is real or unknown. |
| Root | Explicit root wins. |
| Approval | Scope is exact and logged. |
| Undo | Scope and mechanism are clear. |
| Resume | Run id rehydrates task and observations. |
| Evidence | Run/audit/test proof agrees with final claim. |

## Blockers

Block release if:

- A task can be silently dropped.
- A false zero cost is shown after real work.
- Approval lacks scope.
- Resume command is printed but cannot work.
- Tests only verify helper state.
- Known-issues docs contradict the release claim.

## Required commands

At minimum for docs/status changes:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

For code changes, add targeted runtime tests and manual smoke.
