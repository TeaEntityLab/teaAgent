# governance — Risk Vectors & Known Issues

## GOV-R-001: DANGER_FULL_ACCESS bypasses all checks
**File**: `governance/plan_gate.py:19-25`
**Risk**: `DANGER_FULL_ACCESS` permission mode skips the plan gate entirely. An agent in this mode can write anything without a plan.
**Failure mode**: Accidental destructive writes.
**Mitigation**: Never use DANGER_FULL_ACCESS for automated runs; require explicit human confirmation.

> **See also:** [approval_manager/risks.md](../approval_manager/risks.md) — DANGER_FULL_ACCESS bypasses all approval

## GOV-R-002: `--skip-plan-check` leaves no audit trail
**File**: `governance/plan_gate.py:52-55`
**Risk**: When `skip_plan_check=True`, the plan gate silently returns without recording that the check was skipped.
**Failure mode**: Post-hoc audit cannot tell whether a write was plan-bound or bypassed.
**Fix**: Record a `plan_gate_bypassed` audit event.

## GOV-R-003: `_has_plan_contract` accepts any non-empty string as hash
**File**: `governance/plan_gate.py:28-33`
**Risk**: `content_hash` is validated only as a non-empty string. A forged or placeholder hash (e.g., `"placeholder"`) passes the check.
**Failure mode**: Plan gate satisfied with an invalid plan reference.

## GOV-R-004: `check_audit_completeness` not wired to agent loop
**File**: `governance/audit_completeness.py`
**Risk**: The function exists but is not called by the runner automatically. It must be invoked explicitly (e.g., from a post-run hook or CLI).
**Failure mode**: Incomplete audit runs go undetected.

## R5: `lint_tool_registry` called only during preflight
**File**: `runner/_plan_validator.py`
**Risk**: Tool schema violations detected at preflight time. Dynamically registered tools (e.g., MCP tools loaded mid-run) are not re-linted.
**Failure mode**: Invalid MCP tool schemas cause runtime errors rather than preflight failures.

## R6: PermissionMode is stringly typed in some paths
**File**: `cli` handlers
**Risk**: Some CLI handlers may compare permission mode as string rather than enum member, causing mode mismatches if the string representation changes.
