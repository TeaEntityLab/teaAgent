# Memory Module — Inspection

## Purpose

The memory module implements persistent knowledge management for TeaAgent across runs and processes. It stores four kinds of data:

1. **Tagged memory entries** (`MemoryCatalog`) — arbitrary text notes tagged and searchable, scoped optionally by branch or run.
2. **Failure experience cards** (`FailureCardStorage`) — structured records of agent task failures with TTL, confidence, and auto-invalidation.
3. **Pinned file context** (`PinnedFileStorage`) — a registry of files the agent should keep in live context, with secret-file protection.
4. **Team-shared notes** (`TeamMemory`) — append-only Markdown log shared among team members.

A fifth concern, `MemoryHierarchy`, unifies the three tiers (project, personal, auto-memory) into a single interface.

---

## Module Layout

```
teaagent/memory/
  __init__.py          -- public re-export surface
  catalog.py           -- MemoryEntry, MemoryCatalog, MemoryHierarchy (canonical)
  failure_card.py      -- FailureCard, FailureCardStorage, AutoInvalidationRule
  file_watcher.py      -- FileWatcher, FileChangeHandler (watchdog-backed)
  pinned_file.py       -- PinnedFile, PinnedFileStorage
  team_memory.py       -- TeamMemory

teaagent/memory_legacy.py  -- compatibility re-export of memory.catalog
```

> **Status 2026-06-04:** `memory/catalog.py` is the authoritative
> implementation. `memory/__init__.py` and `memory_legacy.py` both re-export the
> same `MemoryCatalog`, `MemoryEntry`, and helper functions for compatibility.
> The old near-duplicate implementation risk is closed, and
> `tests/test_circular_imports.py::test_memory_catalog_canonical_export_path`
> guards the import contract.

---

## Dependencies

### External

| Library | Used in | Purpose |
|---|---|---|
| `watchdog` | `file_watcher.py` | Filesystem event monitoring (optional; `WATCHDOG_AVAILABLE` flag) |
| `fcntl` | `catalog.py` | Cross-process file locking (Unix only; graceful fallback on Windows) |

### Internal

| Import | Used in | Purpose |
|---|---|---|
| `teaagent.audit.utc_now` | `catalog.py` | Timestamp generation |
| `teaagent.storage.append_jsonl_line` | `catalog.py` | Safe JSONL append |

---

## Exported Symbols (`__init__.py`)

```python
from teaagent.memory import (
    FailureCard,
    FailureCardStorage,
    PinnedFile,
    PinnedFileStorage,
    FileWatcher,
    TeamMemory,
    MemoryCatalog,          # from memory.catalog
    MemoryEntry,            # from memory.catalog
    memory_entries_to_prompt,  # from memory.catalog
    memory_entry_from_payload, # from memory.catalog
)
```

---

## Entry Points

| Caller | Uses |
|---|---|
| `context_pack.py::build_context_pack()` | `MemoryCatalog` — searches memory for task-relevant entries |
| `sandbox/_parallel_experiment.py::cleanup_all()` | `MemoryCatalog.quarantine_by_branch()` — quarantines experiment branch memories |
| `plan.py` (via `PreflightReport`) | `MemoryCatalog` — injects matched memories into plan artifacts |
| Agent task runners | `FailureCardStorage` — stores/retrieves failure cards per run |
| TUI / CLI | `PinnedFileStorage`, `TeamMemory` — user-facing memory management commands |
| `FileWatcher` consumers | `PinnedFileStorage.list_all()` to build watched file set |

---

## Call Graph

### MemoryCatalog (authoritative: `memory/catalog.py`)

```
MemoryCatalog.add()
  -> normalize_tags()
  -> append_jsonl_line()

MemoryCatalog.search()
  -> _read_entries()
     -> memory_entry_from_payload()
  -> memory_matches()
  -> memory_relevance_score()

MemoryCatalog.delete_by_branch()
  -> _cross_process_lock()   [fcntl.flock on memory.lock]
  -> _read_entries()
  -> _atomic_write_entries() [os.replace temp file]

MemoryCatalog.quarantine_by_branch()
  -> _cross_process_lock()
  -> _read_entries()
  -> _atomic_write_entries()
  -> append_jsonl_line()     [writes to quarantine file]
```

### FailureCardStorage

```
FailureCardStorage.append()
  -> _read_cards()
  -> _write_cards()

FailureCardStorage.apply_auto_invalidation()
  -> MemoryAutoInvalidationConfig.from_workspace_config()
  -> _read_cards()
  -> _compute_file_signature()   [hashlib.sha256]
  -> _write_cards()

FailureCardStorage.find_matching()
  -> list_active()
     -> list_all()
        -> _read_cards()
        -> FailureCard.from_dict()
     -> FailureCard.is_active()
```

### FileWatcher

```
FileWatcher.start()
  -> FileChangeHandler.__init__()
  -> Observer.schedule()
  -> Observer.start()

FileChangeHandler.on_modified()
  -> debounce check (threading.Lock)
  -> callback(file_path, 'modified')

FileChangeHandler.on_deleted()
  -> callback(file_path, 'deleted')
```

### MemoryHierarchy (`memory/catalog.py`)

```
MemoryHierarchy.search_all()
  -> project.search()
  -> personal.search()
  -> load_auto_memory()

MemoryHierarchy.to_prompt_context()
  -> project.list()
  -> personal.list()
  -> load_auto_memory()
```

---

## Cross-Module Relationships

```
context_pack.py
  --> MemoryCatalog.search()        (task-relevant memory injection)

sandbox/_parallel_experiment.py
  --> MemoryCatalog.quarantine_by_branch()   (cleanup on branch delete)

plan.py (PreflightReport)
  --> MemoryCatalog (via context_pack)       (plan memory injection)
```
