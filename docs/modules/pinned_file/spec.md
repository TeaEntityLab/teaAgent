# pinned_file — Behavior Specification

## Purpose

Pinned files let users keep important workspace files in live context.

## Responsibilities

- Store workspace-relative pinned paths.
- Reject secrets and unsafe paths.
- Watch pinned files when supported.
- Provide bounded context content.

## Contracts

- Pinned paths are workspace-relative.
- Absolute paths outside the workspace are rejected.
- Parent traversal is rejected.
- Symlink escape is rejected.
- Secret-name checks are defense in depth, not the only guard.

## Open risks

- Joining `root / file_path` is not enough to prove containment.
- Users may expect absolute paths to work.
- Symlink escape needs explicit testing.
