# Approval Scope Contract
# 2026-06-02

## Contract

An approval grants authority to one understandable tool action and scope.

## Rules

- Approval prompts show run id, tool name, operation, and path/resource scope.
- Empty path scope is rejected for write/destructive tools unless explicitly escalated.
- File approval does not imply sibling or suffix files.
- Directory approval is recursive only when the user selected directory scope.
- Paths are normalized relative to workspace root before matching.

## Acceptance

- Exact-file approval matches only that file.
- Directory approval is represented distinctly from file approval.
- Unknown path shapes prompt for explicit confirmation or reject.
- CLI and TUI approval text match matcher behavior.

## User risk

Approval is the moment the user grants power. Ambiguity here undermines the whole
governance model.
