# Claim-to-Test Traceability Matrix

> **Receipts before rhetoric.** Every product claim either points to a passing acceptance test
> and a runnable evidence command, or is explicitly labelled **roadmap** (not current capability).

Machine-readable source: [`claim-to-test-traceability.yaml`](claim-to-test-traceability.yaml)  
Drift-detection test: [`tests/acceptance/test_claim_traceability.py`](../../tests/acceptance/test_claim_traceability.py)

Last verified: 2026-06-11

---

## Top-10 Claims

| # | Claim | Status | Acceptance Test | Evidence Command |
|---|-------|--------|-----------------|-----------------|
| C1 | local-first | shipping | `test_workspace_edit_flow.py`, `test_first_hour_e2e_flow.py` | `teaagent run "..." --permission-mode read-only --root .` |
| C2 | provider-agnostic | shipping | `test_provider_matrix_consistency_flow.py`, `test_live_provider_conformance_flow.py` | `pytest tests/acceptance/test_provider_matrix_consistency_flow.py -v` |
| C3 | permission-modes | shipping | `test_plan_mode_read_only_flow.py`, `test_automation_permission_and_autopropose_flow.py` | `pytest tests/acceptance/test_plan_mode_read_only_flow.py -v` |
| C4 | policy-as-code | shipping | `test_policy_as_code_flow.py` | `pytest tests/acceptance/test_policy_as_code_flow.py -v` |
| C5 | cost-boundary | shipping | `test_automation_budget_caps_flow.py`, `test_cost_tracking_flow.py` | `pytest tests/acceptance/test_automation_budget_caps_flow.py tests/acceptance/test_cost_tracking_flow.py -v` |
| C6 | audit-log | shipping | `test_audit_chain_integrity_flow.py` | `pytest tests/acceptance/test_audit_chain_integrity_flow.py -v` |
| C7 | run-evidence | shipping | `test_run_evidence_summary_flow.py` | `pytest tests/acceptance/test_run_evidence_summary_flow.py -v` |
| C8 | undo-recovery | shipping | `test_run_undo_acceptance_flow.py`, `test_agent_undo_cli_flow.py` | `teaagent undo --last` + `pytest tests/acceptance/test_run_undo_acceptance_flow.py -v` |
| C9 | plan-spec-gate | shipping | `test_plan_cli_flow.py`, `test_from_plan_cli_flow.py`, `test_plan_mode_read_only_flow.py` | `pytest tests/acceptance/test_plan_cli_flow.py tests/acceptance/test_from_plan_cli_flow.py -v` |
| C10 | docs-as-control-plane | experimental | `test_docs_acceptance_count_accuracy.py` | `pytest tests/acceptance/test_docs_acceptance_count_accuracy.py tests/acceptance/test_claim_traceability.py -v` |

---

## Claim Detail

### C1 — local-first

**Claim:** TeaAgent runs against a local workspace root with explicit permission modes. No cloud delegation by default.

**Source docs:**
- `README.md` line 8: "TeaAgent is not a generic IDE agent clone or hosted cloud delegate. It is a local-first harness you operate"
- `docs/product-contract.md` line 9: "Local-first by default — runs against a workspace root with explicit permission modes."

**Acceptance tests:**
- `tests/acceptance/test_workspace_edit_flow.py::test_hash_read_edit_git_test_and_diff_summary`
- `tests/acceptance/test_first_hour_e2e_flow.py` (full workflow uses `tmp_path` as workspace root, not a remote)

**Evidence command:**
```bash
teaagent run "summarize the test suite" --permission-mode read-only --root .
# Verify: output contains workspace path, no remote endpoint required
```

**Gap note:** No acceptance test contains an explicit assertion that a cloud endpoint is NOT called. Coverage is structural (all acceptance tests use local `tmp_path`). A negative assertion test would close this gap.

**Status:** shipping

---

### C2 — provider-agnostic

**Claim:** TeaAgent adapts to multiple LLM providers via a provider-adapter pattern; not tied to one model vendor.

**Source docs:**
- `README.md` line 198: diagram showing "14 providers"
- `docs/product-contract.md` line 10: "Provider-adapter based — connects to LLM providers; it is not a model framework."

