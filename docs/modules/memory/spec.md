# memory — Behavior Specification

## Overview

The memory module provides persistent, structured storage for agent knowledge across runs. It manages four distinct concerns: tagged memory entries (catalog), failure experience cards, live pinned-file context, and team-shared markdown notes.

---

## Behavior Contract

### MemoryCatalog (`memory/catalog.py`)

| Guarantee | Detail |
|---|---|
| Append-only writes | `add()` always appends a new JSONL line; it never overwrites or re-sorts existing entries |
| Content non-empty | `add()` raises `ValueError('memory content cannot be empty')` if content strips to `''` |
| Readonly enforcement | All mutating operations (`add`, `add_quarantined`, `delete_*`, `quarantine_*`) raise `RuntimeError('Cannot … in readonly mode')` when `readonly=True` |
| Tag normalization | Tags are always lowercased, stripped, deduplicated, and sorted before storage |
| Search never returns empty for missing file | `list()` and `search()` return `[]` if the backing file does not exist — no exception |
| Show raises `FileNotFoundError` | `show(memory_id)` raises `FileNotFoundError` if `memory_id` is not found |
| Delete is atomic | `delete_by_branch` and `delete_by_run_id` in `memory/catalog.py` use `os.replace()` via `_atomic_write_entries()` for crash-safe rewrites |
| Cross-process locking | `memory/catalog.py` wraps `delete_*` and `quarantine_*` in `_cross_process_lock()` using `fcntl.flock(LOCK_EX)` |
| Quarantined entries isolated | Quarantined entries are written to `memory-quarantine.jsonl`, never to the active `memory.jsonl` |

### FailureCard / FailureCardStorage (`memory/failure_card.py`)

| Guarantee | Detail |
|---|---|
| TTL enforcement | `is_active()` returns `False` for any card where `expires_at` is set and `current_time >= expires_at` |
| Invalidation is permanent | Once `invalidated=True` is persisted, `is_active()` always returns `False` |
| `effective_behavior()` degrades safely | Returns `'ignore'` for inactive cards; only `'block'` for human-reviewed `high`-confidence cards with `warning_behavior=='block'` |
| Corruption tolerance | `_read_cards()` silently returns `[]` on `OSError` or `json.JSONDecodeError` |
| `apply_auto_invalidation()` is idempotent | Signatures are stored alongside cards; re-running on unchanged files produces no updates |

### PinnedFileStorage (`memory/pinned_file.py`)

| Guarantee | Detail |
|---|---|
| Secret files rejected | `add()` checks `_is_secret_filename()` before touching the filesystem; returns `False` and logs a warning on match |
| File existence required | `add()` checks `full_path.exists()` before pinning; returns `False` for non-existent paths |
| No duplicate pins | `add()` returns `False` if the file is already in the pinned list |
| Corruption tolerance | `_read_pinned_files()` silently returns `[]` on `OSError` or `json.JSONDecodeError` |

### TeamMemory (`memory/team_memory.py`)

| Guarantee | Detail |
|---|---|
| Append-only | `add()` always appends; never modifies existing lines |
| Token-capped injection | `inject_prompt()` caps output at approximately `limit_tokens * 4` characters by including the most-recent entries first |
| Missing file safe | `list()` returns `[]` if `team-memory.md` does not exist |

### MemoryHierarchy (three-tier, `memory/catalog.py`)

| Guarantee | Detail |
|---|---|
| Project-level is git-tracked | Stored at `<root>/.teaagent/memory.jsonl` |
| Personal-level is user-wide | Stored at `~/.config/teaagent/memory.jsonl`, never committed |
| Auto-memory is Claude-Code-compatible | Stored at `<root>/.claude/MEMORY.md` |
| `search_all()` returns keyed dict | Always returns `{'project': [...], 'personal': [...], 'auto_memory': [...]}` even if all are empty |

---

## Invariants

1. `MemoryEntry.memory_id` is always a non-empty string (hex UUID or uuid4 hex).
2. `MemoryEntry.content` is always a non-empty stripped string after construction.
3. `MemoryEntry.tags` is always a tuple (possibly empty) of lower-case, stripped strings.
4. `FailureCard.confidence` is always one of `{'low', 'medium', 'high'}`.
5. `FailureCard.warning_behavior` is always one of `{'info', 'warning', 'block'}`.
6. `PinnedFile.file_path` is always the relative path as provided (never resolved to absolute).
7. A card with `invalidated=True` is never considered active, regardless of `expires_at`.
8. The quarantine file (`memory-quarantine.jsonl`) only ever receives new appends — entries are never promoted back to `memory.jsonl` by this module.

---

## State Machines

### FailureCard Lifecycle

```
                   create()
                      |
                      v
              +----------------+
              |     ACTIVE     |  is_active() == True
              |  invalidated=F |
              |  expires_at?   |
              +----------------+
                  |        |
        invalidate()     TTL expires (expires_at <= now)
                  |        |
                  v        v
              +----------------+
              |   INACTIVE     |  is_active() == False
              |                |  effective_behavior() == 'ignore'
              +----------------+
```

### PlanMode state machine (in `plan_mode.py`, used by governance):

```
   DISABLED ---enable()---> ENABLED ---disable() [notes exist]--> CONFIRMING
      ^                         |                                      |
      |                         | disable() [no notes]           confirm_exit()
      |                         v                                      |
      +<-------------------_force_disable()<--------------------------+
                               (cancel_exit returns to ENABLED)
```

### MemoryCatalog Readonly State

```
   readonly=False   -- add/delete/quarantine allowed
   readonly=True    -- read operations only; any mutation raises RuntimeError
```

---

## Storage Paths Summary

| Component | Path |
|---|---|
| Memory catalog | `<root>/.teaagent/memory.jsonl` |
| Quarantine catalog | `<root>/.teaagent/memory-quarantine.jsonl` |
| Cross-process lock | `<root>/.teaagent/memory.lock` |
| Failure cards | `<root>/.teaagent/memory/failures.json` |
| Pinned files | `<root>/.teaagent/memory/pinned.json` |
| Team memory | `<root>/.teaagent/team-memory.md` |
| Auto-memory | `<root>/.claude/MEMORY.md` |
| Personal memory | `~/.config/teaagent/memory.jsonl` |

> **Note:** The `pinned_file` sub-module provides pinned file watching and path validation utilities. See [`pinned_file`](../pinned_file/spec.md) for details.
