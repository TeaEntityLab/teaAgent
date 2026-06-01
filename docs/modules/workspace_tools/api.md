# workspace_tools — Public API Reference

## `WorkspaceToolConfig` (dataclass)
**Location**: `workspace_tools/_config.py`

```python
@dataclass
class WorkspaceToolConfig:
    root: Path
    max_write_bytes: int           # default: 10 MB
    max_read_bytes: int            # default: 1 MB
    gitignore_enabled: bool        # default: True
    shell_timeout_seconds: int     # default: 30
    allowed_shell_commands: Optional[frozenset[str]] = None

    @classmethod
    def from_root(cls, root: str | Path) -> 'WorkspaceToolConfig': ...
```

---

## `build_workspace_tool_registry`
**Location**: `workspace_tools/builder.py:39`
```python
def build_workspace_tool_registry(
    root: str | Path = '.',
    config_provider: Any = None,
) -> ToolRegistry
```
**Pre**: `root` must exist and be a directory.
**Post**: Returns populated `ToolRegistry` with all workspace tools registered.

---

## Tool Schemas

### `workspace_read_file`
```
Input:  { path: string (required), max_bytes: integer }
Output: { content: string, truncated: boolean, size_bytes: integer }
```

### `workspace_write_file`
```
Input:  { path: string (required), content: string (required) }
Output: { path: string, bytes_written: integer }
```
**Raises**: `ToolValidationError` if path escapes root or content exceeds `max_write_bytes`.

### `workspace_edit_at_hash`
```
Input:  { path: string, line_number: integer, hash: string, new_content: string }
Output: { path: string, line_number: integer }
```
**Raises**: `ToolValidationError` if `hash` doesn't match current line.

### `workspace_apply_patch`
```
Input:  { path: string, patch: string }  # unified diff format
Output: { path: string, hunks_applied: integer }
```

### `workspace_list_files`
```
Input:  { path: string, recursive: boolean, max_files: integer }
Output: { files: list[string], truncated: boolean }
```

### `workspace_search_files`
```
Input:  { query: string, path: string?, max_results: integer }
Output: { results: list[{path, line, content}] }
```

### `workspace_shell`
```
Input:  { command: string | list[string], timeout: integer? }
Output: { stdout: string, stderr: string, exit_code: integer }
```

### `git_status`
```
Output: { staged: list[string], unstaged: list[string], untracked: list[string] }
```

### `git_commit`
```
Input:  { message: string, files: list[string]? }
Output: { commit_hash: string, message: string }
```

---

## Helper Functions (`_helpers.py`)

### `resolve_workspace_path(root: Path, path_str: str) -> Path`
Raises `ToolValidationError` if resolved path is outside `root`.

### `compute_line_hash(content: str) -> str`
SHA-256 hex digest of line content (used by `workspace_edit_at_hash`).

### `format_hash_line(line_num: int, hash_str: str, content: str) -> str`
Returns formatted `L{n}:{hash}:{content}` string for agent display.

### `assert_write_size_allowed(content: str | bytes, max_bytes: int) -> None`
Raises `ToolValidationError` if `len(content) > max_bytes`.
