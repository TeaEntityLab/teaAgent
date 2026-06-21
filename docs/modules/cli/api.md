# cli — Public API Reference

## `main() -> int`
**Location**: `cli/__init__.py`

The package-level entry point. Parses CLI arguments and dispatches to handlers.

```python
from teaagent.cli import main
raise SystemExit(main())
```

**Returns**: Integer exit code (0 = success, 1 = error, 2 = usage error).

**Pre-condition**: CLI arguments must be parseable by `argparse`.  
**Post-condition**: Dispatches to the appropriate handler; returns integer exit code.

---

## Handler Signatures

All handlers follow the pattern:
```python
def <command>_command(args: argparse.Namespace) -> int | None
```
Return value: `0` or `None` for success, `1` for error.

### Core Agent Handlers

```python
# cli/_handlers/_agent.py
agent_run_task(args)           # teaagent agent run <task>
agent_plan_command(args)       # teaagent agent plan
agent_undo_command(args)       # teaagent agent undo
agent_resume_command(args)     # teaagent agent resume <run_id>
agent_status_command(args)     # teaagent agent status
agent_attach_command(args)     # teaagent agent attach <run_id>
```

**Pre/Post Conditions (Agent Handlers)**:

| Handler | Pre-condition | Post-condition |
|---------|---------------|----------------|
| `agent_run_task` | `args.task` must be non-empty string | Returns `RunResult` or `None` on success, `1` on error |
| `agent_plan_command` | Workspace root must be configured | Plan stored in run context |
| `agent_undo_command` | A run must have been executed | UndoJournal applied or error reported |
| `agent_resume_command` | `run_id` must reference a resumable run | Resumed run completes or fails |
| `agent_status_command` | Run store accessible | Prints current run status |
| `agent_attach_command` | `run_id` must reference an active run | Attaches to running session |

### Chat Handlers

```python
# cli/_handlers/_chat.py
chat_command(args)             # teaagent chat [task]
```

```python
# cli/_handlers/chat_repl.py
run_chat_repl(args)            # non-TUI REPL loop
```

**Pre/Post Conditions (Chat Handlers)**:

| Handler | Pre-condition | Post-condition |
|---------|---------------|----------------|
| `chat_command` | Provider must be configured; `args.task` optional | Interactive chat session started |
| `run_chat_repl` | Provider must be configured | REPL loop runs until `/quit` or Ctrl-C |

### Audit Handlers

```python
# cli/_handlers/_audit.py
audit_list_command(args)       # teaagent audit list
audit_show_command(args)       # teaagent audit show <run_id>
audit_verify_command(args)     # teaagent audit verify <path>
audit_export_command(args)     # teaagent audit export
audit_serve_command(args)      # teaagent audit serve [--port]
```

**Pre/Post Conditions (Audit Handlers)**:

| Handler | Pre-condition | Post-condition |
|---------|---------------|----------------|
| `audit_list_command` | Audit log directory exists | Prints run list from audit store |
| `audit_show_command` | `run_id` must be valid | Prints run details and event log |
| `audit_verify_command` | `path` must exist and be a valid audit log | Prints verification result (valid/invalid) |
| `audit_export_command` | Audit logs accessible | Exports audit data (default: NDJSON) |
| `audit_serve_command` | Port must be available (default: 5000) | Starts HTTP audit server |

### Approval Handlers

```python
# cli/_handlers/__init__.py (re-exported)
approval_list_command(args)
approval_approve_command(args)
approval_deny_command(args)
approval_grant_command(args)
approval_revoke_command(args)
approval_pending_command(args)
```

**Pre/Post Conditions (Approval Handlers)**:

| Handler | Pre-condition | Post-condition |
|---------|---------------|----------------|
| `approval_list_command` | Approval store accessible | Prints all approval entries |
| `approval_approve_command` | Approval request must exist | Request marked as approved |
| `approval_deny_command` | Approval request must exist | Request marked as denied |
| `approval_grant_command` | Grant scope and tool name valid | New grant created in store |
| `approval_revoke_command` | Grant must exist | Grant removed from store |
| `approval_pending_command` | Approval store accessible | Prints pending-approval items |

---

## Output Utilities (`_output.py`)

```python
def print_json(data: Any, *, indent: int = 2) -> None
def print_table(rows: list[dict], headers: list[str]) -> None
def print_error(message: str) -> None   # writes to stderr
def print_success(message: str) -> None
```

---

## Common CLI Flags

| Flag | Type | Description |
|------|------|-------------|
| `--workspace` | `str` | Workspace root (default: cwd) |
| `--permission-mode` | `str` | One of `PermissionMode` values |
| `--audit-level` | `str` | `L0`\|`L1`\|`L2`\|`L3` |
| `--require-plan` | `bool` | Enforce plan binding for writes |
| `--skip-plan-check` | `bool` | Override plan gate |
| _(removed)_ | _—_ | `--no-tui` was documented but never implemented; use `teeagent run` for non-interactive CLI mode |
| `--model` | `str` | Override LLM model |
| `--provider` | `str` | Override LLM provider |
| `--budget-cents` | `float` | Cost budget for the run |
