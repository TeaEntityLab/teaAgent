# subagents — Public API Reference

## Data Models

### `SubagentDef` (`_types.py:11`)
```python
@dataclass(frozen=True)
class SubagentDef:
    name: str
    description: str = ''
    system_prompt: str = ''
    model: Optional[str] = None
    permission_mode: Optional[PermissionMode] = None
    max_iterations: int = 5
    max_tool_calls: int = 8
    tool_whitelist: Optional[frozenset[str]] = None
    disallowed_tools: Optional[frozenset[str]] = None
    max_depth: int = 1
    isolation: str = 'shared'
    background: bool = False
    effort: Optional[str] = None
```
Immutable definition loaded from `.teaagent/subagents/`. `tool_whitelist` restricts which parent tools are inherited. `max_depth` controls how many delegation levels deep this agent can be started.

---

### `SubagentLineage` (`_types.py:28`)
```python
@dataclass(frozen=True)
class SubagentLineage:
    parent_run_id: str
    def_name: str
    depth: int
    isolation: str = 'shared'
    batch_index: Optional[int] = None
    worktree_path: Optional[str] = None
    container_path: Optional[str] = None

    def to_dict(self) -> dict[str, str | int]: ...
```
Tracks the parent→child relationship. `container_path` is a legacy field name for `directory-snapshot` (kept for backward compatibility).

---

### `SubagentSession` (`_types.py:58`)
```python
@dataclass(frozen=True)
class SubagentSession:
    session_id: str
    def_name: str
    parent_run_id: str
    status: str
    started_at: str               # ISO-8601
    depth: int = 0
    batch_index: Optional[int] = None
    isolation: str = 'shared'
    worktree_path: Optional[str] = None
    container_path: Optional[str] = None
    completed_at: Optional[str] = None
    iterations: int = 0
    tool_calls: int = 0
    cost_cents: float = 0.0
    final_answer: str = ''
    review: Optional[dict[str, Any]] = None

    @property
    def lineage(self) -> SubagentLineage: ...
```

---

### `IsolationContext` (`_isolation.py:24`)
```python
@dataclass(frozen=True)
class IsolationContext:
    parent_root: Path
    child_root: Path
    isolation: str
    worktree_path: Optional[Path] = None
    container_path: Optional[Path] = None
    container_id: Optional[str] = None
    cpu_quota: Optional[float] = None
    memory_limit: Optional[str] = None

    def cleanup(self) -> None: ...
```
`cleanup()` removes worktrees, snapshot directories, or Docker containers depending on `isolation`. Always safe to call multiple times (uses `check=False`/`ignore_errors=True`).

---

### `SubagentApprovalRequest` (`_approval_queue.py:49`)
```python
@dataclass
class SubagentApprovalRequest:
    request_id: str
    subagent_id: str
    parent_run_id: str
    subagent_name: str
    tool_name: str
    tool_arguments: dict[str, Any]
    permission_mode: str
    isolation: str
    batch_index: Optional[int] = None
    worktree_path: Optional[str] = None
    created_at: str = ...           # ISO-8601 UTC
    status: ApprovalRequestStatus = PENDING
    approved_at: Optional[str] = None
    denied_at: Optional[str] = None
    denial_reason: Optional[str] = None
    timeout_seconds: int = 180

    def to_dict(self) -> dict[str, Any]: ...
```

---

### `ApprovalRequestStatus` (`_approval_queue.py:38`)
```python
class ApprovalRequestStatus(Enum):
    PENDING   = 'pending'
    APPROVED  = 'approved'
    DENIED    = 'denied'
    TIMEOUT   = 'timeout'
    CANCELLED = 'cancelled'
```

---

## Functions

### `load_subagent_defs(root: Path) -> dict[str, SubagentDef]`
**File**: `_loader.py:16`

**Pre-conditions**: `root` is a `Path`. `.teaagent/subagents/` need not exist.

