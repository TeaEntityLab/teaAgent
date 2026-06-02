# sandbox — Risk Vectors & Known Issues

## SAN-R-001: Git sandbox not available in detached HEAD
**File**: `sandbox/_git_branch.py:28-40`
**Risk**: `is_git_repository` returns True in detached HEAD state, but `git checkout -b` will fail if HEAD is not on a branch.
**Failure mode**: `create_sandbox_branch` fails, agent run aborted unexpectedly.

## SAN-R-002: Stash pop may fail after merge conflicts
**File**: `sandbox/_git_branch.py`
**Risk**: If the merge produces conflicts and the user manually resolves them, the original stash may not pop cleanly (merge commit on top vs. stash content).
**Failure mode**: `git stash pop` fails, original work lost until manual recovery.

## SAN-R-003: `_sandbox_lock` is module-level
**File**: `sandbox/_git_branch.py:12`
**Risk**: The lock protects a single process. If multiple `teaagent` processes share the same worktree, there is no inter-process locking.
**Failure mode**: Concurrent git operations corrupt the worktree.

## SAN-R-004: Docker sandbox timeout not configurable
**File**: `docker_sandbox.py`
**Risk**: Docker container run has a default timeout; very long skills may be killed mid-execution.

## SAN-R-005: VFS sandbox overlay not persistent
**File**: `sandbox/_vfs_sandbox.py`
**Risk**: VFS overlay is in-memory. On crash, uncommitted overlay changes are lost with no way to recover.
**Failure mode**: Data loss in long agent runs using VFS sandbox.

## SAN-R-006: Parallel experiment resource contention
**File**: `sandbox/_parallel_experiment.py`
**Risk**: Two concurrent agent runs share the same CPU/memory. If the host is resource-constrained, one or both runs may be OOM-killed or produce degraded results.

## Known Limitations
- OS sandbox (`_os_sandbox.py`) is Linux-only (seccomp/landlock); silently disabled on macOS.
- Docker sandbox requires Docker daemon running and accessible; no graceful fallback.
