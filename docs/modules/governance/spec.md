# governance — Behavior Specification

## Purpose

Enforces agent policy gates: plan-before-write enforcement, audit completeness checking, and tool call linting. Governance is the layer between "what the agent wants to do" and "what the policy allows."

## Behavior Contract

### Plan Gate (`plan_gate.py`)
1. **Write tools require a plan** — in `WORKSPACE_WRITE` mode with `require_plan=True`, any call to `workspace_write_file`, `workspace_apply_patch`, or `workspace_edit_at_hash` must have a bound plan in the context (`context['plan_contract']['content_hash']`).
2. **`--skip-plan-check` override** — power users can bypass with explicit acknowledgment.
3. **Mode precedence** — READ_ONLY and DANGER_FULL_ACCESS modes bypass the plan gate entirely.

### Audit Completeness (`audit_completeness.py`)
1. **Required events** — checks that an audit log contains a minimal set of event types (e.g., `run_started`, `run_completed`).
2. **Returns a report** — does not raise; returns a list of missing event types.

### Tool Lint (`tool_lint.py`)
1. **Schema validation** — validates that all registered tools have well-formed JSON Schema `input_schema`.
2. **Annotation consistency** — flags contradictory annotations (e.g., `read_only=True, destructive=True`).
3. **Returns violations** — does not raise; returns list of violations.

### Policy (`policy.py`)
1. **`PermissionMode` enum** — `READ_ONLY`, `WORKSPACE_WRITE`, `PROMPT`, `ALLOW`, `DANGER_FULL_ACCESS`
2. **Permission checks** — used by plan gate, approval manager, and tool registry to gate tool calls.

## Invariants

- `assert_write_allowed` either returns `None` or raises `ToolPermissionError` — never silently allows.
- `WORKSPACE_WRITE` mode always requires plan binding (default, overridable only with `--skip-plan-check`).
- `DANGER_FULL_ACCESS` bypasses all governance checks.
