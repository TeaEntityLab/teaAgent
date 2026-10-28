# Risk Report — PR 108: approval hardening (fail closed, archive dead multi-sig, rename, ADR 0044)

> **Claim class:** Risk note for one branch. Not current truth.
> **Last reviewed:** 2026-10-28

**Date:** 2026-10-28
**Scope:** G-P1-11, A-P1-7, A-P1-8, A-P1-9 (`docs/retrospective/06-action-register.md`)
**Source decisions:** the owner's answers to open questions Q3-Q6 of `docs/plans/approval-manager-split-plan-2026-10-27.md` and the findings in `docs/reviews/approval-manager-split-risk.md`. Both files live on the `claude/approval-split-plan` branch (not on `origin/main`); this report cites them by path only.
**High-risk paths touched:** `teaagent/approval/manager.py` and `teaagent/policy.py` (per `scripts/high_risk_paths.yaml`).
**Human review gate:** OPEN. No approval is recorded in this report.

## What changes

This branch lands four commits, each with one action ID:

1. **Path checks fail closed on OSError (G-P1-11, Q6, findings F3 and F5).** `_has_symlink_component` and `is_protected_skill_path` returned "allow" when the filesystem raised `OSError`. They now treat the path as a symlink-component or protected skill path, so the call is denied. A `ValueError` from `relative_to` (path outside the workspace) still returns False. Tests: `tests/test_approval_fail_closed_oserror.py` (first line `# test-type: adversarial`); each test failed before the change.
2. **Archive the unused duplicate multi-sig and high-risk path in `policy.py` (A-P1-7, Q3).** `ApprovalPolicy` carried `_is_high_risk_operation`, `_check_command_args`, `_check_multi_sig_quorum`, `_generate_approval_hash`, `_collect_peer_signatures`, `_run_async_signature_collection` and the `_signature_executor` they used. Before removal, each name was grepped across `teaagent/` and `scripts/` (no production caller; see the commit message). The code is archived under `docs/archive/code/` as `.py.txt` with an origin header. The live multi-sig path is `MultiSigQuorumManager` in `teaagent/approval/manager.py`. `compute_scoped_payload_digest` and the `ApprovalPolicy` public surface are unchanged.
3. **Rename the P2P `ApprovalRequest` to `PeerApprovalRequest` (A-P1-8, Q4).** `ApprovalRequest` remains as a deprecated alias that resolves to the same class. This removes one of three classes with the same name (plan section 1.5). The alias is a public-name change for importers of `teaagent.approval.manager.ApprovalRequest`; the alias keeps them working.
4. **ADR for the approval package layout (A-P1-9, Q5).** `docs/adr/` gets a Proposed ADR for the target modules, the facade rule, underscore-private module names (Q7 default), the invariants, and removal of the `teaagent/approval/manager.py` god-module exemption. No code moves in this branch.

Not changed on this branch: the deny-precedence order in `ApprovalManager.assert_allowed` (finding F1, owner decision Q1 still open; another branch changes it), once-grant digest rules (F2, Q2), the `teaagent.approval_manager` logger name, the `PermissionMode` values, the runner call sites, and the god-module exemption itself (Step 10 of the plan, after the split lands).

## Risk assessment

- **Blast radius.**
  - (1) Calls whose path checks raise OSError are denied where they were allowed. This is narrow: `Path.is_symlink()` already ignores ENOENT, ENOTDIR, EBADF and ELOOP, so only real I/O errors (for example EACCES on a parent directory) reach the new branch. The skill check now also blocks an unresolvable path under `.claude/skills`-style directories even when the candidate prefix would have been allowed.
  - (2) Only `ApprovalPolicy` methods with no production caller are removed. Callers of `ApprovalPolicy.assert_allowed` and `compute_scoped_payload_digest` see no change.
  - (3) Rename only; old name resolves to the same class object.
  - (4) Documentation only.