**Post-conditions**: Returns `{}` if the directory is absent. Otherwise, returns a dict keyed by `SubagentDef.name` for each parseable file with a valid `name` field. Files with unsupported suffixes or missing/empty `name` are silently skipped.

**Supported formats**: `.yaml`, `.yml` (PyYAML or fallback parser), `.json`, `.md` (YAML frontmatter + body as `system_prompt`).

---

### `normalize_subagent_isolation(value: Any) -> str | None`
**File**: `_isolation.py:77`

Normalizes isolation mode string. Returns `DEFAULT_SUBAGENT_ISOLATION` for `None`/empty. Returns `None` for unrecognized values. Maps deprecated alias `'container'` → `'directory-snapshot'` silently.

---

### `prepare_subagent_isolation(parent_root, *, isolation, session_key, cpu_quota, memory_limit) -> tuple[IsolationContext | None, str]`
**File**: `_isolation.py:112`

**Pre-conditions**: `isolation` is one of `SUPPORTED_SUBAGENT_ISOLATIONS`. `session_key` must be unique for the current parent run.

**Post-conditions**:
- Returns `(IsolationContext, '')` on success.
- Returns `(None, error_message)` on failure.
- Deprecated aliases emit a `DeprecationWarning` before normalizing.
- Worktree isolation requires `.git` to exist in `parent_root`.
- Docker isolation requires `docker --version` to succeed.

**Exceptions**: OSError from snapshot copy is caught and returned as `(None, message)`.

---

### `new_isolation_session_key(*, parent_run_id: str, def_name: str) -> str`
**File**: `_isolation.py:280`

Produces a filesystem-safe, collision-resistant key: `{safe_parent[:12]}-{safe_def_name}-{uuid4().hex[:8]}`.

---

## Classes

### `SubagentManager`
**File**: `_manager.py:48`

#### `__init__(*, root, parent_config, parent_adapter)`
Loads subagent defs from disk. Does not register tools.

#### `bind_registry(registry: Any) -> None`
Called by `register_subagent_tools` to store the parent `ToolRegistry` reference.

#### `list_defs() -> list[SubagentDef]`
Returns all loaded defs sorted by name.

#### `get_def(name: str) -> Optional[SubagentDef]`
Case-insensitive, dash/underscore-normalized lookup.

#### `run_subagent(*, task, parent_run_id, depth, def_name=None, max_iterations=None, max_tool_calls=None, batch_index=None, isolation='shared', skill_path=None, skill_risk_level=None) -> dict[str, Any]`

**Pre-conditions**:
- `task` is a non-empty string.
- `depth` is the parent's current depth; the child will run at `depth + 1`.
- `isolation` is one of the supported isolation modes.

**Post-conditions**:
- Returns a result dict with `status` key.
- On success: `{'run_id', 'status', 'iterations', 'tool_calls', 'cost_cents', 'final_answer', 'lineage', ['review'], 'message'}`.
- On error: `{'run_id': '', 'status': 'error', 'iterations': 0, 'tool_calls': 0, 'final_answer': '', 'message': '<reason>', ['lineage']}`.
- IsolationContext is always cleaned up via `finally`.
- Session is stored in `self._sessions[run_id]` on success.

**Exceptions**: Exceptions from `run_chat_agent` propagate after cleanup.

---

### `CentralizedApprovalQueue`
**File**: `_approval_queue.py:122`

#### `__init__(parent_run_id: str, *, workspace_root: Optional[Path] = None)`
Creates in-memory queue. If `workspace_root` is given, creates/loads `ApprovalQueueStore` and calls `reload_from_store()`.

#### `submit_request_sync(...) -> bool`
Blocking sync method. Submits request, writes to disk, polls with 0.25s sleep until approved/denied/timeout. Returns `True` if approved, `False` otherwise.

#### `submit_request(...) -> bool` (async)
Async version. Uses `asyncio.Future` and `asyncio.wait_for(future, timeout=180)`.

