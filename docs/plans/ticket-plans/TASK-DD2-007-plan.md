# TASK-DD2-007: Remove Or Retire Stale Chat Code

**Priority:** P2
**Status:** Fixed — `_chat.py` consolidated into `chat_repl.py` (-1296 lines, commit 464ce046); one execution path remains; stale production cost `session_cost_cents += 10` removed (commit 29975a63). Verified by comprehensive audit (see docs/work-log/roadmap-work-items-2026-06-04.md).
**Primary files:** `teaagent/cli/_handlers/_chat.py`, `teaagent/cli/_handlers/chat_repl.py`, `tests/*chat*`

## Problem

There are multiple chat-related implementation paths. The active REPL path uses
`ChatSessionController`, while stale code can still contain old cost increments,
suspension wording, or branch behavior. Stale paths attract stale tests.

## Scope

- Identify live imports and CLI routing.
- Move any still-needed handler glue out of stale REPL code.
- Delete or quarantine unreachable REPL/suspension paths.
- Update tests to import active implementation only.

## Acceptance criteria

- One chat execution path remains for REPL-style chat.
- No production placeholder cost such as `session_cost_cents += 10` remains.
- Tests fail if they import retired chat execution paths.
- Docs name the active chat controller path.

## Verification

```bash
rg -n "session_cost_cents \\+= 10|run_chat_repl|creating sandbox branch" teaagent tests
python3 -m pytest tests/test_cli_chat.py tests/test_chat_session_controller.py
```

## Risks

- Deleting too early can break parser/handler glue.
- Keeping stale code can reintroduce fixed bugs through future imports.
