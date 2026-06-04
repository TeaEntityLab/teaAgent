# Memory Module — Public API

---

## Data Models

### `MemoryEntry` (`memory/catalog.py`)

Frozen dataclass. Canonical definition re-exported by `memory/__init__.py`.

```python
@dataclass(frozen=True)
class MemoryEntry:
    memory_id: str              # UUID hex (32 chars)
    content: str                # Non-empty stripped text
    tags: tuple[str, ...]       # Lowercase, stripped, sorted, deduplicated
    created_at: str             # UTC ISO timestamp
    branch_name: str | None     # Optional git branch isolation scope
    run_id: str | None          # Optional run ID isolation scope
```

Methods:
- `to_dict() -> dict[str, Any]` — serializes to JSON-compatible dict with `tags` as list

---

### `FailureCard` (`memory/failure_card.py`, line 109)

Mutable dataclass (not frozen).

```python
@dataclass
class FailureCard:
    id: str                          # 8-char UUID prefix
    run_id: str
    timestamp: float                 # Unix timestamp of failure
    error_type: str                  # e.g. 'TypeError', 'ImportError'
    file_path: str                   # File where error occurred
    line_number: Optional[int]
    error_message: str
    task_description: str
    context_files: list[str]
    confidence: str                  # 'low' | 'medium' | 'high'
    expires_at: Optional[float]      # Unix timestamp; None = no expiry
    invalidated: bool                # True = permanently inactive
    invalidation_reason: Optional[str]
    warning_behavior: str            # 'info' | 'warning' | 'block'
    reviewer_type: str               # 'auto' | 'human'
    evidence_command: Optional[str]
    evidence_exit_code: Optional[int]
    DEFAULT_TTL_SECONDS: ClassVar[int] = 2592000  # 30 days
```

---

### `PinnedFile` (`memory/pinned_file.py`, line 63)

Mutable dataclass.

```python
@dataclass
class PinnedFile:
    file_path: str       # Relative path from workspace root
    pinned_at: float     # Unix timestamp when pinned
    last_modified: float # Unix timestamp of last known modification
```

---

### `AutoInvalidationRule` (`memory/failure_card.py`, line 29)

```python
@dataclass
class AutoInvalidationRule:
    trigger: str         # 'file_signature_change' | 'test_refactor' | 'dependency_version_change'
    confidence: str      # 'high' | 'medium' | 'low'
    action: str          # 'invalidate' | 'warn' | 'block'
    paths: Optional[list[str]]   # Optional path prefix filters
    enabled: bool
```

---

### `DeltaCard` (context_bus — referenced from memory via RAG archival)

Not a memory module class, but used in `ContextBus.archive_to_rag()`.

---

## Classes

---

### `MemoryCatalog` (`memory/catalog.py`)

**Constructor:**
```python
MemoryCatalog(root: str | Path = '.', *, readonly: bool = False)
```
- Pre: `root` must be a valid directory path (created if writable).
- Post: `self.path = <root>/.teaagent/memory.jsonl`; directory created if `not readonly`.

---

#### `add(content, *, tags=(), branch_name=None, run_id=None) -> MemoryEntry`

- **Pre:** `readonly=False`; `content.strip()` must be non-empty.
- **Post:** Entry appended to `memory.jsonl`; returned `MemoryEntry` has normalized tags.
- **Raises:** `RuntimeError` if readonly; `ValueError('memory content cannot be empty')` if blank.

---

#### `add_quarantined(content, *, tags=(), provenance, branch_name=None, run_id=None) -> MemoryEntry`

- **Pre:** `readonly=False`; `content.strip()` non-empty; `provenance` is a dict.
- **Post:** Entry appended to `memory-quarantine.jsonl` with `quarantine=True` and `provenance` keys.
- **Raises:** `RuntimeError` if readonly; `ValueError` if blank content.

---

#### `list(*, limit=20) -> list[MemoryEntry]`

- **Post:** Returns up to `limit` most-recent entries (reversed insertion order). Returns `[]` if file absent.

---

#### `search(query, *, limit=10) -> list[MemoryEntry]`

- **Pre:** `query` is any string.
- **Post:** Returns entries where ALL query tokens appear in `content.lower()` or any `tag`. Ranked by relevance score descending then `created_at` descending. Returns `[]` for empty query.

**Relevance scoring (`memory/catalog.py`):**
- +3 per token found in content
- +2 per token found in any tag
- +4 if `'auto-curated'` is in tags
- +2 if `'run-summary'` is in tags

---

#### `show(memory_id) -> MemoryEntry`

- **Raises:** `FileNotFoundError` if `memory_id` not found.

---

#### `delete_by_branch(branch_name) -> int`

- **Pre:** `readonly=False`.
- **Post:** Atomically rewrites `memory.jsonl` excluding entries where `branch_name` matches; returns count deleted.
- **Raises:** `RuntimeError` if readonly.

---

#### `delete_by_run_id(run_id) -> int`

Same contract as `delete_by_branch` but filters on `run_id`.

---

#### `quarantine_by_branch(branch_name, reason) -> int`

- **Pre:** `readonly=False`.
- **Post:** Removes matched entries from `memory.jsonl` (atomic rewrite), appends each to `memory-quarantine.jsonl` with provenance dict containing `reason`, `original_branch`, `quarantined_at`. Returns count quarantined.

---

