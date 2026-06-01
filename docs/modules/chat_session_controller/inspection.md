# chat_session_controller — Purpose, Dependencies, Exported API, and Call Graph

## Purpose

`chat_session_controller.py` solves the **correctness fragmentation** problem: the same agent task could be executed from the CLI REPL, the TUI, or the `run_chat_repl` function, each with slightly different logic for cost tracking, undo journaling, and result display. This module provides a single shared controller so all surfaces get identical behavior.

The module is small by design (229 lines). It does not implement any agent logic; it only orchestrates existing subsystems.

---

## Source Files

| File | Lines | Role |
|------|-------|------|
| `teaagent/chat_session_controller.py` | 229 | Core controller |
| `teaagent/cli/_handlers/_chat.py` | 593 | CLI chat command; calls `run_tui()` which calls `_run_agent_task()` |
| `teaagent/cli/_handlers/chat_commands.py` | 306 | REPL command handlers (compact, pin/unpin, failure cards, shell) |
| `teaagent/cli/_handlers/chat_completion.py` | 111 | Readline/ontology-based `@`-path completion functions |
| `teaagent/cli/_handlers/chat_repl.py` | 846 | Interactive REPL main loop; uses `ChatSessionController` |

---

## Dependencies

### `chat_session_controller.py`

| Import | Used for |
|--------|----------|
| `teaagent.audit.AuditLogger` | Passed to `run_chat_agent`; undo journal attached as sink |
| `teaagent.chat_agent.ChatAgentConfig, run_chat_agent` | Core agent execution |
| `teaagent.llm.create_llm_adapter` | Creates LLM adapter from config.model string |
| `teaagent.run_store.RunStore` | Creates audit logger; persists run results and undo journals |
| `teaagent.run_undo.UndoJournal` | File mutation tracking and restore |
| `teaagent.runner._types.RunResult` | Return type from `run_chat_agent` |

### `cli/_handlers/chat_repl.py` additional imports

| Import | Used for |
|--------|----------|
| `teaagent.chat_session_controller.ChatSessionController, SessionState` | Shared execution with CG-01/02/03 fixes |
| `teaagent.context.ContextCompactor` | Session context compaction |
| `teaagent.llm.available_providers, create_llm_adapter` | Hot-swap provider/model |
| `teaagent.memory.file_watcher.FileWatcher` | Live context sync for pinned files |
| `teaagent.memory.pinned_file.PinnedFileStorage` | Pin/unpin file persistence |
| `teaagent.run_store.RunStore` | Per-task audit logger and undo path |
| `teaagent.run_undo.UndoJournal` | Per-task undo journal |
| `.chat_commands.*` | Delegated command handlers |
| `.chat_completion.*` | Tab completion helpers |

### `cli/_handlers/chat_commands.py` additional imports

| Import | Used for |
|--------|----------|
| `teaagent.context.ContextCompactor` | `handle_compact()` implementation |
| `teaagent.memory.failure_card.FailureCardStorage` | Failure card list/clear commands |
| `teaagent.memory.pinned_file.PinnedFileStorage` | Pin/unpin command implementations |

---

## Exported API

### From `chat_session_controller.py`

| Name | Type | Description |
|------|------|-------------|
| `SessionState` | `@dataclass` | Mutable shared session state (cost, observations, compaction count, targeted files) |
| `ExecutionResult` | `@dataclass` | Per-task result wrapper (run_result, cost_cents, observations_updated) |
| `ChatSessionController` | class | Main controller class |

### From `cli/_handlers/chat_repl.py`

| Name | Type | Description |
|------|------|-------------|
| `run_chat_repl` | function | Main REPL entry point |
| `print_chat_help` | function | Prints available slash commands |
| `suspend_to_background` | function | Serializes session state to `.teaagent/suspension-{run_id}.json` |

### From `cli/_handlers/_chat.py`

| Name | Type | Description |
|------|------|-------------|
| `chat_command` | function | argparse handler; delegates to `run_tui()` |
| `run_chat_repl` | function | Secondary REPL (legacy, pre-controller) — still exports functions for pinning, memory, etc. |
| `handle_memory_failures` | function | Lists failure cards to stdout |
| `handle_pin` / `handle_unpin` / `handle_pinned` | functions | Pin/unpin file management (also in chat_commands.py — duplicated) |
| `complete_file_path` / `complete_symbol` | functions | Readline-based completion (also duplicated in chat_completion.py) |
| `execute_shell_command` | function | Safe shell execution with denylist |
| `suspend_to_background` | function | Legacy version (creates git branch sandbox) |

### From `cli/_handlers/chat_commands.py`

| Name | Type | Description |
|------|------|-------------|
| `handle_compact` | function | Compacts session_context using ContextCompactor |
| `handle_memory_failures` | function | Lists failure cards |
| `handle_pin` / `handle_unpin` / `handle_pinned` | functions | Pin/unpin |
| `handle_memory_clear` | function | Clears failure cards |
| `get_failure_warnings` | function | Builds failure warning prefix for tasks |
| `execute_shell_command` | function | Safe shell execution |

### From `cli/_handlers/chat_completion.py`

| Name | Type | Description |
|------|------|-------------|
| `complete_file_path` | function | Returns `@path` completions using filesystem |
| `complete_symbol` | function | Returns `@symbol` completions using CodeOntologyBuilder |

---

## Entry Points

1. `chat_command(args)` in `_chat.py` — Called by the CLI argparse routing for `teaagent chat [task]`.
2. `run_chat_repl(config, initial_task)` in `chat_repl.py` — Called by tests and potentially by other integration points.

---

## Call Graph

```
chat_command(args)                          [_chat.py:538]
  └─► run_tui(...)                          [tui/__init__.py]
        └─► TeaAgentTUI._run_agent_task(task)
              └─► run_chat_agent(...)       [chat_agent.py]

run_chat_repl(config, initial_task)         [chat_repl.py:184]
  ├─► ChatSessionController(root, print)   [chat_session_controller.py]
  ├─► controller.execute_task(task, config, adapter, audit, undo_journal)
  │     ├─► run_chat_agent(...)             [chat_agent.py]
  │     ├─► undo_journal.save_to(...)       [run_undo]
  │     ├─► output_fn(final_answer / error)
  │     └─► session_state.session_cost_cents += cost_cents
  │
  ├─► controller.undo_last_run()
  │     ├─► RunStore.latest_run_with_undo() [run_store]
  │     ├─► UndoJournal.restore()           [run_undo]
  │     └─► output_fn(restored/error)
  │
  └── slash command handlers ──►
        handle_compact(compactor, session_context)   [chat_commands.py]
        handle_memory_failures(root)                 [chat_commands.py]
        handle_pin/unpin/pinned(root, cmd)           [chat_commands.py]
        complete_file_path/complete_symbol(text, root) [chat_completion.py]
```
