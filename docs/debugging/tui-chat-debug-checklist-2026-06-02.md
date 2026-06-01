# TUI Chat Debug Checklist
# 2026-06-02

Checklist for TUI chat bugs.

## Startup

- Did `TeaAgentTUI` receive the expected `root`?
- Did `_load_tui_state()` overwrite it?
- Was chat mode explicit or restored from saved state?
- Was `initial_task` supplied?
- Did `_run_agent_task(initial_task)` run before prompt loop?

## Execution

- Did the path call `run_chat_agent` directly?
- Did it pass `chat_messages` from the active session?
- Did it pass cost, iteration, tool, and permission limits?
- Did it record run id and audit events?

## Result display

- Was the answer visible?
- Was failure text specific?
- Was cost incremented from `result.cost_cents`?
- Did `/cost` and `/budget` agree?

## Undo

- Which mechanism ran: undo journal or checkpoint restore?
- Were unrelated manual edits present?
- Was the user told the recovery scope?

## Test smell checks

- Did the test set `_session_cost_cents` directly?
- Did the test bypass `_run_agent_task()`?
- Did the test assert only formatting?
- Did the test inspect user-visible output?
