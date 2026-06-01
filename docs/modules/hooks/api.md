# hooks — Public API Reference

## Enums

### `HookEvent`
```python
class HookEvent(Enum):
    SESSION_START = 'SessionStart'
    USER_PROMPT_SUBMIT = 'UserPromptSubmit'
    PRE_TOOL_USE = 'PreToolUse'
    POST_TOOL_USE = 'PostToolUse'
    PRE_COMPACT = 'PreCompact'
    STOP = 'Stop'
    SUBAGENT_STOP = 'SubagentStop'
    SESSION_END = 'SessionEnd'
```

### `HookPermissionMode`
```python
class HookPermissionMode(Enum):
    AUTO = 'auto'   # same as ASK
    ASK = 'ask'     # block destructive_tools
    ALLOW = 'allow' # no restriction
    DENY = 'deny'   # block everything
```

---

## `HookError(Exception)`
Raised by a `PreToolUseHookFn` to veto the tool call. Message is surfaced to the user.

---

## `HookConfig` (dataclass)
```python
@dataclass
class HookConfig:
    pre_hooks: list[PreToolUseHookFn]
    post_hooks: list[PostToolUseHookFn]
    session_start_hooks: list[SessionHookFn]
    session_end_hooks: list[SessionHookFn]
    user_prompt_submit_hooks: list[SessionHookFn]
    pre_compact_hooks: list[PreCompactHookFn]
    stop_hooks: list[SessionHookFn]
    subagent_stop_hooks: list[SessionHookFn]
    enabled: bool = True
```

---

## `HookRegistry` (dataclass)

### Registration methods
```python
register_pre_hook(fn: PreToolUseHookFn) -> None
register_post_hook(fn: PostToolUseHookFn) -> None
register_session_start_hook(fn: SessionHookFn) -> None
register_session_end_hook(fn: SessionHookFn) -> None
register_user_prompt_submit_hook(fn: SessionHookFn) -> None
register_pre_compact_hook(fn: PreCompactHookFn) -> None
register_stop_hook(fn: SessionHookFn) -> None
register_subagent_stop_hook(fn: SessionHookFn) -> None
```

### Execution methods
```python
run_pre_hooks(tool_name: str, arguments: dict) -> dict | None
```
Runs all pre-hooks in order. Returns final modified args, or raises `HookError`.

```python
run_post_hooks(tool_name: str, arguments: dict, result: dict) -> dict | None
```
Runs all post-hooks in order. Returns final modified result or `None`.

```python
run_session_start_hooks(session_id: str, context: dict) -> None
run_session_end_hooks(session_id: str, context: dict) -> None
run_user_prompt_submit_hooks(session_id: str, context: dict) -> None
run_stop_hooks(session_id: str, context: dict) -> None
run_subagent_stop_hooks(session_id: str, context: dict) -> None
run_pre_compact_hooks(context: dict) -> dict | None
```

---

## Built-in Hook Factories

### `post_lint_check_hook(root, *, tools) -> PostToolUseHookFn`
- Runs `ruff check <root>` after file-write tools.
- Raises `HookError` with first 500 chars of stderr on lint failure.
- Silently skips if `ruff` not installed.

### `run_tests_hook(root, *, tools, command?) -> PostToolUseHookFn`
- Default command: `['uv', 'run', 'pytest', 'tests/', '-x', '-q']`
- 120-second timeout.
- Raises `HookError` on failure; skips if command not found.

### `format_check_hook(root, *, tools) -> PostToolUseHookFn`
- Runs `ruff format <root>`.
- 30-second timeout.

### `shell_command_hook(command, *, tools?, on_tools?) -> PostToolUseHookFn`
- Runs arbitrary shell command via `shlex.split` + `subprocess.run(shell=False)`.
- 30-second timeout (hardcoded, not configurable).

### `permission_check_hook(mode, *, allow_patterns, deny_patterns, destructive_tools) -> PreToolUseHookFn`
- Raises `HookError` for `DENY` mode or tools in `destructive_tools` when mode is `ASK`/`AUTO`.
- Path glob matching via `fnmatch`.

### `mcp_tool_filter_hook(allowed_tools, blocked_tools) -> PreToolUseHookFn`
- Raises `HookError` if tool_name in `blocked_tools` or not in `allowed_tools`.

### `mcp_sampling_hook(max_tokens, temperature) -> PreToolUseHookFn`
- Injects `_sampling` key into arguments for `mcp_*` tool names.

### `context_file_loader_hook(root) -> SessionHookFn`
- SessionStart hook that reads `CLAUDE.md`/`AGENTS.md` via `load_project_instructions(root)`.
- Writes result to `context['project_instructions']`.
