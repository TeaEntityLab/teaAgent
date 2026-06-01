# tui — Public API Reference

## `TUIApp`
**Location**: `tui/__init__.py`

Main Textual application class for the interactive terminal UI.

### `__init__`
```python
TUIApp(
    *,
    initial_task: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    workspace_root: Optional[Path] = None,
    permission_mode: Optional[str] = None,
    budget_cents: Optional[float] = None,
)
```
- `initial_task` — pre-populated task string submitted automatically on startup (TASK-DD2-001 fix)

### `run() -> None`
Starts the Textual event loop. Blocks until user exits (`/quit` or Ctrl-C).

**Pre/Post Conditions (TUIApp)**:

| Method | Pre-condition | Post-condition |
|--------|---------------|----------------|
| `__init__` | `workspace_root` must be a valid `Path` | `TUIApp` instance ready; layout not yet configured |
| `run()` | `TUIApp` must be initialized; `setup_tui()` called | Interactive chat session started; blocks until exit |

---

## TUI Setup (`_setup.py`)

```python
def setup_tui(app: TUIApp) -> None
```
Configures the Textual layout: input widget, output panel, cost display, approval subagent panel.

**Pre-condition**: `app` must be a valid `TUIApp` instance.  
**Post-condition**: Textual layout widgets mounted and ready for user interaction.

---

## TUI Commands (`_commands.py`)

Slash commands available in the TUI input:

| Command | Action |
|---------|--------|
| `/quit` | Exit TUI |
| `/reset` | Clear conversation and cost |
| `/history` | Show conversation history |
| `/help` | Show available commands |
| `/skill <name>` | Execute a skill |
| `/approval list` | Show pending approvals |
| `/model <name>` | Switch model mid-session |
| `/budget` | Show current cost vs budget |

```python
def handle_command(command: str, app: TUIApp) -> Optional[str]
# Returns a response string to display, or None to handle internally.
```

**Pre-condition**: `command` must be a non-empty string.  
**Post-condition**: Command executed; returns response `str` or `None`.

---

## TUI Approval Subagents (`_approval_subagents.py`)

```python
class ApprovalSubagentPanel:
    def show_approval_request(self, tool_name: str, arguments: dict) -> None
    def on_approve(self) -> None
    def on_deny(self) -> None
    def on_approve_session(self) -> None
```
Renders pending tool approval requests inline in the TUI. User approves/denies without leaving the chat.

**Pre/Post Conditions (ApprovalSubagentPanel)**:

| Method | Pre-condition | Post-condition |
|--------|---------------|----------------|
| `show_approval_request` | `tool_name` and `arguments` must be valid | Approval request rendered inline in TUI |
| `on_approve` | Approval request must be active | Request approved; tool execution proceeds |
| `on_deny` | Approval request must be active | Request denied; tool execution blocked |
| `on_approve_session` | Approval request must be active | All future requests for this session auto-approved |

---

## TUI Completion (`_completion.py`)

```python
class TUICompleter:
    def get_completions(self, text: str) -> list[str]
```
Tab-completion for slash commands and known tool names in the TUI input field.

---

## Key TUI Widgets (Textual layout)

| Widget | Purpose |
|--------|---------|
| `InputField` | User text input with history |
| `OutputPanel` | Streaming LLM response display |
| `CostBar` | Real-time cost / budget display |
| `ApprovalPanel` | Inline approval prompts |
| `StatusLine` | Current model, permission mode, session info |

---

## Session Cost Accumulation

Cost is accumulated in the TUI's `ChatSessionController` instance:
- Each `send_message()` call adds `LLMResponse.input_tokens` + `output_tokens` to session totals.
- `CostBar` widget is updated after each response.
- Budget enforcement: if `budget_cents` is set and `total_cost_cents` exceeds it, further messages are blocked.

**Known issue (CG-03)**: Cost may display as zero if `ChatSessionController.get_cost_summary()` is called before the first response completes. See `teaagent-daily-driver-p0-bugs.md`.
