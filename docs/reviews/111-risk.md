# Risk Report — PR 111: approval/manager.py split (pure moves)

> **Claim class:** Risk note for one branch. Not current truth.
> **Last reviewed:** 2026-10-28

**Date:** 2026-10-28
**Scope:** A-P1-6 — split `teaagent/approval/manager.py` (1,538 lines on main) into `teaagent/approval/_*.py` modules behind the stable facade `teaagent.approval.manager`, per `docs/adr/0044-approval-package-layout.md`.
**Source plan:** `docs/plans/approval-manager-split-plan-2026-10-27.md` and risk review `docs/reviews/approval-manager-split-risk.md` (both on branch `claude/approval-split-plan`, not on `main`; cited by path only).
**High-risk paths touched:** `teaagent/approval/` (per `scripts/high_risk_paths.yaml`). `teaagent/policy.py`, `teaagent/runner/_core.py` and `teaagent/runner/_governed_execution.py` are **not** edited by this change.
**Human review gate:** OPEN. No approval is recorded in this report. ADR-0044 is Proposed and its acceptance is also open; the god-module exemption is not removed by this change.

## What changes

1. **Pure moves only.** Each step cuts a definition (or a class member, for the two mixins) out of `manager.py` and pastes it, unchanged, into one new `teaagent/approval/_<cluster>.py` module. The moved code is byte-identical; only import lines and the module logger line are added.
2. **Facade kept.** `teaagent/approval/manager.py` re-exports every name it exposed before (its `__all__`, plus the private names `policy.py`, the tests and the scripts import). `__all__` is unchanged. No caller changes.
3. **Logger name kept.** Every module that logs uses `logging.getLogger('teaagent.approval_manager')`, so `caplog` tests and operator tooling see the same logger name.
4. **No behavior change.** The deny-precedence order in `ApprovalManager.assert_allowed` (already fixed on main, pinned by `tests/test_deny_preset_terminal_over_grants.py`), the digest-binding rules, path containment, skill protection, multi-sig and the `PermissionMode` values are not edited.
5. **Not in this change.** The `teaagent/approval/manager.py` exemption in `scripts/check_god_modules.py` is not removed here. ADR-0044 says the removal happens only after that ADR is accepted.

## Risk assessment

- **Blast radius.** Every approval decision passes through the moved code. The risk is that a move changes a line, drops a re-export, or creates a second class object for the same name. Each is checked per step by an AST move-equivalence script (run outside the repo), a `dir()` parity check on `teaagent.approval.manager`, and the approval-related test subset.
- **Failure modes.**
  - *Two objects for one name.* A moved name re-defined rather than re-exported would make `isinstance` and enum checks fail. Control: the AST script flags any moved definition still present in `manager.py`, and identity tests cover the four import paths.
  - *Patch target goes stale.* A test that monkeypatches a module global the moved code now resolves from its new module would keep passing while no longer exercising the patch. Two such targets exist: `teaagent.approval.manager._is_skill_dev_opt_in` (`tests/test_approval_fail_closed_oserror.py`) and `teaagent.approval_manager._verify_ssh_signature` (`tests/test_sec_tier1_hardening.py`). Control: `_assert_skill_path_not_protected` stays in `manager.py` so the first patch keeps working; the second patch only sits on a path that returns before signature verification, so the test's assertion does not depend on it. No test is edited.
  - *Circular import.* Submodules never import `manager.py`. `tests/test_circular_imports.py` and `scripts/check_circular_imports.py` run at every step.
  - *Test edited to pass.* Forbidden for move commits. The test-file diff of each move commit is checked to be empty.
- **Thin harness.** `manager.py` shrinks; no new framework, event type, dependency or runtime path. `runner/_core.py` is unchanged.
- **Not changed.** F1 (deny precedence) is fixed on main and not touched here. F2 (legacy call-id-only once grants), F3/F5 (already fail-closed on main), F4 (`_looks_like_path` space heuristic), Q3 (`policy.py` duplicate multi-sig code, archived under A-P1-7) are outside this change.

## Dry run and rollback

- **Dry run.** Per step: the step's pinned tests, the approval/deny/policy/permission/multisig/jit/skill/symlink test subset, `ruff check`, `ruff format`, `mypy teaagent/approval --explicit-package-bases`, `scripts/check_circular_imports.py`, `scripts/check_any_count.py --fail-on-increase`, `scripts/check_complexity.py --max 99`, `scripts/check_public_docstrings.py`, the `dir()` parity check, and the AST move-equivalence script.
- **Rollback.** One commit per step. `git revert <sha>` restores the previous layout because the facade keeps every name. No data, schema, grant-store or audit-chain format changes.

## Tests

- Existing tests are not edited, skipped or xfailed. No test is added with `xfail`.
- Step 0 adds identity and public-surface tests under `tests/approval/` (new file only).
- The deny-precedence characterisation required by the plan (Step 0 item 4) is already a required, non-xfail test on main: `tests/test_deny_preset_terminal_over_grants.py`.

## Decision

Proceed with the pure-move steps the owner approved on 2026-10-27, one commit per step, each validated as above. This report does not record the Human Review approval it asks for. Until the owner records it here, this change should not be merged, and the exemption removal waits for ADR-0044 acceptance.
