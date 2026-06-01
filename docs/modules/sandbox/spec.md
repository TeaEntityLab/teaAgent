# sandbox — Behavior Specification

## Purpose

Provides isolated execution environments for agent runs to prevent unintended side effects. Three sandbox strategies: git branch isolation, OS-level process sandboxing, and VFS (virtual filesystem) overlay. Also integrates Docker for skill execution.

## Behavior Contract

### Git Branch Sandbox (`_git_branch.py`)
1. **Branch creation** — creates a new git branch from the current HEAD before the agent writes anything.
2. **Stash** — uncommitted changes are stashed before branch switch.
3. **Conflict detection** — after agent run, merge back detects conflicts and reports them.
4. **Thread-safe** — `_sandbox_lock` prevents concurrent branch operations in the same worktree.

### OS Sandbox (`_os_sandbox.py`)
1. **Process isolation** — agent code runs in a subprocess or container with restricted syscall set.
2. **Filesystem restrictions** — write access limited to specified directories.

### VFS Sandbox (`_vfs_sandbox.py`)
1. **Copy-on-write overlay** — writes are intercepted and stored in a temporary overlay; original files untouched.
2. **Commit or discard** — after agent run, overlay changes can be committed to disk or discarded entirely.

### Parallel Experiment (`_parallel_experiment.py`)
1. **A/B testing** — runs two agent configurations concurrently in separate sandboxes.
2. **Result comparison** — compares outputs to pick the better result.

## State Machine (Git Branch)

```
[INITIAL] clean worktree
  → stash_save(label)
  → git checkout -b {sandbox_branch}

[RUNNING] agent modifies files in sandbox_branch

[DONE]
  → git merge sandbox_branch → main
  ├── success: GitSandboxResult(success=True)
  └── conflict: GitSandboxResult(has_conflicts=True, conflicted_files=[...])

[CLEANUP]
  → git checkout main
  → git stash pop (if stash_id present)
  → git branch -d {sandbox_branch}
```

## Invariants

- `_sandbox_lock` is always acquired before any git branch operation.
- A stash is created before branch switch; restored after.
- Failed sandbox never leaves the worktree on the sandbox branch.

## Relationship to `git_sandbox`

The `git_sandbox` module provides a focused, standalone git sandbox implementation. The sandbox module includes git branch sandboxing as one of its isolation strategies (alongside OS-level and VFS isolation). For git-specific sandboxing workflows, see [`git_sandbox`](../git_sandbox/spec.md).