- **Failure modes.**
  - (1) The denial for an OSError reuses `SYMLINK_BLOCKED` with the existing "contains a symlink component" wording, which is misleading for an I/O error. A follow-up should give this case its own message or reason code. Not changed here to keep the reason-code surface unchanged.
  - (2) If a dormant caller existed outside the grep scope (for example a plugin importing `ApprovalPolicy._check_multi_sig_quorum`), it would fail with AttributeError. The grep covered `teaagent/`, `scripts/` and `tests/`. Archived code can be restored from `docs/archive/code/`.
  - (3) A third-party importer that inspects `ApprovalRequest.__name__` would see `PeerApprovalRequest`. Recorded as the open question in the split risk review (A-P1-4 raised the same question).
  - (4) None at runtime.
- **Thin harness.** No new framework, dependency, event type or runner path. `teaagent/approval/manager.py` stays above the 800-line rule and keeps its exemption; the ADR records the plan to remove it.

## Dry run and rollback

- **Dry run.** Each commit is run through the relevant tests, `pytest -k "approval or policy or permission or skill or symlink"`, ruff, mypy, the repo's governance scripts, and the full suite at the end. Results are recorded in each commit's `Tested:` trailer.
- **Rollback.** Each commit reverts independently with `git revert`. Reverting the rename restores the old P2P class name. Reverting the archive commit restores the policy methods from the same commit's diff; the archive file is a copy and does not need to be restored by hand. No data, schema, audit-chain or run-store format changes.

## Tests

- `tests/test_approval_fail_closed_oserror.py`: symlink component check, path argument denial, protected-skill resolution, skill write denial, and the outside-workspace control case.
- `tests/test_policy.py`, `tests/test_shell_obfuscation_adversarial.py`, `tests/test_approval_async_from_sync.py`, `tests/test_sec_tier1_hardening.py`: tests that exercised archived `ApprovalPolicy` methods were moved with the code to the archive. Tests of live code stay in place; the one test of `policy._check_multi_sig_quorum` is retargeted to `MultiSigQuorumManager`, with the same assertion on the quorum result.
- No test is skipped, xfailed or weakened to pass.

## Decision

Proceed with the four commits, each reviewed separately. Q1 (deny precedence, F1) is not decided and is not part of this branch. Q2 (legacy once grants) is not part of this branch.

## Human Review Required

**Yes.** `teaagent/approval/` and `teaagent/policy.py` are high-risk paths. The change touches the approval decision surface (fail-closed checks) and removes a second multi-sig implementation. Security Officer sign-off (Size C) or the second-reviewer ceremony (Size B) is required before merge (plan Q8). The reviewer should run the AST move-equivalence check (plan Step 0 item 3) on the rename and archive commits.

## Human Approval Gate

**OPEN.** No approval has been recorded. The owner reviews this report before the branch merges.

## Test-weakening sign-off (owner, 2026-10-28)

The owner approved the six test removals or reductions that `check_test_assertion_regression` flags against `main`. Each one exercised only the archived `ApprovalPolicy` multi-sig and high-risk copy (A-P1-7):

- `test_approval_async_from_sync.py::test_policy_signature_collection_from_running_loop`
- `test_policy.py::test_high_risk_detection_default_patterns`, `test_del_shuts_down_signature_executor`, `test_del_is_safe_to_call_twice`
- `test_sec_tier1_hardening.py::test_policy_approval_hash_binds_request_id`, and the `ApprovalPolicy` assertion in `test_approval_hash_is_single_source_of_truth`

The live path stays covered. SEC-09 request-id binding on `MultiSigQuorumManager` is pinned by `test_multisig_hash_binds_unique_request_id`. The manager-against-canonical hash agreement remains in `test_approval_hash_is_single_source_of_truth`. The removed tests are archived with the code in `docs/archive/code/policy-multisig-highrisk-tests-2026-10-28.py.txt`.

This sign-off covers the test removals only. The PR's Human Review gate for the approval changes stays open.
