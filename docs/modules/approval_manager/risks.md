# approval_manager — Risk Vectors & Known Issues

### APR-R-001: `once`-scoped grants consumed before tool executes
**File**: `ergonomics/_approval_state.py`, `approval_manager.py`
**Risk**: `once` grants are removed from the store when `is_allowed()` returns `True`. If the tool then fails (exception, hook error), the grant is already consumed. The user must re-approve for any retry.
**Failure mode**: Unexpected re-prompt on retry of a legitimately approved operation.
**Upstream:** [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (SEC-01 audit integrity; approval state durability)

### APR-R-002: `deny` decisions not persisted
**File**: `approval_manager.py`
**Risk**: JIT denials (user says "no" at the TTY prompt) are in-memory only via `JITApprovalState`. On process restart or agent resume, the denial is gone and the agent will re-prompt.
**Failure mode**: Previously denied tools get re-prompted after restart.
**Upstream:** [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (access control durability; SEC-06 related)

### APR-R-003: `DANGER_FULL_ACCESS` bypasses all approval
**Severity**: Critical (per [severity-calibration-rubric.md](../../security/severity-calibration-rubric.md))
**File**: `approval_manager.py:32-36` (PermissionMode enum)
**Risk**: `DANGER_FULL_ACCESS` skips every check. A user enabling it for convenience may forget it's active.
**Failure mode**: Unintended destructive writes with no approval gate.

> **See also:** [governance/risks.md](../governance/risks.md) — DANGER_FULL_ACCESS bypasses plan gate

### APR-R-004: Multi-sig quorum uses in-memory peer registry
**File**: `approval_manager.py:73-80` (`MultiSigQuorumConfig`)
**Risk**: Peer agent IDs and public keys are configured at startup. If a peer is decommissioned without updating the config, the quorum can never be satisfied (requires N of M peers, all M slots must be valid).
**Failure mode**: All high-risk operations permanently blocked.

### APR-R-005: File lock on `approvals.json` not held during TTY prompt
**File**: `ergonomics/approval_store.py`
**Risk**: Between reading the store and writing back a decision, the file lock is released. Concurrent processes may make conflicting approval decisions for the same grant.
**Failure mode**: Race condition allows a single grant to be consumed by two different runs.

### APR-R-006: Approval UI shows diff in terminal — may expose secrets
**File**: `approval_ui.py`
**Risk**: When prompting for write approval, the UI shows file content diff. If the diff contains secrets (env vars, API keys), they are printed to the terminal.
**Mitigation**: Redaction before display is not implemented; rely on the user not having secrets in workspace files.

### APR-R-007: TTL-expired grants silently removed on next access
**File**: `ergonomics/_approval_state.py`
**Risk**: Expired grants are cleaned up lazily on next `is_allowed()` check. No notification is given that a grant expired.
**Failure mode**: User expects a previously granted persistent approval to still be active; it silently expired.

## Known TODO / Limitations
- `approval_doctor_command` — diagnostic command for approval state; not wired to automated CI.
- `approval_explain_command` — explains why a tool was denied; relies on `DenialReasonCode` being populated (not always done).
