# Approval Manager Split Plan (2026-10-27)

**Status:** Proposed. No code has moved. Human Review gate PENDING (see `docs/reviews/approval-manager-split-risk.md`).
**Owner request:** Plan a split of `teaagent/approval/manager.py` (1,473 lines, still growing).
**Scope:** Plan only. `scripts/check_god_modules.py` is not changed by this plan.
**Path class:** `teaagent/approval/` is high-risk (`scripts/high_risk_paths.yaml`, `review-system.md` §4.2). Every step below requires the §4.2 criteria before merge.

---

## 1. Current-state map

### 1.1 Symbols and line ranges (`teaagent/approval/manager.py`, 1,473 lines)

| Lines | Symbol | Cluster |
| --- | --- | --- |
| 1-36 | Module docstring, imports, `logger = logging.getLogger('teaagent.approval_manager')` (line 32) | header |
| 38-45 | `_PROTECTED_SKILL_PATTERNS`, `_CANDIDATE_SKILL_PREFIX` | skill protection |
| 48-75 | `is_protected_skill_path()` (public, DSK-P0-002) | skill protection |
| 78-92 | `_is_skill_dev_opt_in()` (env var or workspace config) | skill protection |
| 95-100 | `PermissionMode(str, Enum)` | permission mode |
| 103-153 | `JITApprovalState` dataclass (approve_once / consume_once / session approvals) | JIT grants |
| 156-163 | `PeerSignature` (frozen dataclass) | multi-sig |
| 166-220 | `MultiSigQuorumConfig` (frozen dataclass, `from_workspace_config`) | multi-sig |
| 223-233 | `ApprovalRequest` (frozen dataclass, P2P request; name collides with `backend.ApprovalRequest` and `runner._types.ApprovalRequest`) | multi-sig |
| 237-310 | `PermissionModeEnforcer.check()` | permission mode |
| 313 | `_JIT_APPROVAL_TIMEOUT_SECONDS = 60.0` | JIT grants |
| 316-438 | `JITApprovalManager`: `is_approved` 328, `prompt_and_resolve` 339, `_prompt` 373 (TTY, threaded input) | JIT grants |
| 441-728 | `MultiSigQuorumManager`: `__init__` 444, `_audit_event` 462, `is_high_risk` 471, `check_quorum` 491, `_generate_approval_hash` 579, `_collect_peer_signatures` 595, `_run_async_signature_collection` 689, `shutdown` 727 | multi-sig |
| 731-816 | `ApprovalStoreManager`: `check_preset` 742, `check_scoped` 761, `handle_payload_digest_preapproved` 781 | preset / scoped store |
| 819-1281 | `ApprovalManager` (orchestrator; see 1.2) | orchestrator |
| 1284-1285 | `_SSH_VERIFICATION_IMPLEMENTED = True` (imported by two tests) | multi-sig |
| 1288-1314 | `_verify_ssh_signature()` | multi-sig |
| 1317-1365 | `format_denial_message()` (operator-facing remediation text) | denial display |
| 1368-1455 | `_normalize_shell_arg()` (pure; used by `is_high_risk` and by `policy.py`) | shell normalization |
| 1458-1473 | `__all__` (20 names) | facade |

### 1.2 `ApprovalManager` (lines 819-1281) by method

| Lines | Member | Responsibility |
| --- | --- | --- |
| 827-885 | `__init__` | Composes enforcer, JIT, multisig, store managers; builds backend via `backend_from_mode` |
| 887-1053 | `assert_allowed` (`# noqa: C901`) | Decision chain: backend approve -> path containment -> skill protection -> mode denial -> session grant -> once grant -> preset deny/allow -> scoped -> payload preapproval -> multisig -> JIT prompt -> raise |
| 1056 | `_PATH_ARGUMENT_KEYS` | containment |
| 1058-1112 | `_assert_tenant_paths_match` | tenant containment |
| 1114-1116 | `_get_extended_path_keys` | containment |
| 1118-1135 | `_looks_like_path` (static) | containment heuristic |
| 1137-1151 | `_has_symlink_component` (static) | containment |
| 1153-1224 | `_assert_paths_in_workspace` | workspace containment (P0-D-001) |
| 1226-1253 | `_assert_skill_path_not_protected` | skill protection (DSK-P0-002) |
| 1255-1269 | `approve_once` | JIT grant API |
| 1271-1273 | `approve_session` | JIT grant API |
| 1275-1277 | `get_jit_state` | JIT grant API |
| 1279-1281 | `shutdown` | lifecycle |

