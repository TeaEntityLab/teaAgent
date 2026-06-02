# git_sandbox — Public API Reference

## Data Models

### `GitSandboxResult`
| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Operation success flag. |
| `branch_name` | `Optional[str]` | Sandbox branch name involved. |
| `original_branch` | `Optional[str]` | Branch active before sandbox flow. |
| `error` | `Optional[str]` | Error text when failed. |
| `stash_id` | `Optional[str]` | Stash ref saved/restored during flow. |
| `has_conflicts` | `bool` | Merge conflict indicator. |
| `conflicted_files` | `list[str]` | Files in conflict state. |

### `GitBranchSandbox`
| Field | Type | Description |
|---|---|---|
| `root` | `Path` | Workspace git root. |
| `run_id` | `str` | Run identifier for branch lifecycle. |

## Functions

### `stash_save(root: str | Path, label: str) -> Optional[str]`
**Location**: `teaagent/sandbox/_git_branch.py:58`
**Pre-condition**: `root` is a git repository.
**Post-condition**: Stashes dirty state and returns stash ref, or `None` when nothing to stash.

### `stash_pop(root: str | Path, stash_ref: Optional[str] = None) -> bool`
**Location**: `teaagent/sandbox/_git_branch.py:88`
**Pre-condition**: Git repo with matching stash state.
**Post-condition**: Attempts stash apply/pop and returns success boolean.

### `GitBranchSandbox.start(*, auto_stash: bool = False) -> GitSandboxResult`
**Location**: `teaagent/sandbox/_git_branch.py:129`
**Pre-condition**: Sandbox availability checks pass.
**Post-condition**: Creates or enters sandbox branch and returns lifecycle metadata.

### `GitBranchSandbox.rollback() -> GitSandboxResult`
**Location**: `teaagent/sandbox/_git_branch.py:232`
**Pre-condition**: Sandbox instance has start-state to rollback from.
**Post-condition**: Returns to original branch and attempts sandbox cleanup.
