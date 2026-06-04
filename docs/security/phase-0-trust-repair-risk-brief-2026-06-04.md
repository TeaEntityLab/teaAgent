# Phase 0 Trust Repair Risk Brief
# 2026-06-04

## Summary

TeaAgent's security posture is not weak, but it is not yet simple. The strongest
parts are the permission vocabulary, audit logging, plan gates, policy-as-code
tests, and the zero-dependency core. The weakest parts are authority duplication,
bypass semantics, optional-extra dependency surface, and status drift between
ADRs, module docs, and code.

Phase 0 should end only when the trust boundary is easy to explain and hard to
misuse.

## Current Trust Boundary

Confirmed trust primitives:

- Permission modes: `read-only`, `workspace-write`, `prompt`, `allow`,
  `danger-full-access`.
- Approval policy and approval manager enforce destructive tool decisions.
- Audit logs and run evidence provide receipts.
- Policy-as-code can deny actions even when the global permission mode is broad.
- Base package has no mandatory runtime dependencies.

Confirmed trust complications:

- `allow_all_destructive=True` bypasses destructive prompts outside
  `danger-full-access`.
- `DANGER_FULL_ACCESS` remains a legitimate mode and can be misused.
- Two `ApprovalManager` classes exist.
- `policy.py` and `approval_manager.py` remain coupled by a lazy reverse import.
- Memory catalog authority is split between canonical `memory_legacy.py` and a
  near-duplicate `memory/catalog.py`.
- Optional managed runtimes can import a large dependency tree.

## P0 Risk Register Refresh

| ID | Risk | Severity | Current evidence | Required direction |
| --- | --- | --- | --- | --- |
| TR-SEC-01 | Destructive bypass outside explicit full-access mode | Critical | `allow_all_destructive=True` passes in default prompt-mode tests | Gate or remove bypass |
| TR-SEC-02 | `danger-full-access` used on real workspaces | Critical | Docs warn, but automated sandbox-only enforcement is not universal | Require explicit confirmation and isolation checks |
| TR-SEC-03 | Duplicate approval manager names cause wrong patch target | High | `teaagent/approval_manager.py` and `teaagent/runner/_approval_manager.py` both define `ApprovalManager` | Rename helper or consolidate |
| TR-SEC-04 | Policy/approval coupling makes security boundary harder to reason about | High | `policy.py` imports approval manager; approval manager lazy-imports policy helper | Extract shared normalization/helper module |
| TR-SEC-05 | Optional dependency CVEs block or confuse base security scans | High | `google-adk` can pull `fastapi` / `starlette` via dev extras | Separate base audit from optional-extra audit |
| TR-SEC-06 | Memory canonical source is documented but duplicate code remains | Medium | `memory_legacy.py` is exported as canonical; `memory/catalog.py` still exists | Delete, merge, or mark non-runtime |
| TR-SEC-07 | Coverage omit list hides security-relevant code from the gate | Medium | 16 omit patterns in `pyproject.toml` | Add why/return date and smoke tests |
| TR-SEC-08 | Risk severity calibration is inconsistent | Medium | `DANGER_FULL_ACCESS` is High in module docs, Critical in review | Define severity rules |

## Reality Check

The project should resist two tempting stories.

First tempting story:

> "We have 3,377 tests, so the trust boundary is safe."

Counterpoint: some tests preserve existing behavior even when that behavior is a
risk. For example, the prompt-mode destructive bypass test proves current
behavior, not desired safety.

Second tempting story:

> "Optional dependencies do not matter because the core has zero dependencies."

Counterpoint: optional dependencies matter the moment a user enables them. The
right posture is separate audit surfaces, not indifference.

## Phase 0 Exit Conditions

Phase 0 should not be declared complete until:

1. No destructive bypass exists outside explicitly acknowledged full-access mode.
2. There is one canonical approval authority name.
3. The policy/approval circularity has been broken or formally accepted with a
   test that proves import-order stability.
4. Memory catalog canonical source is enforced by code structure, not only docs.
5. Every coverage omit entry has a reason, owner, and expected return path.
6. Base dependency audit and optional-extra dependency audit are both documented.
7. Security risk severity is calibrated by a shared rubric.

## What This Means For Users

TeaAgent can already be useful for daily local agent work when users stay in
supervised modes and value auditability. It should not be marketed as a
production-safe autonomous harness until the bypass and authority duplication
issues are closed.

The honest promise today is:

> TeaAgent is building toward governed autonomy. The governance layer is real,
> but Phase 0 still contains trust-boundary repair work that must outrank new
> ecosystem features.
