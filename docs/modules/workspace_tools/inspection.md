# workspace_tools — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/workspace_tools/__init__.py` | Package init |
| `teaagent/workspace_tools/_config.py` | `WorkspaceToolConfig`, gitignore loading |
| `teaagent/workspace_tools/_files.py` | File tool registrations (`register_workspace_tools`) |
| `teaagent/workspace_tools/_git.py` | Git tool implementations |
| `teaagent/workspace_tools/_helpers.py` | Path resolution, hash helpers, schema builders |
| `teaagent/workspace_tools/_shell.py` | `run_shell_inspect` and shell tool |
| `teaagent/workspace_tools/builder.py` | `build_workspace_tool_registry(root)` |
| `teaagent/workspace_tools/config_provider.py` | `StaticConfigProvider` for DI |
| `teaagent/workspace_tools/factory.py` | `ToolFactory` — creates tool handlers |
| `teaagent/workspace_tools/tool_classes.py` | Domain wrapper classes |

## Key Functions

### `build_workspace_tool_registry(root, config_provider?) -> ToolRegistry`
**Location**: `workspace_tools/builder.py:39`
Main entry point. Creates `WorkspaceToolConfig.from_root(root)`, instantiates `ToolFactory`, and calls `register_workspace_tools(registry, factory)`.

### `register_workspace_tools(registry, factory) -> None`
**Location**: `workspace_tools/_files.py:66`
Registers all file, search, and shell tools into the given `ToolRegistry`.

### `resolve_workspace_path(root, path_str) -> Path`
**Location**: `workspace_tools/_helpers.py`
Resolves and validates that `path_str` stays within `root`. Raises `ToolValidationError` on traversal.

### `compute_line_hash(line_content) -> str`
SHA-256 hex of the line content. Used by `workspace_edit_at_hash`.

## Dependencies

```
workspace_tools/_files.py
  ├── teaagent.tools.ToolAnnotations, ToolRegistry
  ├── teaagent.errors.ToolValidationError
  ├── teaagent.external_backends (FallbackKnowledgeBackend)
  ├── teaagent.hybrid_search
  └── teaagent.workspace_tools._helpers, ._config, ._shell
```

## Entry Points

1. `runner/_core.py` — calls `build_workspace_tool_registry(workspace_root)` during startup
2. `cli/_handlers/_agent.py` — passes workspace root from CLI args
3. `subagents/_tools.py` — creates per-subagent workspace registries (potentially with narrower root)
