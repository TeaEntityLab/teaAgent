# policy — Behavior Specification

## Purpose

`policy` defines session-scoped approval behavior for destructive tool calls and provides backward-compatible policy wiring around `ApprovalManager`.

## Key Types

- `ApprovalPolicy` (frozen dataclass): compatibility approval gate surface for runner/tool dispatch.
- `PermissionMode` (re-export from `approval_manager`): `read-only`, `workspace-write`, `prompt`, `allow`, `danger-full-access`.
- `JITApprovalState`, `MultiSigQuorumConfig`, `PeerSignature`: JIT state and quorum-related types.
- `parse_permission_mode(value: str) -> PermissionMode`: strict parser with explicit allowed-value error.

## Behavior Contract

1. `ApprovalPolicy.assert_allowed(...)` is the execution-time gate and delegates to `ApprovalManager.assert_allowed(...)`.
2. External `jit_state` is synchronized into manager state before evaluation and synchronized back afterward.
3. Approval-store operations are guarded by `_flock_store()` for race-safe updates.
4. Deprecated `preapproved_call_ids` remains supported with warning for compatibility.
5. Invalid permission mode text raises `ValueError` with complete allowed-mode list.

## Invariants

- `assert_allowed` returns `None` when allowed or raises when denied; no tri-state behavior.
- Dataclass immutability is preserved; runtime helpers are initialized in `__post_init__` via `object.__setattr__`.
- JIT approval mutations flow through manager-owned state and are mirrored back to caller state.
- Unknown permission-mode strings are never coerced or defaulted silently.
