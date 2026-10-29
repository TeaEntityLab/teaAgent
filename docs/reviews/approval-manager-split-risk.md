# Approval Manager Split Risk Review

**Date:** 2026-10-27  
**Scope:** `teaagent/approval/manager.py` (1,473 lines), proposed split into nine modules, facade kept at `teaagent.approval.manager`.  
**Plan:** `docs/plans/approval-manager-split-plan-2026-10-27.md`  
**Review criteria:** `docs/retrospective/review-system.md` §4.2 (High-Risk Change Criteria). Path is high-risk per `scripts/high_risk_paths.yaml`.  
**Status:** Analysis complete. No code moved. **Human Review gate: PENDING.**

## Goal

Reduce the size of the approval policy core so that it is under the 800-line god-module rule, without changing approval behavior or breaking any import path. Remove the `teaagent/approval/manager.py` exemption in `scripts/check_god_modules.py` once the split is complete.

## Stakeholders

- Operators relying on deny presets, JIT approvals, path containment, and audit records.
- CLI, TUI, runner, subagent, and `policy.py` callers (26 production files in `teaagent/`, 38 in `tests/` and `scripts/`).
- Integrators that import `teaagent.approval_manager` through the legacy alias.
- The owner, who decides the open questions in the plan (section 8).

## Assets at Risk

- Allow and deny decisions made by `ApprovalManager.assert_allowed`.
- Approval token exactness: once grants bound to a payload digest.
- Fail-closed workspace, tenant, and symlink containment.
- Skill directory protection (DSK-P0-002).
- Multi-signature quorum verification (SSH signatures, `allow_dev_signatures` gate).
- Audit and logger output (`teaagent.approval_manager` logger name and `extra` keys).
- Import identity across `teaagent.approval.manager`, `teaagent.policy`, `teaagent.approval_manager`, and `teaagent.approval`.

## Threat Model

A module move can:

- Make two import paths resolve to different class objects, so `isinstance` and enum comparisons fail silently.
- Break monkeypatch targets, so tests pass while patched behavior is no longer exercised.
- Create circular imports between `policy.py`, `approval/__init__.py`, and the new modules.
- Change behavior while "moving" code, through an edited line that is easy to miss in a large diff.
- Drop a re-export, so a caller fails at import time, or worse, falls back to a different implementation.

The split does not add new capabilities, but a mistake in the containment or grant-order code would open a bypass that the current tests may not catch.

## Assumption Audit

- A1: "Pure move" means no behavior change. **Partly unverified.** Current tests do not pin the deny-precedence order (finding F1), so a move that reorders the decision chain would not necessarily fail a test.
- A2: The facade keeps every import working. **Mostly verified.** Identity is covered by `tests/approval/test_migration_compatibility.py`, but there is no test that compares the full `__all__` surface before and after a move. Plan Step 0 adds one.
- A3: The 800-line rule is the right size target. **Accepted.** It is the repo rule, and each proposed module is well under it.
- A4: The god-module exemption comment ("migration completed") is accurate. **Refuted.** The file is 1,473 lines, and no ADR backs the exemption. `review-system.md` §4 says exemptions require an ADR or documented rationale.
- A5: Multi-sig in `policy.py` is a live path. **Refuted.** `ApprovalPolicy._check_multi_sig_quorum` and related helpers (policy.py:218-458) have no production caller. The live path is `MultiSigQuorumManager` in `manager.py`. A split of `manager.py` alone leaves a second implementation in place.

## Evidence Check

- Line map and cluster analysis from a full read of `teaagent/approval/manager.py`.
- Fan-in: `grep -rn "approval.manager\|from teaagent.approval import\|approval_manager\|teaagent.approval_manager" teaagent tests scripts --include=*.py` gives 152 matching lines in 64 files.
- Hard external dependencies on the module path: `teaagent/_compat_modules.py:13` (alias), `scripts/validate_runner_invariants.py:33` (approval authority import name), the logger name at `manager.py:32` used by `caplog` tests, and `policy.py` re-exporting `_normalize_shell_arg` and `_verify_ssh_signature`.
- Probe (scratch script outside the repo, run with the project venv, `.venv/bin/python`): with a deny preset for `workspace_write_file` (`path_globs=['*']`):
  - deny only: blocked (`POLICY_DENIED`).
  - deny plus `approve_session(tool)` on `ApprovalManager`: **allowed**.
  - deny plus `approve_once(call_id, payload)` on `ApprovalManager`: **allowed**.
  - `ApprovalPolicy.assert_allowed(jit_state=<session approval>)`: **allowed**.