### 1.3 Cohesion clusters

- **A. Permission mode:** `PermissionMode`, `PermissionModeEnforcer`. About 85 lines. Tightly coupled only to `read_only_runtime_block_reason` and `DenialReasonCode`.
- **B. JIT grants and TTY prompt:** `JITApprovalState`, `JITApprovalManager`, timeout constant. About 180 lines. Depends on `teaagent.policy.compute_scoped_payload_digest` (lazy import) and `governance.conversation_ux`.
- **C. Multi-sig quorum:** `PeerSignature`, `MultiSigQuorumConfig`, the P2P `ApprovalRequest`, `MultiSigQuorumManager`, `_verify_ssh_signature`, `_SSH_VERIFICATION_IMPLEMENTED`. About 400 lines. Depends on `federated_sync`, `async_bridge`, `ssh_signatures`, `_multisig_crypto`.
- **D. Preset and scoped store:** `ApprovalStoreManager`. About 95 lines. Depends on `ergonomics.approval_store` (TYPE_CHECKING) and `policy.compute_scoped_payload_digest`.
- **E. Containment:** skill-path protection (`is_protected_skill_path`, `_is_skill_dev_opt_in`, the two pattern tuples) plus workspace and tenant path checks inside `ApprovalManager`. About 260 lines. This is the fail-closed boundary (see section 4).
- **F. Pure helpers:** `_normalize_shell_arg` (about 90 lines), `format_denial_message` (about 50 lines). No state. Lowest-risk moves.
- **G. Orchestrator:** `ApprovalManager.__init__`, `assert_allowed`, `approve_once`, `approve_session`, `get_jit_state`, `shutdown`. About 265 lines. Decision order lives here.

### 1.4 Fan-in (who imports what)

Matching lines (`approval.manager`, `from teaagent.approval import`, `approval_manager`, `teaagent.approval_manager`), excluding `manager.py` itself: **152 lines in 64 files**.

- `teaagent/` (26 files): `approval/` (5: `__init__`, `core`, `backend`, `policy`, `_multisig_crypto`), `policy.py` (imports `ApprovalManager`, `ApprovalRequest`, `JITApprovalState`, `MultiSigQuorumConfig`, `PeerSignature`, `PermissionMode`, `_normalize_shell_arg`, `_verify_ssh_signature`), `cli/` (9), `tui/` (3), `runner/` (2: `_core.py`, `_governed_execution.py`), `subagents/` (2), `types/permissions.py`, `config_lint.py`, `release_evidence.py`, `_compat_modules.py`.
- `tests/` (34 files; the largest pinned surfaces are `test_policy.py`, `test_efx003_one_time_approval.py`, `test_approval_token_exactness.py`, `test_deny_preset_runtime_enforcement.py`, `test_ws3_schema_path_containment.py`).
- `scripts/` (4): `validate_runner_invariants.py` requires `teaagent.approval.manager` or `teaagent.subagents._approval_queue` in each second-framework file. `migrate_imports.py`, `suppress_complexity.py`, `check_god_modules.py` mention the module by name.

**Hard-coded external dependencies on the module path:**

