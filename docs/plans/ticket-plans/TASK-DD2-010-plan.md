# TASK-DD2-010: Enforce Pinned-File Workspace Containment

**Priority:** P0
**Status:** Newly discovered
**Primary files:** `teaagent/memory/pinned_file.py`, `tests/test_memory_pinned.py`

## Problem

Pinned-file storage accepts a path string, joins it to the workspace root, and checks
existence. It does not clearly reject absolute paths, parent traversal, or symlink
escape before storing live-context files.

## Scope

- Require workspace-relative input.
- Resolve candidate paths and verify containment under the workspace root.
- Reject absolute paths, `..`, and symlink escape.
- Keep secret-name heuristics as defense in depth, not the primary boundary.

## Acceptance criteria

- Absolute paths outside the workspace are rejected.
- `../outside` is rejected.
- Symlink escape is rejected.
- Allowed relative files still work.
- Stored pinned paths are normalized workspace-relative paths.

## Verification

```bash
python3 -m pytest tests/test_memory_pinned.py
```

## Risks

- Some users may have relied on absolute pinning.
- If absolute pinning is desired, it needs explicit opt-in and warning UX.