### `FailureCard` — Factory and Query Methods

#### `FailureCard.create(run_id, error_type, file_path, error_message, task_description, context_files, line_number=None, *, confidence='low', ttl_seconds=DEFAULT_TTL_SECONDS, ...) -> FailureCard`

- **Post:** Returns new card with `id = str(uuid4())[:8]`; `timestamp = datetime.now().timestamp()`; `expires_at = now + ttl_seconds` (or `None` if `ttl_seconds <= 0`); `confidence` clamped to valid set.

---

#### `FailureCard.is_active(*, now=None) -> bool`

- **Post:** `False` if `invalidated=True` OR if `expires_at` is set and `(now or time.time()) >= expires_at`. `True` otherwise.

---

#### `FailureCard.effective_behavior() -> str`

Returns: `'ignore'` (inactive), `'block'` (human-reviewed, high confidence, block behavior), otherwise `warning_behavior` value.

---

### `FailureCardStorage` (`memory/failure_card.py`, line 230)

**Constructor:**
```python
FailureCardStorage(root: Path)
```
Creates `<root>/.teaagent/memory/failures.json` storage directory.

---

#### `append(card) -> None`

Reads full list, appends, writes full list.

---

#### `list_all() -> list[FailureCard]`

Returns all cards regardless of active status.

---

#### `list_active() -> list[FailureCard]`

Filters `list_all()` by `card.is_active()`.

---

#### `invalidate(card_id, *, reason) -> bool`

Sets `invalidated=True` and `invalidation_reason` in storage. Returns `True` if found and updated.

---

#### `prune_expired() -> int`

Removes all inactive cards from storage; returns count removed.

---

#### `clear_all() -> None`

Truncates `failures.json` to an empty list.

---

#### `clear_by_id(card_id) -> bool`

Removes exactly one card by ID. Returns `True` if found.

---

#### `find_matching(file_paths, task_description, error_type=None, limit=3) -> list[FailureCard]`

- **Post:** Returns up to `limit` active cards scored by: +10 for matching file path, +5 for matching error type, +N for keyword overlap in task descriptions. Sorted by score descending then timestamp descending.

---

#### `apply_auto_invalidation(config=None) -> dict[str, int]`

- **Post:** Applies `AutoInvalidationRule`s. Returns dict mapping trigger name to count of invalidated/warned cards. Reads workspace `.teaagent/config.json` if `config` is `None`.

---

#### `get_by_id(card_id) -> Optional[FailureCard]`

Returns the card if found, `None` otherwise.

---

### `PinnedFileStorage` (`memory/pinned_file.py`, line 113)

**Constructor:**
```python
PinnedFileStorage(root: Path)
```

---

#### `add(file_path) -> bool`

- **Pre:** `file_path` must exist at `root / file_path`; must not match secret filename patterns.
- **Post:** Adds new `PinnedFile` entry if not already pinned. Returns `True` on success, `False` if already pinned, missing, or secret.

---

#### `remove(file_path) -> bool`

Returns `True` if the file was pinned and is now removed, `False` if not found.

---

#### `list_all() -> list[PinnedFile]`

Returns all pinned files.

---

#### `clear_all() -> None`

Removes all pinned file entries.

---

#### `update_last_modified(file_path) -> bool`

Updates `last_modified` timestamp to `datetime.now().timestamp()`. Returns `True` if found.

---

#### `is_pinned(file_path) -> bool`

Returns `True` if the given path is in the pinned list.

---

### `FileWatcher` (`memory/file_watcher.py`, line 149)

**Constructor:**
```python
FileWatcher(root: Path, callback: Callable[[str, str], None], debounce_ms: int = 500)
```
- **Raises:** `ImportError` if `watchdog` is not installed.

---

#### `start() -> None`

Starts background Observer thread watching `root` recursively. No-op if already running.

---

#### `stop() -> None`

Stops Observer thread with 5-second join timeout.

---

#### `update_watched_files(file_paths: Set[str]) -> None`

Replaces the set of watched absolute paths. Thread-safe.

---

#### `is_running() -> bool`

Thread-safe check of running state.

---

### `TeamMemory` (`memory/team_memory.py`, line 12)

**Constructor:**
```python
TeamMemory(root: str | Path = '.')
```

---

#### `add(entry) -> str`

Appends `- <ISO timestamp> — <entry>\n` to `team-memory.md`. Returns the written line (without trailing newline).

---

#### `list() -> list[str]`

Returns all non-empty lines from `team-memory.md`. Returns `[]` if file absent.

---

#### `inject_prompt(limit_tokens=2048) -> str`

Returns a prompt-ready string with most recent entries first, capped at ~`limit_tokens * 4` characters.

---

## Helper Functions

### `normalize_tags(tags) -> tuple[str, ...]`

Lowercases, strips, deduplicates, and sorts tags.

### `memory_matches(entry, query) -> bool`

All query tokens (split on whitespace) must appear in `entry.content.lower()` or any tag.

### `memory_relevance_score(entry, tokens) -> int`

Returns integer score; higher = more relevant.

### `memory_entry_from_payload(payload) -> MemoryEntry | None`

Validates and reconstructs `MemoryEntry` from a dict. Returns `None` on any validation failure.

### `memory_entries_to_prompt(entries) -> list[dict[str, Any]]`

Converts a list of entries to a list of serialized dicts.
