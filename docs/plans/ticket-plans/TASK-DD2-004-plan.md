# TASK-DD2-004: Harden Path-Scoped Approvals

**Priority:** P0
**Status:** Active
**Primary files:** `teaagent/cli/_handlers/agent_helpers.py`, `teaagent/tui/__init__.py`, `teaagent/ergonomics/_approval_grants.py`

## Problem

Path-scoped approvals are central to daily trust, but path extraction and matching can
be ambiguous. A missing path, broad glob, absolute path, parent traversal, or unsupported
tool input shape can accidentally widen authority.

## Scope

- Normalize approved paths relative to workspace root.
- Define exact-file vs directory-recursive approval.
- Reject or explicitly prompt when no safe path can be extracted.
- Support known path argument names consistently.
- Add tests for absolute paths, `..`, symlinks, and broad glob behavior where relevant.

## Acceptance criteria

- Approving `src/foo.py` does not approve `src/foo.py.bak`.
- Directory approval is represented as directory scope only after explicit user choice.
- Unknown or missing path arguments do not silently become global grants.
- CLI and TUI approval wording describe the same authority.

## Verification

```bash
python3 -m pytest tests/test_smart_hitl.py
python3 -m pytest tests/acceptance/test_approval_root_cli_flow.py
```

## Risks

- Over-tight matching can break legitimate workflows.
- Over-broad matching can violate the approval model.
- Human-readable approval text can drift from matcher behavior.
