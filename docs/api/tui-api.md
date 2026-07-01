# TUI API Specification

The TUI (Terminal UI) is a `prompt_toolkit`-based interactive shell that wraps the REPL. It is entered via `teaagent chat`, `teaagent tui`, or the `chat` REPL command.

**Source:** `teaagent/tui/__init__.py`

---

## Startup Parameters

`TeaAgentTUI` is the top-level class. Its constructor parameters become the initial session state:

```python
TeaAgentTUI(
    database: str = ':memory:',
    provider: Optional[str] = None,
    model: Optional[str] = None,
    root: str | Path = '.',
    allow_destructive: bool = False,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    input_fn: Callable = input,
    output_fn: Callable = print,
    adapter_factory: Optional[Callable] = None,
    initial_task: Optional[str] = None,   # passed from `teaagent chat "task"`
    session_id: Optional[str] = None,
    progress: bool = False,
    stream: bool = False,
    subagent: bool = False,
    route_model: bool = False,
    heartbeat: int = 0,
)
```

If `initial_task` is set, the TUI runs it immediately after the REPL loop starts, before accepting user input.

---

## Session State

The TUI tracks the following mutable state during a session:

| Property | Type | Description |
|----------|------|-------------|
| `database` | `str` | Active GraphQLite DB path |
| `provider` | `Optional[str]` | Active LLM provider |
| `model` | `Optional[str]` | Model override (None = provider default) |
| `route_model_enabled` | `bool` | Task-based model routing active |
| `root` | `Path` | Workspace root |
| `allow_destructive` | `bool` | Destructive tools permitted |
| `permission_mode` | `PermissionMode` | Current permission mode |
| `progress` | `bool` | Progress streaming active |
| `stream` | `bool` | Token streaming active |
| `subagent` | `bool` | Subagent tool exposed |
| `chat` | `bool` | Multi-turn chat mode active |
| `session_id` | `Optional[str]` | Active session ID |
| `pinned_files` | `list[Path]` | Files injected on every run |
| `approved_call_ids` | `set[str]` | In-flight JIT/session-approved call IDs |
| `heartbeat` | `int` | Heartbeat interval (seconds) |
| `effort` | `str` | Effort level (low/normal/high/unlimited) |

State is persisted to `.teaagent/tui_state.json` between sessions.

---

## Keybindings

The TUI uses `prompt_toolkit` with standard readline keybindings. Custom bindings:

### Input Editing

| Key | Action |
|-----|--------|
| `Enter` | Submit command |
| `Ctrl+J` | Submit command (alternative) |
| `Ctrl+C` | Cancel current input / interrupt running task |
| `Ctrl+D` | EOF — exit TUI if input is empty |
| `Ctrl+L` | Clear the screen |
| `Tab` | Trigger auto-complete (paths, `@`-mentions, command names) |
| `Shift+Tab` | Cycle auto-complete backwards |
| `Ctrl+R` | Reverse-search command history |
| `↑` / `↓` | Navigate command history |
| `Alt+Enter` | Insert a newline (multi-line input) |

### Standard Readline Editing

| Key | Action |
|-----|--------|
| `Ctrl+A` | Move cursor to start of line |
| `Ctrl+E` | Move cursor to end of line |
| `Ctrl+W` | Delete word before cursor |
| `Ctrl+U` | Delete to start of line |
| `Ctrl+K` | Delete to end of line |
| `Ctrl+F` / `→` | Move cursor forward one character |
| `Ctrl+B` / `←` | Move cursor back one character |
| `Alt+F` | Move cursor forward one word |
| `Alt+B` | Move cursor back one word |

### Conflict Resolution Mode

Active only when `conflict` command is entered:

| Key | Action |
|-----|--------|
| `o` | Accept current branch (ours) for focused file |
| `t` | Accept incoming branch (theirs) for focused file |
| `n` | Next conflicted file |
| `p` | Previous conflicted file |
| `a` | Abort the merge entirely |

---

## UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  teaagent  [provider: claude]  [model: opus-4-8]        │  ← Header bar
│  root: /Users/me/project  [mode: prompt]  [chat: on]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Output pane (scrollable)                               │
│                                                         │
│  > run "add pagination to /users"                       │
│                                                         │
│  [progress] Analysing codebase...                       │
│  [tool]     read_file(src/routes/users.py)              │
│  [tool]     write_file(src/routes/users.py) [approved]  │
│                                                         │
│  Done. Added cursor-based pagination with page_size     │
│  and cursor query parameters. See src/routes/users.py.  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  > _                                                    │  ← Input pane
└─────────────────────────────────────────────────────────┘
│  cost: $0.03  tokens: 2,104  session: abc123            │  ← Status bar
```

---

## State Transitions

### Normal → Chat Mode

```
(normal)  chat on  →  (chat-mode)
                        messages accumulate across runs
(chat-mode)  chat off  →  (normal)
(chat-mode)  session clear  →  (chat-mode, empty history)
(chat-mode)  session switch <id>  →  (chat-mode, loaded history)
```

### Normal → Conflict Mode

```
(normal)  conflict  →  (conflict-mode)
(conflict-mode)  o / t  →  file accepted, advance to next
(conflict-mode)  n / p  →  navigate files
(conflict-mode)  a  →  merge aborted, (normal)
(conflict-mode, all files resolved)  →  (normal)
```

### Normal → Parallel Mode

```
(normal)  parallel <opt1> <opt2>  →  (parallel-mode)
(parallel-mode)  select <N>  →  branch N merged, (normal)
(parallel-mode)  cancel  →  branches discarded, (normal)
```

### Normal → Background

```
(normal)  background  →  session suspended, TUI exits
  teaagent attach <run_id>  →  (normal, streamed output)
  teaagent resume <run_id>  →  (normal, replayed from checkpoint)
```

---

## Auto-Complete

The TUI provides tab-completion for:

| Context | Completions |
|---------|-------------|
| First token | All REPL command names |
| `provider <TAB>` | All registered provider names |
| `model <TAB>` | Models for the current provider |
| `permission <TAB>` | All permission mode names |
| `session switch <TAB>` | Saved session IDs |
| `@<TAB>` | Workspace files relative to `root` |
| `resume <TAB>` | Persisted run IDs |
| `approve <TAB>` | Pending approval call IDs |
| `show <TAB>` | Persisted run IDs |

---

## Output Conventions

### Event Prefixes (progress mode)

| Prefix | Meaning |
|--------|---------|
| `[progress]` | Agent reasoning step or status update |
| `[tool]` | Tool call being made |
| `[approved]` | Tool call was approved |
| `[denied]` | Tool call was denied |
| `[heartbeat]` | Liveness heartbeat |
| `[error]` | Error during execution |
| `[cost]` | Cost checkpoint |

### Inline Approval Prompt

When `permission-mode` is `prompt` and a destructive tool is about to run:

```
Approval required
  Tool:      write_file
  Call ID:   call_abc123
  Arguments: {"path": "src/auth.py", "content": "..."}
  Risk:      destructive, stateful

  [a]pprove once  [s]ession  [d]eny  [q]uit run
```

Keys: `a` = approve this call only, `s` = approve tool for session, `d` = deny, `q` = abort the run.

---

## Persistence

State saved to `.teaagent/tui_state.json` on clean exit:

```json
{
  "provider": "claude",
  "model": null,
  "root": "/Users/me/project",
  "allow_destructive": false,
  "permission_mode": "prompt",
  "progress": true,
  "stream": false,
  "subagent": false,
  "chat": false,
  "session_id": "abc123",
  "pinned_files": ["src/auth.py"],
  "heartbeat": 0,
  "effort": "normal",
  "route_model_enabled": false
}
```

Command history is stored by `prompt_toolkit` in `~/.teaagent/repl_history`.

---

## Programmatic Entry

To embed the TUI in another application:

```python
from teaagent.tui import TeaAgentTUI
from teaagent.policy import PermissionMode

tui = TeaAgentTUI(
    provider='claude',
    root='/path/to/project',
    permission_mode=PermissionMode.WORKSPACE_WRITE,
    initial_task='summarise recent changes',
)
exit_code = tui.run_repl()
```

`run_repl()` blocks until the user exits and returns an integer exit code (0 = clean exit, non-zero = error).
