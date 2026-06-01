# cli — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/cli/__init__.py` | `main()` — argparse tree, all command registrations |
| `teaagent/cli/__main__.py` | `raise SystemExit(main())` — executable entry point |
| `teaagent/cli/_output.py` | Output formatters: `print_json`, `print_table`, `print_error` |
| `teaagent/cli/execution.py` | Shared execution helpers (run lifecycle, config loading) |
| `teaagent/cli/_handlers/__init__.py` | Re-exports all handler functions |
| `teaagent/cli/_handlers/_agent.py` | `agent_run_task`, `agent_plan_command`, `agent_undo_command` |
| `teaagent/cli/_handlers/_chat.py` | `chat_command` — launches TUI or simple completion |
| `teaagent/cli/_handlers/_audit.py` | `audit_list_command`, `audit_verify_command`, etc. |
| `teaagent/cli/_handlers/_misc.py` | `configure_command`, `completion_command`, `clarify_command` |
| `teaagent/cli/_handlers/agent_helpers.py` | Shared helpers for agent handlers |
| `teaagent/cli/_handlers/chat_commands.py` | Chat-specific command handlers |
| `teaagent/cli/_handlers/chat_repl.py` | REPL loop for non-TUI chat mode |
| `teaagent/cli/_handlers/chat_completion.py` | Single-shot completion mode |
| `teaagent/cli/_*_parsers.py` | Per-command argument parsers (one file per command group) |

## Key Entry Points

### `main() -> int`
**Location**: `cli/__init__.py`
- Builds argparse tree with all subcommands.
- Dispatches `args.func(args)` for matched subcommand.
- Returns 0 on success, 1 on exception.

### `chat_command(args) -> int`
**Location**: `cli/_handlers/_chat.py`
- Launches TUI when stdout is a TTY and `--no-tui` not set.
- Falls back to `chat_repl.py` for non-TTY or `--no-tui`.
- Passes `args.task` as initial task to TUI/REPL.

### `agent_run_task(args) -> int`
**Location**: `cli/_handlers/_agent.py`
- Reads workspace root, permission mode, plan from args.
- Creates `ToolRegistry`, `AuditLogger`, `HookRegistry`.
- Calls `AgentRunner.run(task)`.

## Dependencies

```
cli/__init__.py
  └── teaagent.cli._handlers.*
      └── teaagent.runner, .tui, .audit, .approval_manager, ...
```

## Call Graph

```
main()
  ├── build argparse tree
  ├── parse_args()
  └── args.func(args)
        ├── agent_run_task → AgentRunner.run()
        ├── chat_command → TUIApp.run() | REPL loop
        ├── audit_verify_command → verify_audit_chain()
        └── ...
```
