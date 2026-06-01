# subagents — Risk Vectors, Failure Modes, Edge Cases, Known Issues

## Risk Vectors

### RSK-01: Path traversal in isolation session keys
**File**: `_isolation.py:281-292`

`new_isolation_session_key` strips non-alphanumeric/dash/underscore characters from both `def_name` and `parent_run_id` before assembling the filesystem path. However, callers that pass an untrusted `def_name` from external config could still produce long keys (max 8+12+name length). The `safe_def_name` has no length cap — an extremely long def name could produce an excessively long path.

**Mitigation**: Characters restricted; but no length limit on `def_name` segment.

### RSK-02: `directory-snapshot` workspace copy does not exclude `.env` / secrets
**File**: `_isolation.py:93-109`

`_copy_workspace_snapshot` only skips `.teaagent/` and gitignored files. If `.env` or credential files are not gitignored, they are copied verbatim into the snapshot directory, potentially exposing secrets to subagents with different permission modes.

### RSK-03: `docker` isolation uses `ro` mount — subagent cannot write
**File**: `_isolation.py:229-232`

The Docker volume is mounted read-only (`-v .../temp_dir:/workspace:ro`). A subagent with write tools will fail silently or with opaque errors because it cannot modify `/workspace`. Additionally, the Docker image is always `python:3.11-slim` and not configurable.

### RSK-04: Sync approval polling re-reads disk every 0.25s
**File**: `_approval_queue.py:317-338`

`submit_request_sync` loops with `event.wait(0.25)` and calls `reload_from_store()` on each iteration. Under high load with many parallel subagents, this creates O(n_subagents × 4) disk reads per second. The `.json.lock` file uses `fcntl` (Unix only; graceful fall-through on Windows), so on Windows there is no locking — concurrent writes can corrupt queue files.

### RSK-05: HMAC secret in env var — cleartext
**File**: `_approval_queue_store.py:278-284`

`TEAAGENT_APPROVAL_HMAC_KEY` is read from the environment. Any process with access to the environment can read it. The HMAC only prevents accidental tampering, not a determined attacker with env read access.

### RSK-06: `asyncio._lock` nested inside `threading._sync_lock` — deadlock risk
**File**: `_approval_queue.py:437-443`, `_approval_queue.py:471-488`

`approve_request` acquires `async with self._lock` then `with self._sync_lock` inside. `reload_from_store` holds `self._sync_lock` and calls `self._resolve_future_threadsafe` which uses `call_soon_threadsafe`. If the event loop is blocked by `_lock`, the threadsafe callback cannot execute — this can deadlock under certain coroutine scheduling.

### RSK-07: `_build_registry_for` accesses private attribute `_parent_registry._tools`
**File**: `_manager.py:322`

`source_names = sorted(self._parent_registry._tools.keys())` relies on the private `_tools` attribute of `ToolRegistry`. If `ToolRegistry` is replaced or its internals change, this will break silently or raise `AttributeError`.

### RSK-08: `TeamOrchestrator.run_team` is sequential, not truly concurrent
**File**: `_team_orchestrator.py:196-208`

Despite the name "orchestrator", `run_team` iterates specialists in a `for` loop — there is no thread pool. `subagent_batch` does use `ThreadPoolExecutor`, but `run_team` does not. A slow specialist blocks all subsequent specialists.

### RSK-09: `new_isolation_session_key` — `parent_run_id` truncated to 12 chars
**File**: `_isolation.py:290`

Only 12 characters of `parent_run_id` are used in the session key, reducing uniqueness when many runs share a long common prefix. Collision probability is low but non-zero for high-frequency batch runs.

### RSK-10: `capture_subagent_review` depends on `git add -N` — fails on non-git workspaces
**File**: `_review.py:57`

If the child workspace is not a git repo (e.g., `directory-snapshot` isolation), `_is_git_worktree` returns `False` and the function returns `None` — no review artifact is created. The parent only sees `review=None` in the session record, with no explanation.

### RSK-11: `apply_patch` (review) path escape check
**File**: `_review.py:164-172`

`patch_path.relative_to(workspace)` raises `ValueError` if the path escapes the workspace. This is handled correctly and returns `{'ok': False, 'status': 'invalid_review'}`. However, the patch file contents are passed directly to `git apply` — a malicious patch could overwrite files outside the git index (e.g., via `git apply --3way` writing to tracked paths).

### RSK-12: `_load_simple_yaml` is a partial parser — can silently misparse valid YAML
**File**: `_loader.py:111-171`, `_team_orchestrator.py:39-102`

The fallback `_load_simple_yaml` only handles top-level scalar keys, block scalars (`|`), and list values. Complex YAML (anchors, multi-line strings without `|`, nested mappings) will be silently dropped or misread. This can cause a subagent def to load with missing fields without warning.

---

## Failure Modes

| Scenario | Outcome | Location |
|----------|---------|----------|
| Git not installed, `isolation=worktree` | `prepare_subagent_isolation` returns `None`, `run_subagent` returns error dict | `_isolation.py:148-169` |
| Docker not installed, `isolation=docker` | Same; error dict returned | `_isolation.py:204-211` |
| `git worktree add` fails (e.g., dirty index) | Error dict; ISO context is None | `_isolation.py:159-169` |
| `_copy_workspace_snapshot` OSError | Snapshot dir cleaned up, error dict returned | `_isolation.py:188-191` |
| Child `run_chat_agent` raises | Exception propagates through `finally`; `iso_ctx.cleanup()` is called; session NOT stored | `_manager.py:256-311` |
| Approval request times out (180s) | Returns `False` to the subagent's destructive tool; tool is blocked | `_approval_queue.py:339-347` |
| HMAC mismatch on disk queue load | Empty snapshot returned; pending requests not visible until re-submitted | `_approval_queue_store.py:134-141` |
| `yaml` not installed | Falls back to `_load_simple_yaml`; complex defs may be silently malformed | `_loader.py:87-91` |
| `def_name` not found in `_defs` | `run_subagent` returns `_error(f'unknown subagent: {def_name}')` | `_manager.py:93-105` |
| `max_depth` reached | `run_subagent` returns `_error(f'max_depth ... reached')` | `_manager.py:107-116` |

---

## Edge Cases

- **`isolation='auto'` without `skill_path`**: Returns error immediately (`_manager.py:143-152`).
- **`subagent_batch` with empty tasks list**: Returns `{'status': 'error', ...}` (`_tools.py:251-256`).
- **`def_name` with spaces or mixed case**: `_normalize_name` converts `_` to `-`, strips and lowercases; the matching is case-insensitive (`_manager.py:342-343`).
- **`approved_by` field not stored in `SubagentApprovalRequest`**: The `approve_request_sync` method writes `approved_by` to `_sync_results` but not to the request object itself. The disk record gets `approved_by` only via `update_request_status` (`_approval_queue_store.py:190`).
- **`cleanup()` called on already-removed worktree**: `git worktree remove --force` uses `check=False` so it silently succeeds (`_isolation.py:39-45`).
- **Empty `subagent_reviews` directory**: `list_subagent_reviews` returns `[]` without error (`_review.py:93-95`).
- **`_safe_segment` for review ID capped at 80 chars**: review metadata filenames are thus bounded (`_review.py:228-230`).
