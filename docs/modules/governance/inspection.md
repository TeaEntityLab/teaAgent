# governance — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/governance/__init__.py` | Package init |
| `teaagent/governance/plan_gate.py` | `assert_write_allowed` — plan binding enforcement |
| `teaagent/governance/audit_completeness.py` | `check_audit_completeness` — required event type checks |
| `teaagent/governance/tool_lint.py` | `lint_tool_registry` — schema and annotation linting |
| `teaagent/policy.py` | `PermissionMode` enum, policy data classes |
| `teaagent/plan_mode.py` | Plan mode helpers |
| `teaagent/plan.py` | Plan data structures and storage |

## Key Exports

### `governance/plan_gate.py`
- `WRITE_TOOLS: frozenset[str]` — tools gated by plan check
- `assert_write_allowed(*, tool_name, permission_mode, context, require_plan, skip_plan_check=False) -> None`

### `policy.py`
- `PermissionMode(Enum)` — `READ_ONLY`, `WORKSPACE_WRITE`, `PROMPT`, `ALLOW`, `DANGER_FULL_ACCESS`

### `governance/audit_completeness.py`
- `check_audit_completeness(events: list[AuditEvent]) -> list[str]` — returns missing event types

### `governance/tool_lint.py`
- `lint_tool_registry(registry: ToolRegistry) -> list[str]` — returns violation strings

## Dependencies

```
governance/plan_gate.py
  ├── teaagent.errors.ToolPermissionError
  └── teaagent.policy.PermissionMode

policy.py
  └── stdlib: enum
```

## Entry Points

1. `runner/_core.py` — calls `assert_write_allowed` before dispatching write tools
2. `cli/_handlers/_agent.py` — reads `PermissionMode` from CLI `--permission-mode` flag
3. `cli/_handlers/_audit.py` — calls `check_audit_completeness` for audit health check
4. `runner/_plan_validator.py` — calls `lint_tool_registry` during preflight

## Call Graph

```
runner._core._dispatch_tool_call(tool_name, arguments)
  └── assert_write_allowed(
        tool_name=tool_name,
        permission_mode=self.permission_mode,
        context=self.context,
        require_plan=self.require_plan,
      )
      ├── returns None → proceed
      └── raises ToolPermissionError → tool call aborted
```