- No test in `tests/test_deny_preset_runtime_enforcement.py` pins the precedence between deny and session or once grants.
- Probe was not run as a test, and the runner-level reachability of the bypass is not yet verified end to end.

## Authority / Tool Boundary

The work is a plan and a risk report. It changes `docs/` only. It does not edit any `.py` file, does not change `scripts/check_god_modules.py`, does not access credentials, networks, production services, or persisted run data. The probes used a temporary store directory and ran with the project venv. Nothing was written into the repository tree outside `docs/`.

## Failure Modes

| Failure mode | Control |
| --- | --- |
| Canonical and legacy imports yield different objects | Step 0 facade-identity test covers every moved name. |
| Behavior changes during a move | Step 0 AST move-equivalence check: zero non-import differences per move commit. |
| Circular import between submodules and `policy.py` | Submodules must not import `manager.py`; `tests/test_circular_imports.py` runs at every step. |
| Logger name changes, so operator tooling and `caplog` assertions break | Submodules use `logging.getLogger('teaagent.approval_manager')`; caplog tests run at Steps 1 and 6. |
| Mixin conversion changes method resolution | Methods keep names and `self` semantics; tests that call `_assert_paths_in_workspace` through an instance run at Step 8. |
| A patched method is no longer on the object under test | Monkeypatch test at `tests/test_approval_manager_multisig_fallback.py` pins `_multisig_manager._collect_peer_signatures`. |
| A deny bypass is carried through the refactor unchanged and reads as "fixed" | Step 0 strict xfail records the current bypass; it must stay xfail until Q1 is decided. |
| A test is edited to pass after a move | Plan acceptance criterion 6: test edits in a move commit are a failure. |
| Exemption removed before the split is complete | Step 10 is last, and it requires `check_god_modules.py` to pass without the entry. |

## Worst-case Scenario

A move commit changes the order of checks in `ApprovalManager.assert_allowed`, or drops a containment branch, and the listed tests still pass because none of them pins that ordering or branch. The result is a silent allow decision on a destructive tool, in a release that has already been reviewed as a pure refactor.

## Safe Dry-run Plan

1. Step 0 lands first with no code movement: facade-identity test, public-surface snapshot, AST move-equivalence script, and the strict xfail for deny precedence.
2. Each subsequent step is one commit. Before merging, run the step's listed tests, `scripts/validate_runner_invariants.py`, `scripts/check_high_risk_paths.py`, and the AST check.
3. Reviewer runs the AST check independently on each move commit, not only the author.

## Rollback Plan

- Each step is one commit. `git revert <sha>` restores the previous layout. No data, schema, or run-store migration is involved.
- The facade keeps every name, so reverting a step does not require caller changes.
- Reverting a step that a later step depends on requires reverting the dependent steps first. The import-order test catches a broken dependency.
- If a deny-precedence fix lands during the split, it is a separate commit. Split rollbacks use `git revert` on the move commits only, and must not undo the fix.

## Bounded Execution

- Plan and risk report only, in this change.
- Steps 0-10 of the plan are not started. Each needs its own owner approval.
- No changes to the deny-precedence order, the digest-binding rules, path containment, skill protection, multi-sig, or the logger name, in any move step.
- The `policy.py` duplicate multi-sig code is out of scope (Q3).

## Audit Log Plan

This review, the plan, the probe results recorded above, the commit that adds them, and the action-register row A-P1-6 provide the review trail. Probe scripts are not kept in the repository.

## Findings