1. `teaagent/_compat_modules.py:13` aliases `teaagent.approval_manager` to `teaagent.approval.manager`. Tests assert identity of the aliased module. The alias target path must keep existing.
2. `scripts/validate_runner_invariants.py:33` accepts `teaagent.approval.manager` as the approval-authority import. Any file that currently imports it through the facade must keep that exact import string, or the invariant tool must be updated in the same commit.
3. Logger name `teaagent.approval_manager` (manager.py:32). Tests use `caplog.at_level(..., logger='teaagent.approval_manager')` (for example `tests/test_approval_manager_multisig_fallback.py`).
4. `policy.py` imports private names `_normalize_shell_arg` and `_verify_ssh_signature` from the manager. Tests import them from `teaagent.policy` (for example `tests/test_remediation_p1_p2.py:15`), so `policy.py` must keep re-exporting them.
5. `tests/test_approval_manager_multisig_fallback.py` monkeypatches `manager._multisig_manager._collect_peer_signatures` on an instance. This works only if `ApprovalManager` still holds a `MultiSigQuorumManager` instance attribute with that method name.
6. No test found patches `teaagent.approval.manager.<name>` as a module-level string target. This was checked with grep and should be re-checked before each step.

### 1.5 Name hazards already present

- Three classes are named `ApprovalRequest`: `teaagent.approval.manager.ApprovalRequest` (P2P multi-sig broadcast, frozen dataclass), `teaagent.approval.backend.ApprovalRequest` (backend decision input), and `teaagent.runner._types.ApprovalRequest` (re-exported by `approval/core.py`). A split must not add a fourth. Renaming the P2P one is an API change (open question Q4).
- `teaagent/runner/_approval_manager.py` (`RunnerApprovalCoordinator`) is a different object from `teaagent.approval.manager`. The file name is misleading in grep results.

### 1.6 Related duplication outside the file

`teaagent/policy.py` (494 lines) contains a second copy of the multi-sig and high-risk helpers: `_is_high_risk_operation` (218), `_check_multi_sig_quorum` (245), `_generate_approval_hash` (310), `_collect_peer_signatures` (326), `_run_async_signature_collection` (420), `__del__` (459). Verified by grep:

- `_check_multi_sig_quorum`, `_is_high_risk_operation`, `_collect_peer_signatures`, and `_generate_approval_hash` have **no production caller** inside `teaagent/` (only `tests/test_policy.py:1061` and `tests/test_shell_obfuscation_adversarial.py`, plus a comment in `teaagent/governance/review_gate.py:28`).
- The live multi-sig path is `ApprovalManager.assert_allowed` -> `MultiSigQuorumManager.check_quorum` (manager.py:1027-1034).
- `ApprovalPolicy.assert_allowed` delegates to `ApprovalManager` and does not call `_check_multi_sig_quorum`.

A split of `manager.py` alone leaves two multi-sig implementations and two high-risk pattern lists, one of them hard-coded (`['/prod', '/production', 'database', 'delete', 'rm -rf']`). Removing the duplicate is a separate decision (Q3), not part of the pure-move steps.

---

## 2. Target modules

All targets live under `teaagent/approval/`. Sizes are estimates from the line ranges above, with about 15-30 lines of import overhead per module. Each is far below the 800-line rule.

