# tools — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/tools.py` | `ToolRegistry`, `ToolDefinition`, `ToolAnnotations`, `ToolRateLimit` |
| `teaagent/tool_call_context.py` | Thread-local tool call context (call_id, run_id) |
| `teaagent/tool_permissions.py` | Permission checks per tool |
| `teaagent/workspace_tools/tool_classes.py` | Domain tool class wrappers |
| `teaagent/workspace_tools/builder.py` | `build_workspace_tool_registry()` |
| `teaagent/workspace_tools/factory.py` | `ToolFactory` — DI-friendly tool creation |

## Key Exports (`tools.py`)

- `ToolAnnotations` — frozen dataclass: `read_only`, `destructive`, `idempotent`, `stateful`, `security_tier`
- `ToolRateLimit` — frozen dataclass: `max_calls`, `window_seconds`
- `ToolDefinition` — frozen dataclass: all tool metadata + `handler`; `get_security_tier()` method
- `ToolHandler = Callable[[dict], dict]`
- `ToolRegistry` — the registry class (see API doc)

## Dependencies

```
tools.py
  ├── teaagent.errors.ToolExecutionError
  ├── teaagent.hooks.HookError, HookRegistry
  ├── teaagent.schema.validate_object_schema
  └── teaagent.tool_call_context.get_tool_call_context
```

## Entry Points

1. `runner/_core.py` — holds a `ToolRegistry`, dispatches all tool calls through `registry.call(name, arguments)`
2. `workspace_tools/builder.py` — `build_workspace_tool_registry(root)` creates registry with workspace tools
3. `subagents/_tools.py` — builds subagent-specific tool registries
4. `mcp_tool_adapter.py` — wraps MCP tools as `ToolDefinition` entries

## Call Graph

```
runner._core.AgentRunner._dispatch_tool_call(tool_name, arguments)
  └── ToolRegistry.call(tool_name, arguments)
        ├── _validate_schema(arguments)
        ├── _check_rate_limit(tool_name)
        ├── hook_registry.run_pre_hooks(tool_name, arguments)
        ├── definition.handler(arguments)
        └── hook_registry.run_post_hooks(tool_name, arguments, result)
```