#### `approve_request_sync(request_id, approved_by='human') -> bool`
Marks PENDING→APPROVED, sets threading.Event, persists to disk. Returns `False` if request not found or not PENDING.

#### `deny_request_sync(request_id, reason='Denied by human') -> bool`
Same as approve, but PENDING→DENIED.

#### `approve_all_pending_sync(approved_by='human') -> int`
Convenience: approves all PENDING requests. Returns count.

#### `deny_all_pending_sync(reason, denied_by) -> int`
Convenience: denies all PENDING requests. Returns count.

#### `get_pending_requests() -> list[SubagentApprovalRequest]`
Thread-safe snapshot of all PENDING requests.

#### `get_request(request_id) -> Optional[SubagentApprovalRequest]`
Thread-safe lookup by ID.

#### `reload_from_store() -> None`
Merges disk state into memory. Resolves waiting futures/events for requests that have changed status externally.

#### `cleanup() -> None` (async)
Removes terminal (non-PENDING) requests without associated futures.

---

### `ApprovalQueueStore`
**File**: `_approval_queue_store.py:40`

#### `__init__(workspace_root: Path, hmac_secret: Optional[str] = None)`
Queue files stored at `workspace_root/.teaagent/approval_queues/<parent_run_id>.json`.

#### `save(parent_run_id, requests, batches) -> None`
Atomic write via temp-file + `os.replace`. Optionally signs payload with HMAC-SHA256.

#### `load(parent_run_id) -> QueueDiskSnapshot`
Reads and verifies queue file. Returns empty snapshot on missing file or HMAC failure.

#### `update_request_status(parent_run_id, request_id, status, *, reason=None, approved_by='human') -> bool`
Cross-process approve/deny. Acquires exclusive lock, reads, modifies, writes atomically. Returns `False` if request not found or not PENDING.

#### `prune_stale(*, max_age_seconds, now=None) -> ApprovalQueuePruneReport`
Removes queue files older than `max_age_seconds` with no pending requests.

---

## Module-level helpers (`_approval_queue.py`)

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_approval_queue` | `(parent_run_id, *, workspace_root) -> CentralizedApprovalQueue` | Get-or-create from global registry |
| `try_get_approval_queue` | `(parent_run_id, *, workspace_root) -> Optional[...]` | Get only if exists (no side-effects) |
| `snapshot_pending_subagent_requests` | `(parent_run_id=None, *, workspace_root) -> list[dict]` | Serialized pending requests for UI |
| `approve_request_cross_process` | `(workspace_root, parent_run_id, request_id, *, approved_by) -> bool` | Disk-level approve for out-of-process callers |
| `deny_request_cross_process` | `(workspace_root, parent_run_id, request_id, *, reason) -> bool` | Disk-level deny |
| `make_centralized_subagent_approval_handler` | `(*, parent_run_id, subagent_id, ...) -> ApprovalHandler` | Factory for subagent-scoped sync handler |
| `should_use_centralized_approval` | `(*, parent_run_id, batch_index, parallel_mode) -> bool` | Decision predicate |
| `cleanup_queue` | `(parent_run_id, *, workspace_root) -> None` (async) | Remove queue from global registry + cleanup |

---

## Tool Registration (`register_subagent_tools`)

Registered tools (with their schemas):

| Tool name | Input required | Description |
|-----------|----------------|-------------|
| `subagent` | `task` (str) | Generic single-subagent delegation |
| `subagent_<name>` | `task` (str) | Named def-specific delegation |
| `subagent_batch` | `tasks` (list) | Parallel batch; each item has `task`, optional `def_name`, `max_iterations`, `max_tool_calls`, `isolation` |
| `team` | `task`, `team_name` | Multi-specialist team run |

All subagent tools share optional inputs: `max_iterations`, `max_tool_calls`, `isolation`.