| Module (new) | Contents (from manager.py) | Est. lines | Rule |
| --- | --- | --- | --- |
| `teaagent/approval/_shell_normalize.py` | `_normalize_shell_arg` (1368-1455) | about 100 | pure function, no state |
| `teaagent/approval/_denial_format.py` | `format_denial_message` (1317-1365) | about 60 | pure function, no state |
| `teaagent/approval/_permission_mode.py` | `PermissionMode` (95-100), `PermissionModeEnforcer` (237-310) | about 90 | mode policy |
| `teaagent/approval/_jit.py` | `_JIT_APPROVAL_TIMEOUT_SECONDS` (313), `JITApprovalState` (103-153), `JITApprovalManager` (316-438) | about 195 | JIT grant state and TTY prompt |
| `teaagent/approval/_preset_scope.py` | `ApprovalStoreManager` (731-816) | about 95 | preset and scoped store |
| `teaagent/approval/_multisig.py` | `PeerSignature` (156-163), `MultiSigQuorumConfig` (166-220), `ApprovalRequest` P2P (223-233), `MultiSigQuorumManager` (441-728), `_SSH_VERIFICATION_IMPLEMENTED` (1284-1285), `_verify_ssh_signature` (1288-1314) | about 400 | multi-sig quorum; must keep logger name |
| `teaagent/approval/_skill_protection.py` | `_PROTECTED_SKILL_PATTERNS`, `_CANDIDATE_SKILL_PREFIX`, `is_protected_skill_path` (38-75), `_is_skill_dev_opt_in` (78-92), `_assert_skill_path_not_protected` as mixin method (1226-1253) | about 90 | DSK-P0-002 |
| `teaagent/approval/_path_containment.py` | `_PATH_ARGUMENT_KEYS`, `_assert_tenant_paths_match`, `_get_extended_path_keys`, `_looks_like_path`, `_has_symlink_component`, `_assert_paths_in_workspace` as mixin methods (1056-1224) | about 185 | fail-closed containment; mixin keeps method names |
| `teaagent/approval/manager.py` (kept, stable facade) | `ApprovalManager` orchestrator (819-885, 887-1053, 1255-1281) inheriting the two mixins; re-exports every name in the current `__all__` plus `_normalize_shell_arg`, `_verify_ssh_signature`, `_SSH_VERIFICATION_IMPLEMENTED`, `_JIT_APPROVAL_TIMEOUT_SECONDS`, `is_protected_skill_path`; keeps `logger` named `teaagent.approval_manager` | about 340 | orchestration and facade |

Estimated total: about 1,550 lines across 9 files (up from 1 file of 1,473). The largest module is `_multisig.py` at about 400 lines, which is under the 800-line rule without an exemption.

**Design choices:**

- `manager.py` remains the import target for every existing caller. No caller changes in any step.
- Containment uses **mixins** (`class ApprovalManager(_PathContainmentMixin, _SkillProtectionMixin)`), not free functions. Method names and `self` semantics stay identical, so tests that call `_assert_paths_in_workspace` through an instance keep working, and no behavior is rewritten. Converting these to free functions is a later, separate step, if ever.
- Submodules use the logger name `teaagent.approval_manager` via `logging.getLogger('teaagent.approval_manager')`. This keeps operator tooling and `caplog` assertions stable. A separate logger name would break those assertions.
- Submodules must not import `manager.py`. The dependency direction is `manager.py` -> submodules, one way. This avoids cycles with `policy.py` and `approval/__init__.py`.

---

## 3. Ordered steps

Each step is one commit. Each step is a **pure move**: the moved code is byte-identical except for import lines, and the facade re-exports every name the step moved. Each step must keep the listed tests green.

### Step 0 (test-only, no code moves)

Add pins that the current suite does not have:

1. **Facade identity test.** `teaagent.approval.manager.X is teaagent.approval.<new_module>.X` for every moved name. This must fail if a name is redefined rather than re-exported.
2. **Public surface snapshot.** The set of names in `manager.__all__` plus the private names imported by `policy.py` and the tests. This is a list, not a count.
3. **AST move-equivalence script (dev tool, not in the product).** For each moved function or class, compare the normalized AST between the old and new location, ignoring import statements and the module path. Each move commit must report zero differences. This is the strongest falsifier for "pure move".
4. **Deny-precedence characterization (strict xfail).** A test that asserts a deny preset wins over a session approval and over a once grant. It should be marked `xfail(strict=True)` with a reference to this plan, so the current behavior (bypass; see section 4) is recorded without silently changing it. The owner decides the behavior (Q1). When that decision lands, the xfail flips to a required pass in the same commit as the fix, not in a move commit.

Tests for Step 0: `tests/approval/test_migration_compatibility.py`, `tests/test_circular_imports.py`.

### Step 1: `_shell_normalize.py` (leaf, no dependencies)

- Move `_normalize_shell_arg`. Add a re-export in `manager.py`.
- `policy.py` keeps importing `_normalize_shell_arg` from `manager.py` (no change to `policy.py`).
- Tests: `tests/test_shell_obfuscation_adversarial.py`, `tests/test_remediation_p1_p2.py`, `tests/test_hypothesis_invariants.py`, `tests/test_approval_manager_multisig_fallback.py`.
- `scripts/validate_runner_invariants.py` run.