**Acceptance tests:**
- `tests/acceptance/test_provider_matrix_consistency_flow.py::test_provider_registry_matches_docs_and_cli_output`
- `tests/acceptance/test_live_provider_conformance_flow.py::test_live_conformance_skips_without_required_env_and_does_not_call_provider`

**Evidence command:**
```bash
pytest tests/acceptance/test_provider_matrix_consistency_flow.py -v
# Verifies provider registry matches docs and CLI output
```

**Gap note:** Live multi-provider conformance test skips without `TEAAGENT_ACCEPT_LIVE_CONFORMANCE` env var. The "14 providers" count is only verified by registry-vs-docs consistency, not by exercising each provider adapter.

**Status:** shipping

---

### C3 — permission-modes

**Claim:** Five permission modes enforced at the harness level: `read-only`, `workspace-write`, `prompt`, `allow`, `danger-full-access`.

**Source docs:**
- `docs/product-contract.md` line 14: "Permission-mode enforced — read-only, workspace-write, prompt, allow, and danger-full-access are first-class."
- `README.md` line 198: "(5 permission modes)"

**Acceptance tests:**
- `tests/acceptance/test_plan_mode_read_only_flow.py::test_read_only_plan_mode_allows_inspection_and_returns_planning_metadata`
- `tests/acceptance/test_plan_mode_read_only_flow.py::test_read_only_plan_mode_blocks_workspace_write`
- `tests/acceptance/test_plan_mode_read_only_flow.py::test_read_only_plan_mode_blocks_shell_mutation`
- `tests/acceptance/test_automation_permission_and_autopropose_flow.py::test_automation_permission_mode_matrix_flows_into_background_command`

**Evidence command:**
```bash
pytest tests/acceptance/test_plan_mode_read_only_flow.py -v
```

**Gap note:** No single test exercises all five modes in one run. `danger-full-access` mode coverage exists in `test_policy_as_code_flow.py` (side-effect: deny rules fire even in danger mode). `prompt` and `allow` modes are exercised indirectly in automation tests.

**Status:** shipping

---

### C4 — policy-as-code

**Claim:** Workspace `policy.yaml` defines deny rules that block matching tool calls before execution.

**Source docs:**
- `docs/acceptance.md` line 89: "test_policy_as_code_flow.py | Policy-as-code deny rules"
- `docs/product-contract.md`: "Tool-boundary centered — all side effects flow through ToolRegistry, ApprovalPolicy, and workspace tools."

**Acceptance tests:**
- `tests/acceptance/test_policy_as_code_flow.py::test_policy_yaml_loaded_from_workspace`
- `tests/acceptance/test_policy_as_code_flow.py::test_deny_rule_blocks_matching_tool_in_runner`
- `tests/acceptance/test_policy_as_code_flow.py::test_deny_rule_does_not_block_non_matching_tool`
- `tests/acceptance/test_policy_as_code_flow.py::test_deny_rule_fires_in_danger_full_access_mode`

**Evidence command:**
```bash
pytest tests/acceptance/test_policy_as_code_flow.py -v
```

**Status:** shipping

---

### C5 — cost-boundary

**Claim:** Hard cost cap enforced via `--max-estimated-cost-cents`; run aborts if budget ceiling is hit.

**Source docs:**
- `README.md` line 31: "Cost cap | ✅ hard budget via `--max-estimated-cost-cents`"
- `docs/strategy/reflective-strategic-assessment-2026-06-06.md` line 67: "Hard cost cap (`--max-estimated-cost-cents`) | Stable"

**Acceptance tests:**
- `tests/acceptance/test_automation_budget_caps_flow.py::test_reconcile_marks_runtime_cap_exceeded`
- `tests/acceptance/test_cost_tracking_flow.py::test_run_result_exposes_token_counts`
- `tests/acceptance/test_cost_tracking_flow.py::test_run_completed_audit_event_has_cost_fields`

**Evidence command:**
```bash
pytest tests/acceptance/test_automation_budget_caps_flow.py tests/acceptance/test_cost_tracking_flow.py -v
```

