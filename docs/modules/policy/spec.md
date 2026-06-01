# policy — Behavior Specification

## Purpose

Approval policy definitions for tool execution. Defines the `ApprovalPolicy` interface and `PermissionMode` enum used across the governance and approval_manager modules.

## Key Types

- `PermissionMode` — Enum with values read-only, workspace-write, prompt, allow, danger-full-access
- `ApprovalPolicy` — Callable interface for tool approval decisions