### Step 2: `_denial_format.py` (leaf)

- Move `format_denial_message`. The text is operator-facing and tests may pin wording.
- Tests: `tests/test_permission_explain.py`, `tests/acceptance/test_policy_denial_reason_code_flow.py`, `tests/acceptance/test_policy_as_code_flow.py`, `tests/test_policy.py`.

### Step 3: `_permission_mode.py`

- Move `PermissionMode` and `PermissionModeEnforcer`. Changing the `PermissionMode` enum is itself a §4.2 trigger, so the enum's value strings (`read-only`, `workspace-write`, `prompt`, `allow`, `danger-full-access`) must not change in this step.
- Tests: `tests/policy/test_permission_matrix.py`, `tests/test_full_access_gate.py`, `tests/acceptance/test_plan_mode_read_only_flow.py`, `tests/test_mode2_tui_chat.py`, `tests/test_policy_routing.py`.

### Step 4: `_jit.py`

- Move `JITApprovalState`, `JITApprovalManager`, `_JIT_APPROVAL_TIMEOUT_SECONDS`.
- The `ApprovalManager.__init__` line that builds `JITApprovalManager` stays in `manager.py` and resolves the name through `manager.py`'s own namespace, so existing patches on `manager.JITApprovalManager` keep working.
- Tests: `tests/test_efx003_one_time_approval.py`, `tests/test_approval_token_exactness.py`, `tests/test_policy_jit.py`, `tests/test_phase5_jit_approval_server.py`, `tests/test_phase6_jit_server.py`, `tests/test_approval_queue_persistence.py`.

### Step 5: `_preset_scope.py`

- Move `ApprovalStoreManager`.
- Tests: `tests/test_deny_preset_runtime_enforcement.py`, `tests/test_approval_token_exactness.py`, `tests/test_auto_mode_authority_audit.py`.

### Step 6: `_multisig.py`

- Move `PeerSignature`, `MultiSigQuorumConfig`, the P2P `ApprovalRequest`, `MultiSigQuorumManager`, `_SSH_VERIFICATION_IMPLEMENTED`, `_verify_ssh_signature`.
- Logger name stays `teaagent.approval_manager`.
- The instance attribute `_multisig_manager` and its method names must not change (fallback test).
- `policy.py` still imports `PeerSignature`, `MultiSigQuorumConfig`, `ApprovalRequest`, `_verify_ssh_signature` from `manager.py`. Re-exports cover this.
- Tests: `tests/test_approval_manager_multisig_fallback.py`, `tests/test_sec_tier1_hardening.py`, `tests/test_hypothesis_invariants.py`, `tests/test_approval_coordination_backend.py`, `tests/test_remediation_p1_p2.py`.

### Step 7: `_skill_protection.py` (mixin)

- Move `_PROTECTED_SKILL_PATTERNS`, `_CANDIDATE_SKILL_PREFIX`, `is_protected_skill_path`, `_is_skill_dev_opt_in`. Move `_assert_skill_path_not_protected` into `_SkillProtectionMixin`.
- Tests: `tests/test_skill_write_quarantine.py`, `tests/test_skill_lifecycle.py`, `tests/test_check_high_risk_paths.py`.

### Step 8: `_path_containment.py` (mixin)

- Move `_PATH_ARGUMENT_KEYS`, `_assert_tenant_paths_match`, `_get_extended_path_keys`, `_looks_like_path`, `_has_symlink_component`, `_assert_paths_in_workspace` into `_PathContainmentMixin`.
- Staticmethods stay staticmethods. The `_has_symlink_component` return behavior on `OSError` must not change (see section 4).
- Tests: `tests/test_ws3_schema_path_containment.py`, `tests/test_approval_manager_symlink_check.py`, `tests/test_tenant_isolation.py`, `tests/integration/test_sec13_security_paths.py`, `tests/test_prompt_injection_boundaries.py`, `tests/test_governance_fuzz.py`.

