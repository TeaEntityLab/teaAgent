# chat_session_controller — Public API Reference

## `ChatSessionController`
**Location**: `chat_session_controller.py`

Primary class managing a stateful chat session (conversation history, cost, model config).

### `__init__`
```python
ChatSessionController(
    provider: str,
    model: str,
    *,
    system_prompt: Optional[str] = None,
    workspace_root: Optional[Path] = None,
    audit_logger: Optional[AuditLogger] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    budget_cents: Optional[float] = None,
    tool_registry: Optional[ToolRegistry] = None,
)
```

### `send_message`
```python
async def send_message(
    self,
    user_message: str,
    *,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str
```
- **Pre**: Controller is initialized and not exceeded budget.
- **Post**: User message and assistant response appended to `conversation_history`.
- **Returns**: Full assistant response string.
- **Raises**: `BudgetExceededError` if `budget_cents` is set and exceeded.
- **Side effects**: Fires tool calls if LLM requests them; records audit events.

### `get_conversation_history`
```python
def get_conversation_history(self) -> list[dict[str, Any]]
# Returns: [{'role': 'user'|'assistant', 'content': str}, ...]
```

### `get_cost_summary`
```python
def get_cost_summary(self) -> dict[str, Any]
# Returns: {'total_cost_cents': float, 'input_tokens': int, 'output_tokens': int}
```

### `reset`
```python
def reset(self) -> None
# Clears conversation history and resets cost counters.
```

### `close`
```python
async def close(self) -> None
# Fires session end hooks; persists session state if configured.
```

---

## `chat_command` handler
**Location**: `cli/_handlers/_chat.py`

```python
def chat_command(args: argparse.Namespace) -> int
```

Dispatcher:
- `args.task` — initial task string (may be empty)
- _(removed)_ — `--no-tui` was documented but never implemented
- TTY detected → `TUIApp(initial_task=args.task).run()`
- No TTY → `run_chat_completion(args)` (single shot)

---

## Chat REPL (`chat_repl.py`)

```python
def run_chat_repl(args: argparse.Namespace) -> int
```
Line-buffered REPL. Reads from stdin, sends to `ChatSessionController.send_message()`, prints to stdout. Supports `/quit`, `/reset`, `/history` slash commands.

---

## Data Structures

### Conversation history entry
```python
{'role': 'user' | 'assistant', 'content': str}
```

### Cost summary
```python
{
    'total_cost_cents': float,
    'input_tokens': int,
    'output_tokens': int,
    'turn_count': int,
}
```
