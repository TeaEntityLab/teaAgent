# Phase 0 Priority Work Items
# 2026-06-04

## Purpose

This work log turns the cross-review and critical questioning documents into
concrete tasks. It intentionally favors trust repair over feature expansion.

Related implementation/reflection record:
`parallel-phase-0-implementation-report-2026-06-04.md`.

## Work Items

| ID | Priority | Task | Evidence | Acceptance criteria |
| --- | --- | --- | --- | --- |
| P0-TR-001 | P0 | Gate `allow_all_destructive` behind explicit full-access semantics | Historical behavior allowed `allow_all_destructive` in prompt mode | Prompt mode with `allow_all_destructive=True` fails; legitimate bypass callers must use an explicit broad permission mode and tests cover the contract |
| P0-TR-002 | P0 | Rename or consolidate runner-local `ApprovalManager` | Historical duplicate name; current code has `RunnerApprovalCoordinator` | Only one canonical approval authority name remains; runner helper name reflects workflow role |
| P0-TR-003 | P0 | Break policy/approval lazy reverse import | Historical reverse import risk; current import-order tests pass | Shared normalization helper extracted or no reverse import remains; import-order smoke test added |
| P0-TR-004 | P0 | Make memory canonical source structural | Historical split; current `memory_legacy.py` re-exports `memory.catalog` | One runtime implementation remains, or duplicate is quarantined with tests proving import target |
| P0-TR-005 | P0 | Add coverage omit ledger | 16 omit patterns in `pyproject.toml` | Each omit has owner, reason, risk, and expected return milestone |
| P0-TR-006 | P0 | Add optional-extra dependency audit policy | `google-adk` optional tree can pull vulnerable transitive deps | Security docs distinguish base audit, lockfile audit, and optional-extra audit cadence |
| P0-TR-007 | P0 | Assign or close proposed ADRs | ADRs 0010, 0012, 0014, 0015, 0017, 0018 are Proposed | Each has owner and one of Accepted/Rejected/Superseded/Archived |
| P1-TR-008 | P1 | Add at least one smoke test per coverage-omitted package | TUI, tournament, validation, WASM and other paths are omitted | Smoke test exists or explicit non-testable rationale exists |
| P1-TR-009 | P1 | Build generated docs front door | 435 Markdown files make discovery hard | `docs/INDEX.md` or equivalent links current status, risk, roadmap, tickets, ADRs, and historical evidence |
| P1-TR-010 | P1 | Calibrate security severity levels | Review says Critical, module docs say High for similar bypasses | Shared severity rubric exists and high-risk docs are updated |
| P1-TR-011 | P1 | Separate "behavior preservation" tests from "safety intent" tests | Current tests can preserve risky bypass behavior | Security tests assert desired contract, not only legacy behavior |
| P1-TR-012 | P1 | Refresh dependency audit report after security workflow change | Existing dependency report predates recent optional-extra scan correction | Report states base/dev/optional audit surfaces separately |

## Recommended Execution Order

1. `P0-TR-001`: approval bypass semantics.
2. `P0-TR-002`: approval authority naming.
3. `P0-TR-003`: policy/approval import boundary.
4. `P0-TR-004`: memory catalog canonicalization.
5. `P0-TR-005` and `P0-TR-006`: governance ledgers.
6. `P0-TR-007`: ADR ownership cleanup.
7. P1 items only after at least the first four P0 items have tests.

## Human Review Gates

Human review should be required before:

- Removing or redefining `danger-full-access`.
- Changing default permission mode behavior.
- Deleting `memory/catalog.py` or `memory_legacy.py`.
- Removing coverage omit entries without replacement tests.
- Adding a broad dependency override for security scan convenience.

## Done Means

Phase 0 trust repair is done only when the following are all true:

- A destructive operation cannot bypass approval unless the user explicitly
  selected and acknowledged the relevant full-access semantics.
- Approval code has one obvious authority path.
- Memory code has one obvious authority path.
- Docs expose the current truth without requiring search through dated layers.
- Security CI distinguishes base package safety from optional runtime safety.
- Tests fail when the trust contract is weakened.

## Status Log

- 2026-06-04 — **P0-TR-001 DONE.** `allow_all_destructive` is now inert in
  non-full-access modes (notably `prompt`) even when
  `full_access_acknowledged=True` is set. The acknowledgement flag records
  ceremony metadata; it does not grant authority by itself. The bypass at
  `PermissionModeEnforcer.check` now fails safe and raises `ToolPermissionError`
  with reason code `DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED`. The two
  legitimate callers promote explicitly: auto mode
  (`runner/_auto_mode_manager.py`, opt-in) returns a `danger-full-access`
  policy scoped by `AutoModeGuard`, and chat (`chat_agent.py`) maps the explicit
  `--allow-destructive` user flag to `danger-full-access`. No CLI/UX change for
  existing `--allow-destructive` users. Covered by
  `tests/test_full_access_gate.py` (enforcer, policy/manager, and auto-mode
  layers) plus a regression guard in
  `tests/regression/test_contract_approval.py::test_allow_all_destructive_without_ack_blocks`.
  Current verification: 3273 passed, 141 skipped, 18 subtests passed, 0 failed
  on Python 3.12.8.
- 2026-06-04 — **P0-TR-002 DONE.** The runner-local approval workflow helper is
  now `RunnerApprovalCoordinator`, while the canonical authority remains
  `teaagent.approval_manager.ApprovalManager`. `rg 'class ApprovalManager'
  teaagent tests` returns only the canonical runtime class. Regression guard:
  `tests/test_circular_imports.py::test_runner_approval_helper_is_not_named_approval_manager`.
- 2026-06-04 — **P0-TR-003 VERIFY/CLOSE.** `teaagent.approval_manager` no
  longer imports `teaagent.policy`; import-order smoke tests cover
  policy-first and approval-manager-first load order. Remaining work is to keep
  future normalization helpers out of either side of the policy boundary.
- 2026-06-04 — **P0-TR-004 DONE.** `teaagent.memory.catalog` is the canonical
  implementation. `teaagent.memory` and `teaagent.memory_legacy` both re-export
  the same classes for compatibility. Regression guard:
  `tests/test_circular_imports.py::test_memory_catalog_canonical_export_path`.