### Step 9: facade cleanup

- Remove dead imports from `manager.py`. Confirm `__all__` matches Step 0's snapshot exactly.
- `teaagent/approval/__init__.py` `_EXPORTS` map: no change expected. Confirm.
- Tests: all of Steps 1-8, plus `tests/acceptance/test_security_approval_manager_flow.py`, `tests/acceptance/test_efx_durable_effect_flow.py`, `tests/integration/test_approval_ui.py`.

### Step 10: exemption removal (separate commit, after Steps 1-9 are green)

- Remove `'teaagent/approval/manager.py'` from `DEFAULT_EXEMPTIONS` in `scripts/check_god_modules.py:27`. This is the only commit that edits that file.
- Precondition: `python scripts/check_god_modules.py` passes with no exemption for `teaagent/approval/*`.
- Requires the owner decision in Q5 (ADR).

### Full validation at every step

- `pytest -q tests/approval tests/policy tests/test_circular_imports.py tests/test_policy.py` (the policy and enforcement set above).
- `python scripts/validate_runner_invariants.py`
- `python scripts/check_high_risk_paths.py` (if present; otherwise the equivalent pre-commit check).
- `python scripts/check_god_modules.py` (must not get worse: the exemption stays until Step 10).
- AST move-equivalence script from Step 0 (zero differences except imports).

---

## 4. Invariants to preserve

These are what the split must not change. Where the current code does not satisfy an invariant, it is listed as a finding, not as a preserved property.

**I1. Deny preset is terminal. Current state: NOT satisfied on either code path (finding F1).**

- Intended: a matching deny preset blocks the call regardless of prior grants.
- Current order in `ApprovalManager.assert_allowed` (manager.py): session approval early return (974-975) and once-grant consume (979-980) run **before** the preset deny check (987-991).
- Probe result (scratch script, outside the repo, run with the project venv): with a deny preset for `workspace_write_file` (`path_globs=['*']`):
  - baseline (deny only): blocked, `POLICY_DENIED`.
  - deny plus `approve_session(tool)`: **allowed**.
  - deny plus `approve_once(call_id, payload)` with the same call: **allowed**.
  - `ApprovalPolicy.assert_allowed(jit_state=<session approval>)` with the same deny preset: **allowed**.
- No test in `tests/test_deny_preset_runtime_enforcement.py` pins the precedence between deny and session or once grants (its tests cover deny vs. no-deny and revocation only).
- Reachability: the probe shows the bypass on the manager and policy objects directly. A session approval held in the JIT state (the state the runner passes as `jit_state`) is honored even when a deny preset matches. Whether a real run can reach this state is not yet verified end to end. The denial text suggests `teaagent approve --tool X --session`, but I did not confirm that the CLI writes into the JIT state of a later run. The plan does not fix this. The split must preserve current behavior, and the fix is a separate, owner-approved behavior change (Q1, Step 0 item 4).

**I2. Approval token exactness.**

- A once grant with a payload digest matches only the same tool and arguments (`JITApprovalState.consume_once`, manager.py:135-149). A mismatched digest leaves the grant in place.
- Legacy call-id-only grants (no digest) are consumed on the first payload of any content (manager.py:109-110, 145-148). This is documented as intentional. It is weaker than digest binding (finding F2, Q2).
- `tests/test_approval_token_exactness.py` and `tests/test_efx003_one_time_approval.py` pin the digest-bound behavior.

**I3. Fail-closed path matching.**

- `_assert_paths_in_workspace` resolves each candidate under `workspace_root` and raises `WORKSPACE_WRITE_MODE` on containment failure (manager.py:1184-1194 and 1208-1218).
- Symlink components raise `SYMLINK_BLOCKED` (1195-1200, 1219-1224).
- `_assert_tenant_paths_match` raises on a foreign-tenant path (1107-1112).
- Finding F3: `_has_symlink_component` returns **False** on `OSError` (manager.py:1149-1151), so a filesystem error during the symlink check passes the check. Containment (`resolve()` plus `relative_to`) runs first, so the practical gap is narrow, but the component check is fail-open. The split must not change this silently. Q6 asks whether to make it fail closed.
- Finding F4: `_looks_like_path` excludes any string that contains a space (manager.py:1131-1134). Phase 2 checks only named keys (`path`, `file_path`, `target_path`, `file`, plus extras). A path-like value with a space under a non-named key is not checked. Recorded for review; not changed by this plan.
- Finding F5: `_assert_skill_path_not_protected` builds `root_path / raw` without `resolve()` before calling `is_protected_skill_path`, which catches `OSError` and returns False (fail-open on error).

