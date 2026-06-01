# sandbox — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/sandbox/__init__.py` | Package init, re-exports |
| `teaagent/sandbox/_git_branch.py` | Git branch isolation: `GitSandboxResult`, `is_git_repository`, `stash_save`, `create_sandbox_branch`, `merge_sandbox_branch` |
| `teaagent/sandbox/_os_sandbox.py` | OS-level sandbox using seccomp/landlock |
| `teaagent/sandbox/_parallel_experiment.py` | A/B parallel experiment framework |
| `teaagent/sandbox/_vfs_sandbox.py` | VFS copy-on-write overlay |
| `teaagent/git_sandbox.py` | Legacy git sandbox adapter (wraps `sandbox/_git_branch.py`) |
| `teaagent/docker_sandbox.py` | `DockerSandbox` — runs skill code in Docker containers |

## Key Exports (`_git_branch.py`)

- `GitSandboxResult` — frozen dataclass: `success`, `branch_name`, `original_branch`, `error`, `stash_id`, `has_conflicts`, `conflicted_files`
- `is_git_repository(root) -> bool`
- `is_worktree_clean(root) -> bool`
- `stash_save(root, label) -> Optional[str]` — returns stash ref like `stash@{0}`
- `create_sandbox_branch(root, prefix?) -> GitSandboxResult`
- `merge_sandbox_branch(root, branch_name, *, stash_id?) -> GitSandboxResult`
- `cleanup_sandbox_branch(root, branch_name) -> None`

## Dependencies

```
sandbox/_git_branch.py
  └── stdlib: subprocess, threading, json, pathlib

sandbox/_os_sandbox.py
  └── (platform-specific: seccomp, landlock)

docker_sandbox.py
  └── teaagent.skill_router (SandboxType)
```

## Entry Points

1. `runner/_core.py` — optionally wraps run in `create_sandbox_branch` when `--sandbox=git` flag used
2. `skill_executor.py` — uses `DockerSandbox` for Docker-isolated skill execution
3. `cli/_handlers/_sandbox.py` — `sandbox_*` CLI commands

## Call Graph

```
runner._core (with git sandbox)
  create_sandbox_branch(root)
  [agent runs, writes to sandbox branch]
  merge_sandbox_branch(root, branch_name)
    └── subprocess: git merge
  cleanup_sandbox_branch(root, branch_name)

skill_executor
  DockerSandbox.run(code, payload)
    └── subprocess: docker run
```
