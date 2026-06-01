# tui — Module Inspection

## Purpose

The TUI module is the interactive operator cockpit for TeaAgent. It provides a Textual-based terminal UI where users chat with agents, manage approvals, monitor cost/budget, and switch models mid-session — all without leaving the terminal.

The TUI is meant to expose project state (root, provider, model, permission mode, run state) and route user commands to backend APIs without reinterpreting core agent behavior. Its design contracts include: explicit root wins over saved state, cost is always real or marked unknown, and every run-producing command exposes a run id.

## Source Files

| File | Responsibility |
|------|---------------|
| `teaagent/tui/__init__.py` | `TUIApp` — main Textual application class, layout composition, event loop entry point |
| `teaagent/tui/_setup.py` | `setup_tui()` — configures Textual widgets: input, output panel, cost bar, approval panel |
| `teaagent/tui/_commands.py` | `handle_command()` — slash-command routing (`/quit`, `/reset`, `/history`, `/help`, `/skill`, `/approval list`, `/model`, `/budget`) |
| `teaagent/tui/_approval_subagents.py` | `ApprovalSubagentPanel` — inline rendering of pending tool approval requests with approve/deny/session-approve actions |
| `teaagent/tui/_completion.py` | `TUICompleter` — tab-completion for slash commands and known tool names in the input field |

## Key Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `TUIApp` | class | Main Textual application; takes `initial_task`, `provider`, `model`, `workspace_root`, `permission_mode`, `budget_cents` |
| `TUIApp.run()` | method | Starts the Textual event loop; blocks until `/quit` or Ctrl-C |
| `TUIApp.initial_task` | property | Pre-populated task string auto-submitted on startup (TASK-DD2-001 fix) |
| `setup_tui(app)` | function | Configures Textual layout: InputField, OutputPanel, CostBar, ApprovalPanel, StatusLine |
| `handle_command(cmd, app)` | function | Dispatches slash commands; returns response string or None for internal handling |
| `ApprovalSubagentPanel` | class | Inline approval UI; methods: `show_approval_request()`, `on_approve()`, `on_deny()`, `on_approve_session()` |
| `TUICompleter` | class | Tab-completion provider for slash commands and tool names |

## Dependencies

| Dependency | Used For |
|-----------|----------|
| `teaagent.runner.AgentRunner` | Backend execution of agent tasks from TUI chat input |
| `teaagent.chat_agent` | Agent messaging loop invoked per user message |
| `teaagent.chat_session_controller` | Shared session state, cost accumulation, budget enforcement from TUI |
| `teaagent.context` | Context pack assembly and compaction for model calls |
| `teaagent.budget` / `teaagent.budget_monitor` | Hard cost cap enforcement displayed in CostBar |
| `teaagent.approval_manager` | Permission enforcement and JIT approval prompts rendered in ApprovalPanel |
| `teaagent.audit.AuditLogger` | Per-run audit event recording |
| `teaagent.cli._handlers._chat` | `chat_command` — the CLI entry point that launches TUI (or falls back to REPL) |

## Entry Points

| Caller | How invoked |
|--------|------------|
| `teaagent.cli.__init__.main()` | `chat_command(args)` → `TUIApp(...).run()` when stdout is a TTY and `--no-tui` is not set |
| `teaagent.cli._handlers._chat.chat_command()` | Constructs `TUIApp` with workspace root, provider, model, permission mode, budget, and initial task from CLI args |
| Internal slash commands | `/quit`, `/reset`, `/history`, `/help`, `/skill <name>`, `/approval list`, `/model <name>`, `/budget` |

## Call Graph

```
CLI main()
  └── chat_command(args)
        ├── [stdout is TTY && !--no-tui]
        │     TUIApp(initial_task=..., provider=..., model=..., ...)
        │     setup_tui(app)
        │       ├── InputField     (user text input with history)
        │       ├── OutputPanel    (streaming LLM response display)
        │       ├── CostBar        (real-time cost / budget display)
        │       ├── ApprovalPanel  (inline approval prompts)
        │       └── StatusLine     (current model, permission mode, session info)
        │     TUIApp.run()
        │       ├── [on startup] submit initial_task → ChatSessionController.send_message()
        │       ├── [on user input]
        │       │   ├── handle_command(cmd, app) → slash command dispatch
        │       │   └── ChatSessionController.send_message(user_text)
        │       │         ├── ContextCompactor.compact()
        │       │         ├── AgentRunner.run(task) or model.decide()
        │       │         ├── [on ToolPermissionError]
        │       │         │   ApprovalSubagentPanel.show_approval_request()
        │       │         │     └── user choose: approve / deny / approve-session
        │       │         ├── BudgetMonitor check → CostBar update
        │       │         └── AuditLogger.record() for each event
        │       └── [on /quit or Ctrl-C] stop event loop
        └── [non-TTY or --no-tui]
              chat_repl loop (fallback REPL mode)
```