**Gap note:** Parent cost caps are **not** propagated to child agents (documented gap in `docs/strategy/reflective-strategic-assessment-2026-06-06.md` line 586). The claim covers single-agent runs only until this is fixed.

**Status:** shipping (single-agent scope); child-propagation is **roadmap**

---

### C6 — audit-log

**Claim:** Every iteration, tool call, approval decision, and final result is recorded in per-run append-only JSONL with SHA-256 hash-chain and sensitive-value redaction.

**Source docs:**
- `docs/product-contract.md` line 12: "Audit-first — every iteration, tool call, approval decision, and final result is recorded in per-run JSONL."
- `docs/strategy/reflective-strategic-assessment-2026-06-06.md` line 66: "Append-only JSONL audit log with SHA-256 hash-chain | Stable"

**Acceptance tests:**
- `tests/acceptance/test_audit_chain_integrity_flow.py::test_each_audit_line_is_valid_json`
- `tests/acceptance/test_audit_chain_integrity_flow.py::test_event_ids_are_unique`
- `tests/acceptance/test_audit_chain_integrity_flow.py::test_sensitive_values_redacted_in_log`
- `tests/acceptance/test_audit_chain_integrity_flow.py::test_persisted_log_matches_memory_events`
- `tests/acceptance/test_audit_chain_integrity_flow.py::test_run_store_audit_file_permissions`

**Evidence command:**
```bash
pytest tests/acceptance/test_audit_chain_integrity_flow.py -v
teaagent audit verify  # verify hash-chain integrity on a completed run
```

**Status:** shipping

---

### C7 — run-evidence

**Claim:** Evidence bundle includes changed files, commands run, tests passed, approvals granted, denied actions, cost totals, known failures, and rollback path.

**Source docs:**
- `docs/acceptance.md` line 98: "test_run_evidence_summary_flow.py | Run evidence summary"

**Acceptance tests:**
- `tests/acceptance/test_run_evidence_summary_flow.py::test_evidence_summary_includes_all_required_fields`
- `tests/acceptance/test_run_evidence_summary_flow.py::test_evidence_summary_for_successful_run`
- `tests/acceptance/test_run_evidence_summary_flow.py::test_evidence_summary_for_failed_run`
- `tests/acceptance/test_run_evidence_summary_flow.py::test_evidence_summary_for_cancelled_run`
- `tests/acceptance/test_run_evidence_summary_flow.py::test_evidence_summary_sensitive_values_redacted`

**Evidence command:**
```bash
pytest tests/acceptance/test_run_evidence_summary_flow.py -v
teaagent runs export <run_id>  # export full evidence bundle for a run
```

**Status:** shipping

---

### C8 — undo/recovery

**Claim:** Undo journal captures pre-write workspace state; `teaagent undo --last` restores modified and new files to the pre-run baseline.

**Source docs:**
- `docs/acceptance.md` line 93: "test_run_undo_acceptance_flow.py | Reversible change recovery"
- `README.md` line 30: "Undo | ✅ `teaagent undo --last` (or git sandbox rollback)"

**Acceptance tests:**
- `tests/acceptance/test_run_undo_acceptance_flow.py::test_run_undo_restores_workspace_after_agent_writes`
- `tests/acceptance/test_agent_undo_cli_flow.py::test_agent_undo_restores_last_run_writes`

**Evidence command:**
```bash
teaagent undo --last
pytest tests/acceptance/test_run_undo_acceptance_flow.py tests/acceptance/test_agent_undo_cli_flow.py -v
```

**Status:** shipping

---

### C9 — plan/spec-gate

**Claim:** `--require-plan` binds a run to a plan artifact; `--from-plan` records plan provenance in the audit trail. High-risk runs without a plan are blocked when the gate is enabled.

**Source docs:**
- `docs/product-contract.md` line 32: "Make bounded code changes — hash-anchored edits, protected paths, optional plan binding (--from-plan, --require-plan)."
- `docs/roadmap-status.md` line 110: "SCL-P0-001 | Bind high-risk runs to a spec or plan receipt. | plan gate / runner | Complete"

