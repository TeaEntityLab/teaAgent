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

Closed or regression-guarded complications in the current branch:

- `allow_all_destructive=True` no longer bypasses destructive prompts in
  `prompt` mode, even with `full_access_acknowledged=True`.
- Runner-local approval helper naming is no longer a duplicate
  `ApprovalManager`; it is `RunnerApprovalCoordinator`.
- The policy/approval import-order risk is guarded by import smoke tests.
- `memory_legacy.py` is a compatibility re-export of the canonical
  `teaagent.memory.catalog` implementation.

Remaining trust complications:

- `DANGER_FULL_ACCESS` remains a legitimate mode and can be misused.
- Optional managed runtimes can import a large dependency tree; they are now
  separated from the base PR audit gate but still require release review.
- Auto mode still swaps the runner approval policy to a broad policy during
  execution, so policy restoration and audit clarity remain worth reviewing.

## P0 Risk Register Refresh

| ID | Risk | Severity | Current evidence | Required direction |
| --- | --- | --- | --- | --- |
| TR-SEC-01 | Destructive bypass outside explicit full-access mode | Critical | Fixed in current branch; prompt-mode bypass tests now fail closed | Keep regression guard and require explicit full-access mode for bypass callers |
| TR-SEC-02 | `danger-full-access` used on real workspaces | Critical | Docs warn, but automated sandbox-only enforcement is not universal | Require explicit confirmation and isolation checks |
| TR-SEC-03 | Duplicate approval manager names cause wrong patch target | High | Fixed in current branch; runner helper is `RunnerApprovalCoordinator` | Keep canonical-name regression guard |
| TR-SEC-04 | Policy/approval coupling makes security boundary harder to reason about | High | Import-order tests pass; no reverse import observed in current path | Keep boundary tests and avoid shared helpers inside either side |
| TR-SEC-05 | Optional dependency CVEs block or confuse base security scans | High | Policy and workflow now separate base, dev/lockfile, and optional-extra audit lanes | Keep optional-extra findings visible without polluting base PR gate |
| TR-SEC-06 | Memory canonical source is documented but duplicate code remains | Medium | Fixed in current branch; `memory_legacy.py` re-exports `memory.catalog` | Keep canonical import-path regression guard |
| TR-SEC-07 | Coverage omit list hides security-relevant code from the gate | Medium | Ledger now lists 16 omit patterns with owner, reason, return milestone, and smoke-test candidate | Keep validator in CI and add more direct smoke tests |
| TR-SEC-08 | Risk severity calibration is inconsistent | Medium | Shared severity rubric exists in `docs/security/severity-calibration-rubric.md` | Keep module docs and risk rows aligned to the rubric |

## Reality Check

The project should resist two tempting stories.

First tempting story:

> "We have 3,377 tests, so the trust boundary is safe."

Counterpoint: some tests preserve existing behavior even when that behavior is a
risk. The prompt-mode destructive bypass tests were rewritten in the current
branch so they now prove desired safety: prompt mode fails closed even if
`allow_all_destructive=True` and `full_access_acknowledged=True`.

Second tempting story:

> "Optional dependencies do not matter because the core has zero dependencies."

Counterpoint: optional dependencies matter the moment a user enables them. The
right posture is separate audit surfaces, not indifference.

## Phase 0 Exit Conditions

Phase 0 should not be declared complete until:

1. No destructive bypass exists outside explicit full-access mode.
2. There is one canonical approval authority name.
3. The policy/approval circularity has been broken or formally accepted with a
   test that proves import-order stability.
4. Memory catalog canonical source is enforced by code structure, not only docs.
5. Every coverage omit entry has a reason, owner, and expected return path.
6. Base dependency audit and optional-extra dependency audit are both documented.
7. Security risk severity is calibrated by a shared rubric.

Current branch status: items 1-7 are implemented, documented, or
regression-guarded. Remaining Phase 0 safety work should focus on broad-mode
entry ceremony, auto-mode policy restoration evidence, and converting
coverage-omit smoke candidates into direct tests.

## What This Means For Users

TeaAgent can already be useful for daily local agent work when users stay in
supervised modes and value auditability. It should not be marketed as a
production-safe autonomous harness until broad-mode ceremony, auto-mode policy
restoration evidence, and remaining coverage-omit smoke tests are closed.

The honest promise today is:

> TeaAgent is building toward governed autonomy. The governance layer is real,
> but Phase 0 still contains trust-boundary repair work that must outrank new
> ecosystem features.
