# A-P1-4 Approval Module Migration Risk Review

**Date:** 2026-06-21  
**Action:** A-P1-4  
**Scope:** Move approval module ownership into teaagent/approval/ while preserving
the four legacy import paths through _compat_modules.py.

## Goal

Make teaagent.approval the physical and logical home of approval manager, backend,
selector, and UI implementations without changing approval behavior.

## Stakeholders

- CLI, TUI, runner, and subagent callers.
- Integrators that still import the root-level compatibility paths.
- Operators relying on JIT, multi-signature, containment, and audit behavior.

## Assets at Risk

- Approval allow and deny decisions.
- PermissionMode and approval class identity across import paths.
- JIT, multi-signature, path-containment, and tenant checks.
- Import stability for existing integrations.

## Threat Model

A module move can introduce circular imports, duplicate class definitions, break
monkeypatch targets, or make old and new import paths resolve to different objects.
Any of those failures could make approval enforcement unavailable or inconsistent.

## Assumption Audit

- This action is an ownership and import migration, not a policy redesign.
- Legacy import paths remain supported through the existing alias loader.
- The legacy approval-manager logger name remains stable for operator tooling.
- Historical documents may retain old paths as historical evidence; current guidance
  must use the canonical package.

## Evidence Check

- The four root modules contain the implementations.
- Their teaagent/approval/ counterparts currently re-export root symbols.
- tests/approval/test_migration_compatibility.py already checks symbol identity.
- _compat_modules.py provides an established physical-file-free alias mechanism.

## Authority / Tool Boundary

The migration changes repository source, tests, and current documentation only. It
does not access credentials, networks, production services, or persisted run data.

## Failure Modes

| Failure mode | Control |
| --- | --- |
| Canonical and legacy imports yield different objects | Identity tests cover all exported symbols. |
| Canonical package import loops | Circular-import and import-order tests run before completion. |
| Security behavior changes during the move | Implementations are moved mechanically; focused approval tests compare behavior. |
| Legacy patch or import paths disappear | _compat_modules.py aliases all four legacy paths. |
| Root implementation files recur | Static migration test requires the four files to remain absent. |

## Worst-case Scenario

Approval enforcement fails to load or a caller evaluates a different enum or class,
causing an incorrect allow or denial decision.

## Safe Dry-run Plan

Add failing tests for canonical ownership, legacy aliases, and root-file absence before
moving any implementation. Run the focused migration suite after each move.

## Rollback Plan

The migration is local and file-based. Restore the four root implementations, restore
the subpackage re-export modules, and remove the four alias entries. No persistent data
or schema rollback is required.

## Bounded Execution

- Move only approval_manager.py, approval_backend.py, approval_selectors.py, and
  approval_ui.py.
- Update direct production imports, invariant tooling, and current documentation.
- Do not change approval algorithms, defaults, schemas, or external APIs.

## Audit Log Plan

This review, the state ledger, migration tests, focused test output, pre-commit output,
and the retrospective register provide the review trail.

## Human Review Required

Yes. The migration changes the import boundary for security-sensitive approval code.

## Human Approval Gate

The owner authorized bounded local execution on 2026-06-21. Human review remains
required before merge.

## Acceptance Criteria

1. The four canonical modules physically own their implementations.
2. The four root implementation files no longer exist.
3. Legacy imports resolve through _compat_modules.py to the canonical modules.
4. Legacy and canonical imports expose identical class and enum objects.
5. Production imports and runner invariants name the canonical package.
6. Focused tests, static checks, documentation checks, and pre-commit hooks pass.

## Decision Record

**Claim:** Physical ownership can move without a breaking API change.  
**Evidence:** The existing meta-path alias loader already supports deprecated modules,
and compatibility tests assert object identity.  
**Unknowns:** Third-party code may inspect module.__name__ rather than imported
symbols.  
**Counterargument:** Keeping root shim files would preserve module metadata more
literally.  
**Decision:** Use alias-only compatibility because the action explicitly requires no
root approval modules and the repository already uses this mechanism.  
**Falsifier / Verification:** Any import-order failure, identity mismatch, approval test
failure, or missing legacy import makes the migration incomplete.

## State Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Canonical ownership tests | verified | Canonical classes report teaagent.approval module ownership. |
| Legacy alias and identity tests | verified | All four legacy modules resolve to the canonical module objects. |
| Root implementation files removed | verified | Static test confirms all four root files are absent. |
| Production imports and invariants canonicalized | verified | AST guard and runner-invariant script pass. |
| Focused approval behavior | verified | 570 approval, policy, permission, tenant, and security tests completed with exit 0; 3 skipped. |
| Remaining alphabetical tail | verified | A fresh process completed 1,704 `tests/test_[s-z]*.py` tests; 7 skipped. |
| Static, documentation, and hook checks | verified | Ruff, mypy, runner invariants, root count, docs consistency, OKF checks, and all pre-commit hooks pass. |
| Full-suite single-process run | environment-limited | Reached 80% with only 7 identified environment failures, then exited 133 during a test that passes in isolation. Five failures require loopback `socket.bind`; two preflight/plan assertions expect a ready host but this sandbox blocks `.git` writes, DNS, and local binds. |

The full-suite process result is not evidence of an approval regression: all seven
failures reproduce in `tests/test_real_usage_agents.py` and are caused by the managed
sandbox, while `tests/test_skill_write_quarantine.py` passes 35/35 in isolation at the
exit-133 boundary. The focused migration and security suites remain the acceptance
gate for this action.

## Go / No-go Decision

**Go for human review.** The migration acceptance gate is green. The managed-sandbox
limits on the single-process full suite remain disclosed above and do not affect the
focused approval, policy, permission, tenant, or security evidence.
