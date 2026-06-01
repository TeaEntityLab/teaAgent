# hooks — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/hooks.py` | All hook types, `HookRegistry`, `HookConfig`, built-in hooks |

## Key Exports

### Protocol types (callable interfaces)
- `PreToolUseHookFn` — `(tool_name, arguments) -> dict | None`; raise `HookError` to veto
- `PostToolUseHookFn` — `(tool_name, arguments, result) -> dict | None`
- `SessionHookFn` — `(session_id, context) -> None`
- `PreCompactHookFn` — `(context) -> dict | None`

### Data classes
- `HookConfig` — holds lists of all 8 hook types + `enabled: bool`
- `HookRegistry` — wraps `HookConfig`, exposes `register_*` and `run_*` methods

### Exceptions
- `HookError` — raised by a pre-hook to veto; caught by the runner

### Enums
- `HookEvent` — 8 enum values (Claude Code compatible names)
- `HookPermissionMode` — `AUTO`, `ASK`, `ALLOW`, `DENY`

### Built-in hook factories (all return `PostToolUseHookFn` or `PreToolUseHookFn`)
- `lint_check_hook(root, *, tools)` — alias for `post_lint_check_hook`
- `post_lint_check_hook(root, *, tools)` — runs `ruff check` after write tools
- `run_tests_hook(root, *, tools, command)` — runs pytest after write tools
- `format_check_hook(root, *, tools)` — runs `ruff format` after write tools
- `shell_command_hook(command, *, tools, on_tools)` — arbitrary shell after write tools
- `permission_check_hook(mode, *, allow_patterns, deny_patterns, destructive_tools)` — PreToolUse veto
- `mcp_tool_filter_hook(allowed_tools, blocked_tools)` — PreToolUse MCP allow/block list
- `mcp_sampling_hook(max_tokens, temperature)` — PreToolUse sampling injection
- `context_file_loader_hook(root)` — SessionStart loader for CLAUDE.md/AGENTS.md

## Dependencies

```
hooks.py
  ├── stdlib: subprocess, dataclasses, enum, pathlib
  └── (lazy) teaagent.prompt.load_project_instructions  [context_file_loader_hook]
```

## Entry Points

1. `runner/_core.py` — creates `HookRegistry`, calls `run_pre_hooks` / `run_post_hooks` around each tool call
2. `chat_session_controller.py` — fires `run_session_start_hooks`, `run_session_end_hooks`
3. CLI `teaagent run --hook` flags would configure `HookRegistry` before hand-off

## Call Graph

```
runner._core: per tool call
  HookRegistry.run_pre_hooks(tool_name, arguments)
    └── for fn in config.pre_hooks: fn(tool_name, arguments)  # may raise HookError
  [tool executes]
  HookRegistry.run_post_hooks(tool_name, arguments, result)
    └── for fn in config.post_hooks: fn(tool_name, arguments, result)

runner._core: session lifecycle
  HookRegistry.run_session_start_hooks(session_id, context)
  HookRegistry.run_session_end_hooks(session_id, context)
```
