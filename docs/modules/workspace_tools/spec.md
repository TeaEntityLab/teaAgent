# workspace_tools — Behavior Specification

## Purpose

Provides the concrete tool implementations that agents use to interact with the filesystem, git, and shell within a workspace root. All file operations are path-sandboxed to the workspace root.

## Behavior Contract

1. **Path sandboxing** — every file operation resolves the path relative to `workspace_root` and rejects any path that escapes it (path traversal prevention via `resolve_workspace_path`).
2. **Write size limits** — `workspace_write_file` and `workspace_apply_patch` enforce a maximum write size (from `WorkspaceToolConfig.max_write_bytes`).
3. **Hash-anchored edits** — `workspace_edit_at_hash` requires the caller to provide the current line's SHA-256 hash, preventing stale edits to files changed since the agent last read them.
4. **Gitignore respect** — `workspace_list_files` and `workspace_search_files` filter out paths matching `.gitignore` patterns when configured.
5. **Shell isolation** — `workspace_shell` runs commands in the workspace root with a timeout; environment is sanitized.
6. **Knowledge backend fallback** — search/parse operations use `FallbackKnowledgeBackend` which chains code-analysis backends and falls back gracefully when none are available.

## Tool Inventory

| Tool name | Category | Read-only? | Destructive? |
|-----------|----------|-----------|-------------|
| `workspace_read_file` | Files | Yes | No |
| `workspace_write_file` | Files | No | Yes |
| `workspace_apply_patch` | Files | No | Yes |
| `workspace_edit_at_hash` | Files | No | Yes |
| `workspace_list_files` | Files | Yes | No |
| `workspace_search_files` | Files | Yes | No |
| `workspace_search_code` | Code | Yes | No |
| `workspace_parse_code` | Code | Yes | No |
| `workspace_shell` | Shell | No | Yes |
| `git_status` | Git | Yes | No |
| `git_diff` | Git | Yes | No |
| `git_commit` | Git | No | Yes |
| `git_log` | Git | Yes | No |

## Invariants

- No tool may read or write outside `workspace_root`.
- `workspace_edit_at_hash` fails if the provided hash does not match the current line content.
- Shell timeout is always finite; no tool hangs indefinitely.
