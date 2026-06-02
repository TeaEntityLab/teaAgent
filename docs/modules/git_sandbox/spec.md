# git_sandbox — Behavior Specification

## Purpose

The git sandbox isolates agent work from the user's active branch when enabled.

## Responsibilities

- Record original branch.
- Create or identify sandbox branch.
- Preserve dirty worktree state safely.
- Support merge, discard, or keep outcomes.
- Record sandbox metadata in run evidence.

## Contracts

- The sandbox object that starts a run must preserve lifecycle state through resolution.
- Branch names and run ids must be traceable.
- Auto-stash state must be restored only through explicit resolution.
- Help text must match default behavior.

## Open risks

- Pending run id and final run id can split lifecycle state.
- Recreated sandbox objects can lose original branch.
- Users can be confused about whether sandbox is opt-in or default.

## Relationship to `sandbox`

The `sandbox` module provides git branch sandboxing alongside OS and VFS isolation strategies. This module (`git_sandbox`) provides a focused git-only sandbox implementation. For the broader sandbox framework, see [`sandbox`](../sandbox/spec.md).
