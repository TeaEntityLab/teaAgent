# run_store — Module Inspection

## Purpose

The run store is the durable, persistent record of every agent run in TeaAgent. It stores run lifecycle events, task text, audit logs, approval states, changed files, and final answers — forming the evidentiary chain that supports run listing, replay, review, and resumption.

The store's contracts are strict: every run id must resolve to a task or an explicit corrupted/missing marker; resume requires stored task and observations; review requires changed-file and audit evidence; corrupt JSONL entries must surface as degraded health, not vanish silently from run lists.

## Source Files

| File | Responsibility |
|------|---------------|
| `teaagent/run_store.py` | Core store implementation — `RunStore` class: CRUD operations, JSONL read/write, `list_runs()`, `show_run()`, `summarize()`, `resume_context()` |
| `teaagent/cli/_handlers/_agent.py` | CLI handlers that consume the store: `agent_run_task()` writes runs on completion, `agent_show_command()` reads run details, `agent_list_command()` enumerates runs, `agent_resume_command()` restores context |
| `teaagent/cli/_handlers/chat_repl.py` | Chat REPL that accesses run store for `/runs` listing and `/resume <id>` commands |
| `teaagent/runner/_core.py` | `AgentRunner.run()` writes `run_started`, `run_completed`, `run_failed` events that the store records |

## Key Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `RunStore` | class | Central store class; manages JSONL-backed run persistence under `~/.teaagent/runs/` |
| `RunStore.list_runs(limit)` | method | Returns summary list of recent runs with status, task snippet, cost, timestamp |
| `RunStore.show_run(run_id)` | method | Returns full run record including task, status, observations, audit events, changed files |
| `RunStore.summarize(run_id)` | method | Returns a condensed human-readable summary; surfaces `None` on corrupt JSON (degraded, not missing) |
| `RunStore.resume_context(run_id)` | method | Extracts stored task text and observations needed for run resumption |
| `RunStore.save(run_result)` | method | Persists a completed `RunResult` as a JSONL entry |
| `RunStore.record_event(run_id, event)` | method | Appends a lifecycle event to the run's JSONL line |

## Dependencies

| Dependency | Used For |
|-----------|----------|
| `teaagent.audit.AuditLogger` | Source of per-run audit events that the store records |
| `teaagent.budget` / `teaagent.budget_monitor` | Cost totals written into run records for display |
| `teaagent.runner._types.RunResult` | Primary data type consumed by `RunStore.save()` |
| `teaagent.chat_session_controller` | Session-level access to run store for `/runs` and `/resume` in chat modes |
| `teaagent.cli._handlers._agent` | CLI commands that create, read, and list runs via the store |
| `teaagent.cli._output` | Output formatters (`print_table`, `print_json`) used to display run data |

## Entry Points

| Caller | How invoked |
|--------|------------|
| `teaagent.cli.__init__.main()` → `agent_run_command` | `RunStore.save(run_result)` after `AgentRunner.run()` completes |
| `teaagent.cli.__init__.main()` → `agent_show_command` | `RunStore.show_run(run_id)` → renders full run detail |
| `teaagent.cli.__init__.main()` → `agent_list_command` | `RunStore.list_runs()` → renders recent runs table |
| `teaagent.cli.__init__.main()` → `agent_resume_command` | `RunStore.resume_context(run_id)` → feeds into `AgentRunner.run()` with restored observations |
| `teaagent.cli._handlers.chat_repl` | REPL `/runs` and `/resume <id>` commands read from the store |
| `teaagent.tui` → `ChatSessionController` | Session controller reads run store for TUI run listing and resumption |

## Call Graph

```
CLI main()
  ├── agent_run_command(args)
  │     AgentRunner.run(task)
  │       ├── audit.record('run_started')         [writes run_started event]
  │       ├── [loop iterations with tool calls]
  │       │     └── audit.record(...) for each event
  │       └── return RunResult(status=...)
  │     RunStore.save(run_result)                 [persists completed run as JSONL]
  │       └── writes ~/.teaagent/runs/<run_id>.jsonl
  │
  ├── agent_list_command(args)
  │     RunStore.list_runs(limit)
  │       └── scans ~/.teaagent/runs/*.jsonl
  │       └── for each valid file: extract status, task snippet, cost, timestamp
  │       └── for each corrupt file: surface warning (RS-R-001), mark degraded
  │
  ├── agent_show_command(args)
  │     RunStore.show_run(run_id)
  │       └── reads ~/.teaagent/runs/<run_id>.jsonl
  │       └── [valid] returns full record (task, status, observations, audit, changed_files)
  │       └── [missing] returns explicit "not found" marker
  │       └── [corrupt] returns degraded health marker with partial data
  │
  ├── agent_resume_command(args)
  │     RunStore.resume_context(run_id)
  │       └── extracts stored task and observations
  │       └── [if context insufficient] raises error (RS-R-002)
  │     AgentRunner.run(task, initial_observations=[...])  [resumes with prior context]
  │
  └── chat_repl / TUI
        ChatSessionController.run_store → RunStore.list_runs() / .show_run()
```

## Integrity Checks

Based on the module's specification and risk analysis, these invariants must hold:

1. **Every run starts with a durable `run_started` event** — the run id, task text, and timestamp are written before any model call.
2. **Task text is always present** — a run without task text is invalid; `show_run()` must surface this as degraded.
3. **Observations are stored for resume** — suspended or interrupted runs must retain enough context (task + observations) for successful resumption.
4. **Approval states are represented** — each run records tool calls that required approval and their outcomes (granted/denied/timed-out).
5. **Corrupt files are counted and warned** — `list_runs()` must not silently filter corrupt JSONL; it must surface a count or warning (RS-R-001).
6. **Missing vs corrupt is distinguishable** — `show_run(run_id)` must return distinct states for "file not found" vs "file exists but is unreadable".
