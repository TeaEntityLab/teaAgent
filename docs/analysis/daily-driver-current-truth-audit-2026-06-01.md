# Daily-Driver Current Truth Audit

Date: 2026-06-01

Scope: TUI mode, TUI chat mode, `teaagent chat`, and agent mode. This document is
intended to supersede stale parts of earlier same-day daily-driver documents, not to
erase their historical value.

## Purpose

Several June 1 documents correctly identified serious daily-driver risks, but the code
has since moved enough that some findings are now fixed, partly fixed, or shifted to a
different surface. This audit separates current evidence from older stale statements so
future implementation work does not chase the wrong failure.

## Current Truth Table

| Area | Current status | Evidence | User impact |
|---|---|---|---|
| Canonical chat REPL task execution | Partly fixed in `chat_repl.py`, but not necessarily reached by `teaagent chat`. | `teaagent/cli/_handlers/chat_repl.py` now uses `ChatSessionController.execute_task`; `teaagent/cli/_handlers/_chat.py` delegates `chat_command` to `run_tui` and ignores parsed initial task. | Fixes in the controller may not protect the default chat entry point. |
| `teaagent chat <task>` | Active high risk: parsed task can be dropped. | `add_agent_run_arguments(... include_task_positional=True)` accepts `task`; `chat_command` does not pass it to `run_tui`; `run_tui` has no initial-task argument. | A daily user can type a task and get an empty chat shell instead of execution. |
| TUI cost and budget display | Active high risk. | TUI stores `_session_cost_cents` and prints it, but `_run_agent_task` receives `result.cost_cents` without accumulating it. | Users cannot trust cost/budget feedback in the primary daily surface. |
| CLI chat session cost | Improved in controller-backed path. | `ChatSessionController` increments `session_state.session_cost_cents` after `run_chat_agent`. | Safer if the user is actually on the controller-backed path. |
| Undo in canonical chat controller | Improved. | `ChatSessionController.undo_last_run` restores `UndoJournal` and does not use a blanket `git checkout -- .`. | Stronger recoverability for controller-backed chat sessions. |
| TUI undo help | Active UX risk. | TUI help lists two different `undo` meanings; command dispatch restores undo journals before the later checkpoint-oriented branch can apply. | Users cannot predict what undo will do. |
| TUI compact | Fixed relative to older docs. | `_handle_compact` calls `ContextCompactor.compact_chat_history`. | Older "compact is a stub" claims should be treated as stale. |
| TUI split-pane display | Partly fixed relative to older docs. | The state panel no longer clears the whole screen, but auto-enabled panels can still be noisy on large terminals. | Lower correctness risk, still a daily-use polish risk. |
| Agent git sandbox | Active high risk. | `_execute_agent_task` creates and starts `GitBranchSandbox` when a repository is available, independent of whether `--git-sandbox` was supplied. | Non-interactive or default agent runs can unexpectedly switch branches. |
| Background / suspension wording | Active medium risk. | `suspend_to_background` says it is a checkpoint, while the caller also prints "converted to background task" and suggests `teaagent agent run --background {run_id}`. | Users may believe work continues after exit when it does not. |
| Duplicate chat implementation | Active maintenance risk. | `_chat.py` still contains older REPL code and runtime `chat_command`, while tests focus heavily on `chat_repl.py` and `ChatSessionController`. | Future fixes can land in the wrong file. |
| MCP remote tool trust | Active product/security risk. | `mcp_tool_adapter._infer_annotations` trusts server-provided annotations to decide read-only/destructive behavior. | A bad or sloppy MCP server can weaken permission expectations. |
| Acceptance docs | Active release-confidence risk. | `scripts/validate_docs_consistency.py` previously reported a mismatch between `docs/acceptance.md` and collected acceptance tests. | Docs can claim readiness that CI evidence does not support. |

## Superseded Or Shifted Findings

The following older claims should not be used as current truth without re-checking code:

- "The chat REPL always reports successful tasks as failed" is no longer accurate for
  `ChatSessionController` paths, but default `teaagent chat <task>` still has a separate
  entry-point risk.
- "Chat `/undo` always risks blanket workspace destruction" is no longer accurate for
  controller-backed undo, but stale duplicate code and confusing help still make recovery
  semantics risky.
- "TUI compact is a stub" is stale.
- "TUI clears the screen every prompt" is stale, but the auto panel can still be noisy.

## Active Highest-Risk Queue

1. Make `teaagent chat <task>` execute the supplied task or reject the syntax loudly.
2. Wire TUI chat execution through `ChatSessionController`, or at minimum accumulate
   `result.cost_cents` and share undo/run-state behavior.
3. Make agent git sandbox opt-in, or rename the flag and docs so auto-sandboxing is an
   explicit product contract.
4. Replace background/suspension copy with one lifecycle vocabulary.
5. Quarantine or delete stale duplicate REPL paths after proving runtime imports.
6. Update acceptance-count docs from the same source used by validation.

## Evidence Boundary

Evidence is direct repo inspection plus two read-only subagent audits. External market
research informs the priority of cost, recovery, and lifecycle risks, but the statuses
above are based on local code behavior.

