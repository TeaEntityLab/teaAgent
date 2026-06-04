# Memory Module — Risks, Failure Modes, and Edge Cases

---

## Risk Vectors

### MEM-R-001: Duplicate `MemoryCatalog` Implementation

**File:** `memory/catalog.py` vs `memory_legacy.py`

**Status 2026-06-04: Closed / regression-guarded.**

Historical risk: both files defined `MemoryEntry`, `MemoryCatalog`,
`normalize_tags`, `memory_matches`, `memory_relevance_score`,
`memory_entry_from_payload`, and `memory_entries_to_prompt`.

Current reality:

- `memory/catalog.py` is canonical.
- `memory/__init__.py` re-exports from `memory.catalog`.
- `memory_legacy.py` is a compatibility re-export of `memory.catalog`.
- `tests/test_circular_imports.py::test_memory_catalog_canonical_export_path`
  proves that public, package-level, canonical, and legacy imports resolve to
  the same `MemoryCatalog` class.

Residual risk: a future edit could accidentally reintroduce logic into
`memory_legacy.py`. Keep the regression guard and avoid adding new behavior to
the compatibility module.

---

### MEM-R-002: Cross-Process Lock is Unix-Only

**File:** `memory/catalog.py`, `_cross_process_lock()`

`_cross_process_lock()` uses `fcntl.flock`. On Windows or platforms without `fcntl`:

```python
except (ImportError, OSError):
    pass  # gracefully fall back to no locking
```

This means concurrent sub-agent processes on Windows can corrupt
`memory.jsonl` via torn read-modify-write cycles. The compatibility module no
longer owns the lock implementation.

---

### MEM-R-003: `catalog.py` Uses Non-Atomic Rewrites

**Status 2026-06-04: Closed for `delete_by_branch()` and `delete_by_run_id()`.**

`delete_by_branch()` and `delete_by_run_id()` now call `_atomic_write_entries()`,
which writes a temp file and swaps it into place via `os.replace()`.

Residual risk: other JSON-file stores in the memory module may still use direct
read-modify-write paths and should be evaluated separately.

---

### MEM-R-004: `FailureCardStorage` Reads/Writes Full JSON Array

**File:** `memory/failure_card.py`, lines 256–277

Every call to `append()`, `invalidate()`, or `prune_expired()` reads the entire `failures.json` into memory, modifies it, and writes it back. For large failure histories this is O(n) I/O per operation and can be slow. There is no streaming or JSONL format here.

---

### MEM-R-005: `FailureCardStorage._write_cards()` Silently Swallows `OSError`

**File:** `memory/failure_card.py`, lines 268–277

```python
except OSError as exc:
    logger.warning('Failed to write failure cards: %s', exc)
```

A disk-full or permission error causes a write to silently fail. The caller receives no error, and the in-memory mutation is lost. Same for `PinnedFileStorage._write_pinned_files()` at line 159.

---

### MEM-R-006: `FileWatcher` Is Optional but Raises on Construction

**File:** `memory/file_watcher.py`, lines 165–169

If `watchdog` is not installed, constructing a `FileWatcher` raises `ImportError`. However, at import time `WATCHDOG_AVAILABLE = False` is set and dummy types are defined. Any code that unconditionally constructs `FileWatcher(...)` without checking `WATCHDOG_AVAILABLE` first will raise at runtime.

---

### MEM-R-007: Debounce Uses Wall Clock and `threading.Lock`, Not Process-Safe

**File:** `memory/file_watcher.py`, lines 108–113

Debounce logic in `FileChangeHandler.on_modified()` uses `time.time()` and a thread lock. If two rapid events arrive on different threads but within the debounce window, the second is silently dropped. The suppressed callback invocation at line 116 (`with suppress(Exception)`) means any exception in the user's callback is silently lost.

---

### MEM-R-008: Secret File Detection is Filename-Only, Not Content-Based

**File:** `memory/pinned_file.py`, lines 162–197

`_is_secret_filename()` only checks filename patterns, not file contents. A secret stored in a file named `config.txt` or `settings.py` will not be caught. The docstring explicitly notes this ("Uses filename-only heuristics — never reads file contents").

---

### MEM-R-009: `PinnedFile.from_dict()` Has No Validation

**File:** `memory/pinned_file.py`, line 110

```python
return cls(**data)
```

If the stored JSON is missing `file_path`, `pinned_at`, or `last_modified`, this raises `TypeError`. Unlike `FailureCard.from_dict()` (line 225) which filters to known fields, `PinnedFile.from_dict()` passes the full dict directly.

---

### MEM-R-010: `TeamMemory.inject_prompt()` Token Estimate is a 4:1 Char Heuristic

**File:** `memory/team_memory.py`, line 54

```python
char_budget = limit_tokens * 4
```

This approximation will over-include for CJK or emoji-heavy content (1–2 chars per token) and under-include for whitespace-heavy prose. The actual injected prompt may significantly exceed `limit_tokens`.

---

### MEM-R-011: `MemoryHierarchy.search_all()` `auto_memory` Match is Substring-Only

**File:** `memory/catalog.py`, `MemoryHierarchy.search_all()`

```python
if query.lower() in auto_content.lower():
    results['auto_memory'] = [MemoryEntry(memory_id='auto-memory-1', content=auto_content[:500], ...)]
```

Only the first 500 chars of the auto-memory file are returned as a single synthetic entry, regardless of document size. If the query matches late in a long file, the returned content may not contain the relevant section.

---

### MEM-R-012: `apply_auto_invalidation()` Key `file_signature` Not in `FailureCard` Dataclass

**File:** `memory/failure_card.py`, lines 406–419

`item['file_signature'] = current_sig` stores extra keys directly in the raw dict. These keys are not part of the `FailureCard` dataclass fields. `FailureCard.from_dict()` at line 225 filters only known fields, so file signatures survive serialization in the raw JSON but are invisible after deserialization via `from_dict()`. This means `apply_auto_invalidation()` always re-stores signatures on each invocation for already-signature-stored cards.

---

## Known Issues Summary Table

| ID | File | Line | Severity | Description |
|---|---|---|---|---|
| MEM-R-001 | `memory_legacy.py` | module | Closed | Compatibility re-export; guarded by canonical import-path test |
| MEM-R-002 | `memory/catalog.py` | `_cross_process_lock()` | Medium | No cross-process locking on Windows |
| MEM-R-003 | `memory/catalog.py` | `delete_by_*` | Closed | Atomic rewrite now uses `os.replace()` |
| MEM-R-004 | `memory/failure_card.py` | 247–277 | Low | Full JSON array read-write O(n) per operation |
| MEM-R-005 | `memory/failure_card.py` | 268–277 | Medium | OSError on write silently swallowed |
| MEM-R-006 | `memory/file_watcher.py` | 165–169 | Low | ImportError if watchdog absent and FileWatcher constructed |
| MEM-R-007 | `memory/file_watcher.py` | 116 | Low | Callback exceptions silently suppressed |
| MEM-R-008 | `memory/pinned_file.py` | 162–197 | Medium | Filename-only secret detection |
| MEM-R-009 | `memory/pinned_file.py` | 110 | Medium | `PinnedFile.from_dict()` no field validation |
| MEM-R-010 | `memory/team_memory.py` | 54 | Low | Inaccurate token estimate for inject_prompt |
| MEM-R-011 | `memory/catalog.py` | `MemoryHierarchy.search_all()` | Low | Auto-memory search returns truncated content |
| MEM-R-012 | `memory/failure_card.py` | 406–419 | Low | `file_signature` key invisible after deserialization |