**I4. Audit records.**

- `MultiSigQuorumManager._audit_event` writes `multisig_fallback` to the audit chain when `agent_id` is unset (manager.py:462-469, 516-524). It is best-effort and never changes the gate decision.
- `tool_permission_denied` is emitted by logger (manager.py:959-968). The runner layer records the audit event. The split must keep both the logger name and the `extra` keys.

**I5. ApprovalPolicy before ToolRegistry.execute.**

- This plan does not touch `runner/_governed_execution.py` or the runner. Every step must leave the call sites in `runner/_core.py` and `runner/_governed_execution.py` unchanged.

**I6. Identity and import stability.**

- Every name reachable as `teaagent.approval.manager.X`, `teaagent.approval.X` (lazy map in `approval/__init__.py`), `teaagent.approval_manager.X` (alias in `_compat_modules.py`), and `teaagent.policy.X` (re-export) must remain the **same object** after each step.

**I7. Multi-sig fails to the standard approval chain, not to allow.**

- If `agent_id` is unset, `check_quorum` returns False and the call falls through to JIT prompting (manager.py:505-529). The split must not add an allow branch.

---

## 5. Removing the god-module exemption

The exemption at `scripts/check_god_modules.py:27` is annotated "migration completed". That is not accurate: the file is 1,473 lines and the exemption is the only thing keeping it out of the 800-line check. The comment also says "Explicit exemptions require an ADR or documented rationale", and no ADR backs it.

Removal, at the end of the plan:

1. Steps 1-9 land. Every file under `teaagent/approval/` is under 800 lines (verify with `scripts/check_god_modules.py --threshold 800` after temporarily removing the entry in a scratch copy, not in the repo).
2. Step 10 removes the single exemption line. No other exemption changes in this plan.
3. The ADR for the package layout (Q5) is accepted before Step 10 merges.

`teaagent/approval/*` files are not individually exempt today, so only `manager.py` needs a line removed.

---

## 6. Rollback

- **Per step.** Each step is one commit. `git revert <sha>` restores the previous file layout. The facade keeps every name, so callers never need to change in any step.
- **No data or schema change.** The approval store, grant files, audit chain, and run records are not touched. No migration or repair is needed.
- **Partial rollback.** If Step N is reverted but Step N+1 is kept, Step N+1 must not depend on Step N's new module. Each step's module must be importable from `manager.py` alone, so a revert of an earlier step means reverting later dependent steps first. This is checked by the import-order test in Step 0.
- **Rollback of Step 10.** Restore the exemption line. No other effect.
- **Rollback of Step 0 xfail.** Delete the xfail test. No effect on behavior.
- **If F1 is fixed during the split window.** The fix is its own commit with its own tests (Q1). Rollback of the split must then not revert the fix. Use `git revert` on the move commits only.

---

## 7. Acceptance criteria and falsifiability

### Acceptance (all required)

1. `teaagent/approval/manager.py` is under 800 lines. Every new module is under 800 lines.
2. `scripts/check_god_modules.py` passes with the manager exemption removed (Step 10).
3. Identity test (Step 0 item 1) passes for every moved name.
4. Public surface snapshot (Step 0 item 2) is unchanged from the baseline.
5. AST move-equivalence reports zero differences per move commit, except import lines.
6. The listed test files for each step pass, with no test edited to pass. Test edits in a move commit are a failure of this plan.
7. `scripts/validate_runner_invariants.py` passes.
8. `tests/approval/test_migration_compatibility.py` and `tests/test_circular_imports.py` pass.
9. Logger name `teaagent.approval_manager` is unchanged (verified by the caplog-based tests).
10. No new public symbol is added and no symbol is removed. Count before and after: the `__all__` of `manager.py` is the same set.
11. The deny-precedence xfail (Step 0 item 4) remains xfail with the same reason until Q1 is decided. It must not start passing, or fail, as a side effect of a move.

