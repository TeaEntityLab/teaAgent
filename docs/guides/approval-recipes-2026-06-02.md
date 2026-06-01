# Approval Recipes
# 2026-06-02

Examples for safe approval behavior.

## Approve one docs file

Good approval:

```text
tool: edit_file
path: docs/daily-driver-current-status.md
scope: exact file
```

Why: the path matches the task and has narrow scope.

## Approve a docs directory

Good only when the task names the directory:

```text
tool: edit_file
path: docs/plans/ticket-plans/**
scope: directory recursive
```

Why: many ticket files may be created or updated.

## Reject missing path

Reject:

```text
tool: edit_file
path: <missing>
```

Reason: write authority without path scope is not meaningful approval.

## Reject parent traversal

Reject:

```text
path: ../outside-project/file.md
```

Reason: path intent escapes the workspace.

## Reject confusing suffix match

If you approve `src/foo.py`, it should not approve:

```text
src/foo.py.bak
```

Exact file approval should remain exact.

## Approval review questions

Ask:

1. Is this the tool I expected?
2. Is this the exact file or directory I expected?
3. Is the action reversible?
4. Does the run id match the task I am reviewing?
5. Would I approve this if it ran outside the TUI?
