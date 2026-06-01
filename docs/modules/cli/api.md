# cli — Public API Reference

## `main() -> int`
**Location**: `cli/__init__.py`

The package-level entry point. Parses CLI arguments and dispatches to handlers.

```python
from teaagent.cli import main
raise SystemExit(main())
```

**Returns**: Integer exit code (0 = success, 1 = error, 2 = usage error).

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

### Chat Handlers

```python
# cli/_handlers/_chat.py
chat_command(args)             # teaagent chat [task]
```

```python
# cli/_handlers/chat_repl.py
run_chat_repl(args)            # non-TUI REPL loop
```

### Audit Handlers

```python
# cli/_handlers/_audit.py
audit_list_command(args)       # teaagent audit list
audit_show_command(args)       # teaagent audit show <run_id>
audit_verify_command(args)     # teaagent audit verify <path>
audit_export_command(args)     # teaagent audit export
audit_serve_command(args)      # teaagent audit serve [--port]
```

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
| `--no-tui` | `bool` | Disable TUI, use REPL |
| `--model` | `str` | Override LLM model |
| `--provider` | `str` | Override LLM provider |
| `--budget-cents` | `float` | Cost budget for the run |
