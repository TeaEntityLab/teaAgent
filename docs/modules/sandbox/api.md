# sandbox — Public API Reference

## `GitSandboxResult` (frozen dataclass)
**Location**: `sandbox/_git_branch.py:16`

```python
@dataclass(frozen=True)
class GitSandboxResult:
    success: bool
    branch_name: Optional[str] = None
    original_branch: Optional[str] = None
    error: Optional[str] = None
    stash_id: Optional[str] = None
    has_conflicts: bool = False
    conflicted_files: list[str] = field(default_factory=list)
```

---

## Free Functions (`sandbox/_git_branch.py`)

### `is_git_repository(root: str | Path) -> bool`
Returns `True` if `root` is inside a git repository.

### `is_worktree_clean(root: str | Path) -> bool`
Returns `True` if there are no uncommitted changes.

### `stash_save(root: str | Path, label: str) -> Optional[str]`
- Stashes current changes including untracked files.
- Returns stash reflog selector (e.g., `'stash@{0}'`) or `None` if nothing to stash.
- **Pre**: Must be inside a git repository.

### `create_sandbox_branch(root: str | Path, prefix: str = 'teaagent-sandbox') -> GitSandboxResult`
- Acquires `_sandbox_lock`.
- Stashes changes, creates a new branch from HEAD.
- Returns `GitSandboxResult(success=True, branch_name=..., original_branch=..., stash_id=...)`.
- On failure: returns `GitSandboxResult(success=False, error=...)`.

### `merge_sandbox_branch(root: str | Path, branch_name: str, *, stash_id: Optional[str] = None) -> GitSandboxResult`
- Checks out original branch, merges `branch_name`.
- On conflict: returns `GitSandboxResult(has_conflicts=True, conflicted_files=[...])`.
- If `stash_id` provided and merge succeeds: pops the stash.

### `cleanup_sandbox_branch(root: str | Path, branch_name: str) -> None`
Deletes the sandbox branch (force if needed).

---

## `DockerSandbox`
**Location**: `docker_sandbox.py`

```python
class DockerSandbox:
    def __init__(
        self,
        image: str = 'python:3.12-slim',
        *,
        memory_mb: Optional[float] = None,
        timeout_seconds: int = 30,
        network: str = 'none',
    ) -> None: ...

    def run(
        self,
        code: str,
        payload: dict[str, Any],
        *,
        entrypoint: str = 'run',
    ) -> Any
    # Executes code in Docker container, returns JSON-decoded output.
    # Raises DockerSandboxError on failure/timeout.
```

---

## Data Flow

```
create_sandbox_branch(root)
  → GitSandboxResult { branch_name, original_branch, stash_id }

[agent writes to sandbox branch]

merge_sandbox_branch(root, branch_name, stash_id=stash_id)
  → GitSandboxResult { success, has_conflicts, conflicted_files }

cleanup_sandbox_branch(root, branch_name)
```