| ID | Finding | Severity (proposed) | Evidence | Handling |
| --- | --- | --- | --- | --- |
| F1 | A deny preset is not terminal over a session approval or a once grant, on either `ApprovalManager` or `ApprovalPolicy`. | High (security, pending owner confirmation of reachability) | Probe above; manager.py:974-991 order | Not fixed by the split. Owner decision Q1. Strict xfail at Step 0. |
| F2 | Legacy call-id-only once grants are consumed on the first payload of any content. | Medium | manager.py:109-110, 145-148 | Owner decision Q2. |
| F3 | `_has_symlink_component` returns False on `OSError`, so the symlink check is fail-open on error. | Medium (narrow; containment runs first) | manager.py:1147-1151 | Owner decision Q6. Behavior unchanged by the split. |
| F4 | `_looks_like_path` skips strings containing spaces, so a path-like value with a space under a non-named argument key is not checked. | Low to medium | manager.py:1119-1135, 1174-1201 | Recorded for review. Not changed by this plan. |
| F5 | `_assert_skill_path_not_protected` builds the target without `resolve()`, and `is_protected_skill_path` returns False on `OSError`. | Low to medium | manager.py:1239-1246; policy path in `is_protected_skill_path` (48-75) | Owner decision Q6. |
| F6 | `policy.py` carries a second multi-sig and high-risk implementation with no production caller (about 215 lines). | Medium (maintenance and drift risk) | policy.py:218-458; grep results in plan section 1.6 | Owner decision Q3. |
| F7 | Three classes named `ApprovalRequest` in the approval package and runner types. | Low (confusion, wrong-type risk in imports) | manager.py:223; backend.py:33; runner/_types via core.py | Owner decision Q4. |
| F8 | The god-module exemption says "migration completed"; the file is 1,473 lines and has no ADR. | Process | scripts/check_god_modules.py:27; review-system.md §4 | Plan Step 10 and Q5. |

## Human Review Required

**Yes.** `teaagent/approval/` is a high-risk path. The plan changes the approval-policy decision surface and the import boundary for it. Security Officer sign-off (Size C) or the second-reviewer ceremony (Size B) is needed before any move commit. Review size is to be confirmed by the owner (plan Q8).

## Human Approval Gate

**PENDING.** No approval has been recorded. The owner reviews this report and the plan before any code moves. The owner must also decide Q1 (deny precedence) before Step 0 item 4 can be resolved.

## Acceptance Criteria (for the split, as planned)

1. `teaagent/approval/manager.py` and every new module are under 800 lines.
2. `scripts/check_god_modules.py` passes with the manager exemption removed (Step 10).
3. Facade-identity and public-surface tests pass unchanged after each move.
4. The AST move-equivalence check reports zero non-import differences for each move commit.
5. The listed policy and enforcement tests pass at every step without test edits.
6. `scripts/validate_runner_invariants.py` passes.
7. The deny-precedence xfail is unchanged until Q1 is decided.

## Decision Record

**Claim:** The file can be split into nine modules, behind an unchanged facade, with no import breakage and no behavior change, in ten steps, each reversible by one revert.  
**Evidence:** Line map and cluster analysis; fan-in count; existing identity tests in `tests/approval/test_migration_compatibility.py`; the A-P1-4 migration used the same alias mechanism successfully.  
**Unknowns:** Whether the current tests pin enough of the decision order to catch a reordering error (F1 suggests not for precedence). Whether the deny bypass is reachable in a real run (only the object-level probe was run). Whether downstream integrators inspect `module.__name__` (A-P1-4 review raised the same question).  
**Counterargument:** The file is cohesive enough as a single policy core, and the split adds indirection in a security path. A single larger file is easier to audit end to end. Response: the audit benefit comes from the AST check and per-cluster tests, not from one file, and the size rule is the repository's own standard.  
**Decision (proposed):** Proceed to Step 0 only after owner review. Resolve Q1 before any move that touches `assert_allowed`. Keep every move behavior-neutral.  
**Falsifier / Verification:** Any AST difference in a move commit, any identity failure, any caplog failure, any change in the strict xfail's status without a fix commit, any runner-invariant failure, or any `teaagent/approval/*` file over 800 lines after its step makes the split incomplete or unsafe.
