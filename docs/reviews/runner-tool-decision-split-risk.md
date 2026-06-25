# Runner Tool-Decision Split Risk Review

**Date:** 2026-06-25  
**Action:** A-P2-6  
**Scope:** Mechanical decomposition of `AgentRunner._execute_tool_decision` in
`teaagent/runner/_core.py` into `_authorize_tool_call`, `_dispatch_tool_call`, and
`_process_tool_result`.

## Goal

Reduce cyclomatic complexity and review surface on the governed tool-execution path
without changing approval authority, audit ordering, or error semantics.

## Assets at Risk

- Tool allow/deny decisions (spine, auto-mode, JIT, plan contract, payload digest).
- Audit event ordering (`tool_call_requested` → `tool_call_started` → completed/failed).
- Checkpoint persistence and context compaction after successful tool calls.
- Long-result truncation and observation append semantics.

## Threat Model

A mechanical split can accidentally reorder authorization vs execution, drop audit
events, mishandle `ToolPermissionError` vs `ToolExecutionError`, or skip checkpoint /
compaction on one branch. Any of those failures could allow an unauthorized tool call
or leave run state inconsistent with the audit trail.

## Boundaries

- No change to approval policy algorithms, tool registry contracts, or event schemas.
- No change to public `AgentRunner.run()` API.
- Split is private-method only; callers continue to invoke `_execute_tool_decision`.

## Failure Modes and Controls

| Failure mode | Control |
| --- | --- |
| Authorization skipped or run after execution | `_execute_tool_decision` calls `_authorize_tool_call` before `_dispatch_tool_call`; dispatch has no policy checks. |
| Audit events reordered or dropped | Each helper owns the same event subset as the pre-split monolith; runner invariants + approval tests exercise the path. |
| `ToolExecutionError` treated as permission denial | Error handling remains in `_dispatch_tool_call`; permission flow remains in `_authorize_tool_call`. |
| Compaction / checkpoint regression | `_process_tool_result` retains post-success checkpoint + compaction logic unchanged. |
| Behavioral drift during refactor | Focused runner invariants, tool-decision validation, and cancel-flow acceptance tests run before merge. |

## Dry Run and Rollback

Dry run: run focused runner tests (`test_runner_invariants.py`,
`test_tool_decision_validation.py`, `test_cancel_flow.py`) before and after the split.
Rollback is file-local: restore the monolithic `_execute_tool_decision` body in
`runner/_core.py`.

## Human Review Gate

Human review required before merge because the change touches the high-risk runner core
(`scripts/high_risk_paths.yaml`).

## Acceptance Criteria

1. `_execute_tool_decision` orchestrates three helpers with no `# noqa: C901`.
2. Authorization, dispatch, and result-processing semantics match the pre-split path.
3. Focused runner and approval-path tests pass.
4. Pre-commit hooks pass, including `check_high_risk_paths.py`.

## Decision

**Go for bounded local execution.** Mechanical extraction only; no policy redesign.
