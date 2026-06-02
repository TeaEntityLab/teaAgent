# pinned_file — Public API Reference

## Data Models

### `PinnedFile`
| Field | Type | Description |
|---|---|---|
| `file_path` | `str` | Workspace-relative file path. |
| `pinned_at` | `float` | Pin timestamp (Unix). |
| `last_modified` | `float` | Last tracked update timestamp (Unix). |

### `PinnedFileStorage`
| Field | Type | Description |
|---|---|---|
| `root` | `Path` | Resolved workspace root. |
| `storage_file` | `Path` | Backing file `.teaagent/memory/pinned.json`. |

## Functions

### `PinnedFile.create(file_path: str) -> PinnedFile`
**Location**: `teaagent/memory/pinned_file.py:77`
**Pre-condition**: `file_path` is a workspace-relative path string.
**Post-condition**: Returns new pinned record with current timestamps.

### `PinnedFileStorage.add(file_path: str) -> bool`
**Location**: `teaagent/memory/pinned_file.py:199`
**Pre-condition**: Path is relative, in-workspace, non-secret pattern, and exists.
**Post-condition**: Persists new pinned entry and returns `True`; otherwise `False`.

### `PinnedFileStorage.remove(file_path: str) -> bool`
**Location**: `teaagent/memory/pinned_file.py:242`
**Pre-condition**: Path is relative and in-workspace.
**Post-condition**: Removes entry when present and returns `True`; else `False`.

### `PinnedFileStorage.list_all() -> list[PinnedFile]`
**Location**: `teaagent/memory/pinned_file.py:272`
**Pre-condition**: None.
**Post-condition**: Returns all pinned entries; corrupted storage yields empty list.

### `PinnedFileStorage.update_last_modified(file_path: str) -> bool`
**Location**: `teaagent/memory/pinned_file.py:285`
**Pre-condition**: Path is relative and in-workspace.
**Post-condition**: Updates matching entry timestamp if found.

### `PinnedFileStorage.is_pinned(file_path: str) -> bool`
**Location**: `teaagent/memory/pinned_file.py:320`
**Pre-condition**: None.
**Post-condition**: Returns whether path is currently pinned.