### Falsifiers (any one shows the split broke something)

- A move commit changes any non-import line of a moved function (AST check fails).
- An identity test fails: two paths yield different objects for the same name.
- An import-order test fails (for example importing `teaagent.policy` first, then `teaagent.approval.manager`, or the reverse). `tests/test_circular_imports.py` covers this.
- A caplog test fails because a warning moved to a different logger.
- The deny-precedence xfail starts passing with no fix commit (a move changed behavior), or the strict xfail is removed.
- `validate_runner_invariants.py` reports a missing approval authority import.
- Any test in the listed policy and enforcement set fails at its step.
- Any file under `teaagent/approval/` grows past 800 lines after a move (layout is wrong).

---

## 8. Open questions for the owner

- **Q1 (behavior, blocks Step 0 item 4).** Should a deny preset be terminal over session approvals and once grants (finding F1)? Recommended: yes. The fix is a separate behavior commit: move the preset deny check before the session and once-grant early returns, with the strict xfail flipped to a required pass. The split does not do it.
- **Q2.** Keep legacy call-id-only once grants (consumed on any payload)? Recommended: retire them, or require a digest for new grants. Retiring them is a behavior change and needs its own commit.
- **Q3.** Delete the duplicate multi-sig and high-risk helpers in `policy.py` (about 215 lines, production-uncalled except by `tests/test_policy.py:1061`)? This is out of scope for the manager split but changes the same security surface. Recommended: yes, as a separate step after Step 10, with the test at `tests/test_policy.py:1061` retargeted to `MultiSigQuorumManager`.
- **Q4.** Rename the P2P `ApprovalRequest` in `_multisig.py` (for example `PeerApprovalRequest`) and keep a deprecated alias? This removes the three-way name collision (section 1.5). It is an API change.
- **Q5.** Write an ADR for the `approval/` package layout before Step 1, and cite it in the exemption removal? Recommended: yes. Number to be assigned by the owner.
- **Q6.** Make `_has_symlink_component` and `is_protected_skill_path` fail closed on `OSError` (F3, F5)? Recommended: yes, as its own behavior commit with a test.
- **Q7.** Keep underscore-private module names (`_jit.py`, `_multisig.py`), or use public names (`jit.py`, `multisig.py`)? This plan uses underscore names to keep the public surface unchanged. Public names would invite new imports that bypass the facade.
- **Q8.** Sign-off. Review size is B or C in `review-system.md` §2-3. Who signs the §4.2 criteria, including Security Officer sign-off (Size C) or the second-reviewer plus `full_access_acknowledged` ceremony (Size B)?
- **Q9.** Is the split worth doing before Q1 is decided? Recommended: decide Q1 first. The split is mechanical, but a security finding should not be carried through a refactor without an explicit decision on its behavior.

---

## 9. References

- `teaagent/approval/manager.py` (subject of this plan).
- `teaagent/approval/__init__.py` (lazy export map, unchanged).
- `teaagent/_compat_modules.py` (legacy alias `teaagent.approval_manager`).
- `scripts/check_god_modules.py` (exemption at line 27; not changed by this plan).
- `scripts/high_risk_paths.yaml` (`teaagent/approval/` is high-risk).
- `docs/retrospective/review-system.md` §4.2 (High-Risk Change Criteria).
- `docs/reviews/approval-manager-split-risk.md` (risk report for this plan).
- `docs/reviews/a-p1-4-approval-migration-risk.md` (the earlier root-to-package migration; same mechanics).
- `docs/retrospective/06-action-register.md` A-P1-4 (complete), A-P1-6 (added for this plan, status in progress).
