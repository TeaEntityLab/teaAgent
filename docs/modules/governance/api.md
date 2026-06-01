# governance — Public API Reference

## `PermissionMode` (Enum)
**Location**: `policy.py`

```python
class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'

| Mode | Allows writes? | Plan required? | Approval prompts? |
|------|---------------|---------------|------------------|
| `READ_ONLY` | No | N/A | No |
| `WORKSPACE_WRITE` | Yes | Yes (default) | Yes |
| `PROMPT` | Yes | Optional | Yes |
| `ALLOW` | Yes | Optional | No |
| `DANGER_FULL_ACCESS` | Yes | No | No |

---

## `assert_write_allowed`
**Location**: `governance/plan_gate.py:36`

```python
def assert_write_allowed(
    *,
    tool_name: str,
    permission_mode: PermissionMode,
    context: dict[str, Any],
    require_plan: bool,
    skip_plan_check: bool = False,
) -> None
```

**Pre-conditions**:
- `tool_name` is a known write tool or arbitrary string (non-write tools always pass).
- `context` is the current agent context dict.

**Post-conditions**:
- Returns `None` if write is allowed.
- Raises `ToolPermissionError` with an actionable message if blocked.

**Gate logic**:
```
if tool_name not in WRITE_TOOLS: return (pass)
if permission_mode not in _PLAN_MODES: return (pass — READ_ONLY blocks at higher level)
if skip_plan_check: return (explicit override)
if WORKSPACE_WRITE and not require_plan: raise (strict default)
if require_plan and not _has_plan_contract(context): raise
```

**Constants**:
```python
WRITE_TOOLS = frozenset({
    'workspace_write_file',
    'workspace_apply_patch',
    'workspace_edit_at_hash',
})
```

---

## `check_audit_completeness`
**Location**: `governance/audit_completeness.py`

```python
def check_audit_completeness(events: list[AuditEvent]) -> list[str]
```
Returns list of missing required event type names. Empty list = complete.

**Required event types**: `run_started`, `run_completed` (or `run_failed`).

---

## `lint_tool_registry`
**Location**: `governance/tool_lint.py`

```python
def lint_tool_registry(registry: ToolRegistry) -> list[str]
```
Returns list of violation strings. Empty list = no violations.

**Checks performed**:
- `input_schema` is a valid JSON Schema `object` type
- No contradictory annotations (`read_only=True, destructive=True`)
- Tool names match `[a-z][a-z0-9_]*` pattern

---

## Data Model: Plan Contract

```python
# Stored in agent context under context['plan_contract']
{
    "content_hash": "sha256hex",   # SHA-256 of plan content
    "path": "/path/to/plan.md",    # optional
    "created_at": "ISO 8601",      # optional
}
```