**Acceptance tests:**
- `tests/acceptance/test_plan_cli_flow.py::test_plan_cli_writes_artifact`
- `tests/acceptance/test_from_plan_cli_flow.py::test_run_from_plan_records_provenance`
- `tests/acceptance/test_plan_mode_read_only_flow.py::test_read_only_plan_mode_blocks_workspace_write`

**Evidence command:**
```bash
pytest tests/acceptance/test_plan_cli_flow.py tests/acceptance/test_from_plan_cli_flow.py -v
teaagent plan "add feature X" --root .
teaagent run "add feature X" --from-plan .teaagent/plans/<id>.json
```

**Status:** shipping

---

### C10 — docs-as-control-plane

**Claim:** The docs corpus is the governance control plane. Claims in docs must correspond to verifiable test evidence. Stale docs are a governance failure, not a cosmetic issue.

**Source docs:**
- `docs/analysis/intent-reassessment-and-worklist-2026-06-11.md` line 146: "If docs are the control plane, stale evidence inside docs is not cosmetic."
- `docs/analysis/teaagent-evidence-ledger-2026-06-04.md` line 41: "the docs corpus is now a control plane. Its job is to keep state truthful, not merely detailed."

**Acceptance tests:**
- `tests/acceptance/test_docs_acceptance_count_accuracy.py::test_acceptance_doc_passed_count_matches_pytest_collect` — validates acceptance test count in docs matches reality
- `tests/acceptance/test_claim_traceability.py::test_all_top10_claims_have_acceptance_test_reference` — validates this matrix: every claim has a test reference or is explicitly labelled roadmap *(added by W12)*
- `tests/acceptance/test_claim_traceability.py::test_no_shipping_claim_lacks_test_file` — validates that no claim marked "shipping" references a non-existent test file *(added by W12)*

**Evidence command:**
```bash
pytest tests/acceptance/test_docs_acceptance_count_accuracy.py tests/acceptance/test_claim_traceability.py -v
```

**Gap:** "Stale docs = governance failure" is a design principle, not a fully automated check. The drift-detection tests enforce count accuracy and claim-file existence, but do not verify claim-text accuracy against code behavior. Full control-plane verification would require semantic cross-referencing.

**Status:** experimental (automated count and matrix checks exist; semantic drift detection is **roadmap**)

---

## H4 Policy/RBAC Coverage Declarations (ADR-0031 Criterion 2)

Machine-readable source: `h4_policy_rbac_coverage` in
[`claim-to-test-traceability.yaml`](claim-to-test-traceability.yaml).

Checker: `scripts/check_h4_coverage.py`.

Current repository workspace inventory: no enabled `.teaagent/policies/*.json`
and no `.teaagent/roles/*.json` entries. The YAML section is intentionally
empty. When a workspace has enabled H4 policies or RBAC roles, each item must
declare at least one allow-side test and one deny-side test before ADR-0031
promotion can be considered. The checker verifies declaration completeness and
test-file references only; it does not run tests or certify semantic adequacy.

---

## Gap Summary

| Claim | Gap | Needed to close |
|-------|-----|-----------------|
| C1 local-first | No negative assertion that cloud endpoint is never called | Add test asserting no remote adapter called in default mode |
| C2 provider-agnostic | Live conformance skips without env var; "14 providers" count not exercised | CI gate: provider count verified; live test opt-in documented |
| C5 cost-boundary | Child-agent budget propagation unimplemented | Implement and test `test_subagent_budget_inherits_parent_cap` |
| C10 docs-as-control-plane | Semantic drift not detected; only count + file-existence checked | Semantic claim-text extractor and cross-reference engine |

---

## How to Keep This Current

1. When adding a new product claim to any source doc, add a row to [`claim-to-test-traceability.yaml`](claim-to-test-traceability.yaml).
2. Run `pytest tests/acceptance/test_claim_traceability.py -v` to verify the matrix is self-consistent.
3. If a claim has no test, mark `status: roadmap` in the YAML — do not mark it `shipping`.
4. This matrix is referenced by `test_claim_traceability.py`; editing YAML without running the test will fail CI.
