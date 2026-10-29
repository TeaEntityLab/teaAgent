# ADR 0044: Approval Package Layout

## Status

Accepted — 2026-10-29 (owner)

**Decision owner:** project owner (approval split plan Q5, 2026-10-27).
**Human Review gate:** closed. The owner accepted this ADR on 2026-10-29 after the split landed as pure moves (TeaEntityLab/teaAgent#111). The approval-hardening review it depended on shipped in TeaEntityLab/teaAgent#108.

**Review trigger:** owner acceptance, or completion of the split (plan steps 0-10), whichever comes first.

## Context

`teaagent/approval/manager.py` holds the approval orchestrator and most of its policy
machinery in one file: about 1,480 lines and still growing. It is a high-risk path
(`scripts/high_risk_paths.yaml`, `review-system.md` section 4.2). The repository's
god-module rule is 800 lines (`scripts/check_god_modules.py`). The file is exempt from that
rule at `scripts/check_god_modules.py:27`, annotated "migration completed". That comment is
not accurate: the file is far above the threshold, and the exemption has no ADR behind it.
`review-system.md` section 4 requires an ADR or documented rationale for an exemption.

The file has seven clusters with few dependencies between them:

- shell-argument normalization (pure function);
- denial message formatting (pure function);
- permission mode policy (`PermissionMode`, `PermissionModeEnforcer`);
- just-in-time grant state and the TTY prompt (`JITApprovalState`, `JITApprovalManager`);
- preset and scoped approval store (`ApprovalStoreManager`);
- multi-signature quorum (`PeerSignature`, `MultiSigQuorumConfig`, the peer approval request, `MultiSigQuorumManager`, SSH verification);
- skill-directory protection and path containment (`is_protected_skill_path`, `_has_symlink_component`, `_assert_paths_in_workspace` and helpers).

The split plan (`docs/plans/approval-manager-split-plan-2026-10-27.md`, on branch
`claude/approval-split-plan`) proposes ten ordered steps, each a pure move with an
AST equivalence check. The plan's line ranges were measured on the 1,473-line file. Re-derive
them before Step 1.

Three classes named `ApprovalRequest` existed in the approval and runner packages before
this ADR. The P2P multi-signature class was renamed to `PeerApprovalRequest` under A-P1-8,
with `ApprovalRequest` kept as an alias for that class. The duplicate multi-signature code in
`policy.py` was archived under A-P1-7. Neither change moves code between modules.

## Decision

### Target modules

All targets live under `teaagent/approval/`. The sizes are estimates from the plan.

| Module (new) | Contents moved from `manager.py` | Est. lines | Notes |
| --- | --- | --- | --- |
| `_shell_normalize.py` | `_normalize_shell_arg` | ~100 | Pure function, no state. Leaf. |
| `_denial_format.py` | `format_denial_message` | ~60 | Operator-facing wording. Tests may pin it. Leaf. |
| `_permission_mode.py` | `PermissionMode`, `PermissionModeEnforcer` | ~90 | The enum values (`read-only`, `workspace-write`, `prompt`, `allow`, `danger-full-access`) must not change. |
| `_jit.py` | `_JIT_APPROVAL_TIMEOUT_SECONDS`, `JITApprovalState`, `JITApprovalManager` | ~195 | JIT grant state and TTY prompt. |
| `_preset_scope.py` | `ApprovalStoreManager` | ~95 | Preset and scoped store. |
| `_multisig.py` | `PeerSignature`, `MultiSigQuorumConfig`, `PeerApprovalRequest`, `MultiSigQuorumManager`, `_SSH_VERIFICATION_IMPLEMENTED`, `_verify_ssh_signature` | ~400 | Must keep the logger name. Largest module, under 800 lines without an exemption. |
| `_skill_protection.py` | `_PROTECTED_SKILL_PATTERNS`, `_CANDIDATE_SKILL_PREFIX`, `is_protected_skill_path`, `_is_skill_dev_opt_in`; `_assert_skill_path_not_protected` as a mixin method | ~90 | DSK-P0-002. |
| `_path_containment.py` | `_PATH_ARGUMENT_KEYS`, `_assert_tenant_paths_match`, `_get_extended_path_keys`, `_looks_like_path`, `_has_symlink_component`, `_assert_paths_in_workspace` as mixin methods | ~185 | Fail-closed containment. Mixin keeps method names. |
| `manager.py` (kept) | `ApprovalManager` orchestrator, inheriting the two mixins | ~340 | The stable facade. |

The estimated total is about 1,550 lines across nine files, up from one file of 1,473 lines.

### Facade rule

`teaagent/approval/manager.py` stays the import target for every existing caller. It
re-exports every name in its current `__all__`, plus the private names that `policy.py`,
the tests and the scripts import (`_normalize_shell_arg`, `_verify_ssh_signature`,
`_SSH_VERIFICATION_IMPLEMENTED`, `_JIT_APPROVAL_TIMEOUT_SECONDS`, `is_protected_skill_path`).
No caller changes in any move step. Each name reachable as `teaagent.approval.manager.X`,
`teaagent.approval.X` (the lazy map in `approval/__init__.py`), `teaagent.approval_manager.X`
(the alias in `_compat_modules.py`) or `teaagent.policy.X` (the re-export) must remain the
same object after every step.

Submodules must not import `manager.py`. The dependency direction is one way, from
`manager.py` to the submodules. This prevents cycles with `policy.py` and
`approval/__init__.py`, which `tests/test_circular_imports.py` checks at every step.

### Naming

Submodules use underscore-private names (`_jit.py`, `_multisig.py`). Public names
(`jit.py`, `multisig.py`) would invite new imports that bypass the facade. This is the
plan's Q7 default; the owner confirms it when accepting this ADR.

### Invariants

The split must preserve these. Where the current code does not satisfy one, the finding is
recorded and is not changed by a move.

1. **Deny preset is terminal (finding F1, not satisfied today).** The preset deny check runs
   after the session approval and once-grant early returns in `ApprovalManager.assert_allowed`.
   No move reorders them. The strict xfail that records the bypass stays until owner decision
   Q1 is recorded; the fix is a separate behaviour commit.
2. **Approval token exactness.** A once grant with a payload digest matches only the same
   tool and arguments. Legacy call-id-only grants (finding F2, owner decision Q2) are unchanged.
3. **Fail-closed path matching.** Containment failures raise `WORKSPACE_WRITE_MODE`; symlink
   components raise `SYMLINK_BLOCKED`; a path check that hits `OSError` denies (G-P1-11 landed
   this before the split, so the split inherits it).
4. **Audit records.** `multisig_fallback` is written to the audit chain when `agent_id` is
   unset, best-effort, and never changes the gate decision. `tool_permission_denied` keeps
   its logger name and `extra` keys. The logger name stays `teaagent.approval_manager`.
5. **ApprovalPolicy before ToolRegistry.execute.** The split does not touch
   `runner/_core.py` or `runner/_governed_execution.py`.
6. **Identity and import stability.** Every re-exported name is the same object across the
   four import paths above, checked by an identity test (plan Step 0 item 1).
7. **Multi-sig fails to the standard approval chain, not to allow.** An unset `agent_id`
   returns False and the call falls through to JIT prompting.

### Removing the god-module exemption

The exemption at `scripts/check_god_modules.py:27` is removed in a single commit after the
move steps are green, and only after this ADR is accepted. Its precondition is that
`python scripts/check_god_modules.py` passes with no `teaagent/approval/*` exemption. No
other exemption changes as part of the split.

## Rationale

- **Size.** Each target module is far below 800 lines, and the largest (`_multisig.py`,
  about 400 lines) needs no exemption.
- **Pure moves.** Each step moves byte-identical code except import lines, with an AST
  equivalence check (plan Step 0 item 3). A reviewer can verify a move without re-reading
  the approval logic.
- **Facade.** Keeping `manager.py` as the import target means no caller changes, and each
  step reverts with one `git revert`.
- **Mixins for containment.** Converting the containment helpers to free functions would
  change method resolution and test patch points. That conversion is not part of the split.

## Consequences

### Positive

- The god-module exemption can be removed, with an ADR behind it, as the plan requires.
- The approval decision surface is reviewable one cluster at a time.

### Negative

- Nine modules instead of one. The orchestrator is still the facade, so the reader follows
  imports from `manager.py`.
- The estimated total grows by about 80 lines of import overhead.

### Not decided by this ADR

- **Deny precedence (F1, Q1)** and **legacy call-id-only grants (F2, Q2)** are behaviour
  decisions. This ADR does not decide them, and no move changes them.
- **Public module names (Q7).** This ADR keeps underscore names.
- **Converting mixins to free functions.** Deferred; not part of the split.

## Alternatives Considered

1. **Keep one file and keep the exemption.** Rejected. It leaves the repository's own size rule
   unenforced on the highest-risk file, and the exemption has no ADR.
2. **Public module names (`jit.py`, `multisig.py`).** Rejected for now. The public names would
   invite imports that bypass the facade and widen the public surface.
3. **Split the file in one commit.** Rejected. A single large move is hard to verify, and the
   AST check depends on one cluster per commit.
4. **Free functions for containment.** Deferred. It changes method resolution and the patch
   points that tests use.

## References

- `docs/plans/approval-manager-split-plan-2026-10-27.md` (on branch `claude/approval-split-plan`).
- `docs/reviews/approval-manager-split-risk.md` (on branch `claude/approval-split-plan`).
- `docs/reviews/approval-hardening-risk.md` (this branch; the open human review gate).
- `docs/retrospective/06-action-register.md`: G-P1-11, A-P1-7, A-P1-8, A-P1-9.
- `scripts/check_god_modules.py` (exemption at line 27); `scripts/high_risk_paths.yaml`.
- `teaagent/_compat_modules.py` (the `teaagent.approval_manager` alias).
- ADR-0040 (second framework invariants) and ADR-0041 (harness thinning) for the harness-thin direction.
