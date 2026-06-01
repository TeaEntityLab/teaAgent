# errors — Behavior Specification

## Purpose

Centralized error definitions for the TeaAgent harness. Defines error categories, exception hierarchy, and error classification for audit logging.

## Error Categories

The `ErrorCategory` enum classifies errors into model_logic, permission, system, and transient categories.

## Exception Hierarchy

- `AgentHarnessError` — base class for all harness errors
- `ToolPermissionError` — tool call denied by policy/plan gate
- Other specific error types
