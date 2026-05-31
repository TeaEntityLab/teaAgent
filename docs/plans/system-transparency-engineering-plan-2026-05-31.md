# System Transparency Engineering Plan - 2026-05-31

This plan turns the 2026-05-31 transparency risk audit into reviewable work. The
goal is to make TeaAgent easier to inspect, safer to operate, and harder to
misrepresent through stale claims.

## North Star

TeaAgent should be able to answer four operator questions with evidence:

1. What can this run do?
2. Why was this action allowed or denied?
3. What evidence proves the stated maturity claim?
4. Which risks are open, accepted, mitigated, or release-blocking?

## Non-Goals

- Do not add a second agent framework.
- Do not add new dependencies unless a task explicitly earns that decision.
- Do not make marketing claims that are not backed by acceptance tests or
  documented operational constraints.
- Do not treat local developer convenience as the release default.

## Engineering Principles

- Prefer existing registry, policy, audit, and acceptance patterns.
- Convert hidden state into explicit state, scoped by run, root, or profile.
- Make every trust boundary visible in code, docs, and tests.
- Keep release claims generated from or checked against evidence.
- Fix small consistency failures immediately; use ADRs for architectural choices.

## Acceptance Criteria

| ID | Acceptance Criterion | Evidence |
| --- | --- | --- |
| AC-001 | `ToolRegistry.execute` applies pre-hook argument mutations and post-hook result mutations. | New acceptance or unit test fails before fix and passes after. |
| AC-002 | Hook vetoes, mutations, and post-processing decisions are auditable without leaking secrets. | Audit fixture includes hook lifecycle records. |
| AC-003 | Code-analysis graph state is scoped by workspace root or run ID. | Two-root isolation test. |
| AC-004 | Stateful non-file tools are explicitly annotated or capability-gated. | Tool lint rule or dedicated registry test. |
| AC-005 | `cx` and `qmd` backend calls have bounded timeouts. | Timeout fixture with fake slow executable. |
| AC-006 | `workspace_code_parse` validates action-specific fields before execution. | Missing-field tests return classified actionable errors. |
| AC-007 | Remote MCP tools without trusted annotations are conservative by default. | Remote MCP fixture with mutation-like tool name and missing hints. |
| AC-008 | Plugin strict mode is default for CI/release profiles. | Profile test blocks unknown plugin source. |
| AC-009 | Audit L3 privacy wording matches implementation, or encryption is implemented. | Doc/code consistency test. |
| AC-010 | Release maturity status has one canonical source. | Validator checks README, maturity matrix, and package metadata. |
| AC-011 | Docs consistency and competitive docs refresh pass locally and in CI. | `validate_docs_consistency.py` and refresh `--check`. |
| AC-012 | Tool lint warnings are either zero or tracked in a warning budget. | Tool lint report plus warning-budget check. |
| AC-013 | Public claims map to acceptance tests or explicit known gaps. | Claim-to-evidence matrix. |
| AC-014 | Risk register includes owner, status, due date, and release-blocking flag. | Machine-readable risk register or validated Markdown table. |
| AC-015 | Managed, CI, and local profiles have separate documented gates. | Verification profile table and CI jobs. |
| AC-016 | Multi-writer audit storage support is documented or tested. | ADR plus stress/probe test if supported. |
| AC-017 | Policy denials include operator-readable reason codes. | Policy acceptance tests assert reason codes. |
| AC-018 | External tooling diagnostics explain `cx` database permission failures. | CLI diagnostic test and docs. |
| AC-019 | Acceptance tiers are mapped to risk severity. | Risk-to-test matrix links P0/P1/P2 coverage. |
| AC-020 | Release candidate verification produces an evidence bundle. | Script output includes commands, versions, test counts, and artifact paths. |

## Test Matrix

| Tier | Purpose | Command |
| --- | --- | --- |
| P0 | Fast governance smoke: policy, approvals, audit, destructive guardrails. | `python3 scripts/run_acceptance_tier.py --tier p0` |
| P1 | Main-branch safety: common workflows plus governance regressions. | `python3 scripts/run_acceptance_tier.py --tier p1` |
| P2 / all | Release confidence across documented acceptance stories. | `python3 scripts/run_acceptance_tier.py --tier all` |
| Docs | Verify public claims and generated competitive docs. | `python3 scripts/refresh_competitive_docs.py --check && python3 scripts/validate_docs_consistency.py` |
| Tool governance | Verify tool metadata and registry invariants. | `teaagent tool lint --root .` |
| Collection | Verify acceptance discovery count and import health. | `python3 -m pytest tests/acceptance --collect-only -q` |

## Verification Profiles

| Profile | When | Required Gates |
| --- | --- | --- |
| Local edit | Before finishing a narrow change. | Targeted tests, docs check if docs changed, tool lint if tools changed. |
| Pull request | Every PR. | P0, docs checks, targeted tests, tool lint. |
| Main branch | After merge or scheduled run. | P0, P1, docs checks, tool lint. |
| Release candidate | Before publishing. | P0, P1, all acceptance, docs checks, tool lint, risk-register review, evidence bundle. |
| Managed runtime | Before enabling hosted or shared use. | Release candidate gates plus strict plugin profile, remote MCP trust review, audit storage review. |

## Task Plan

| ID | Task | Risk Covered | Acceptance | Tests |
| --- | --- | --- | --- | --- |
| TASK-001 | Fix `docs/use-cases.md` survey marker so docs validators pass. | RSK-002 | AC-011 | Docs checks. |
| TASK-002 | Add a failing integration test for ToolRegistry pre-hook argument mutation. | RSK-001 | AC-001 | New hook registry integration test. |
| TASK-003 | Add a failing integration test for ToolRegistry post-hook result mutation. | RSK-001 | AC-001 | New hook registry integration test. |
| TASK-004 | Wire `run_pre_hooks` and `run_post_hooks` return values through `ToolRegistry.execute`. | RSK-001 | AC-001 | Hook integration tests plus existing acceptance. |
| TASK-005 | Add audit fields for hook veto, mutation, and post-processing. | RSK-001, RSK-015 | AC-002 | Audit lifecycle fixture. |
| TASK-006 | Scope code-analysis graph state by root or run ID. | RSK-003 | AC-003 | Two-root graph isolation test. |
| TASK-007 | Decide whether stateful in-memory graph ingestion is destructive, stateful, or capability-gated. | RSK-004 | AC-004 | Tool annotation test. |
| TASK-008 | Add a registry lint rule for stateful non-idempotent tools without explicit governance. | RSK-004, RSK-010 | AC-004, AC-012 | Tool lint tests. |
| TASK-009 | Add per-action validation for `workspace_code_parse`. | RSK-006 | AC-006 | Missing `name`, `path`, `line`, and `symbol` tests. |
| TASK-010 | Add timeout config to external backend invocations. | RSK-005 | AC-005 | Fake slow executable test. |
| TASK-011 | Classify backend timeouts as actionable tool errors. | RSK-005 | AC-005 | Timeout error assertion. |
| TASK-012 | Document `cx` local database requirements and sandbox failure mode. | RSK-020 | AC-018 | Diagnostic command docs check. |
| TASK-013 | Add a `teaagent code-analysis doctor` or equivalent diagnostic path. | RSK-020 | AC-018 | CLI diagnostic test. |
| TASK-014 | Add conservative default policy for unannotated remote MCP tools. | RSK-007 | AC-007 | Remote MCP fixture test. |
| TASK-015 | Add trust profile config for remote MCP servers. | RSK-007, RSK-016 | AC-007 | Policy and config tests. |
| TASK-016 | Require explicit manifest coverage for remote tools in strict profiles. | RSK-016 | AC-007 | Manifest coverage report test. |
| TASK-017 | Decide audit L3 path: implement encryption or rename the privacy level. | RSK-008 | AC-009 | ADR plus doc/code consistency test. |
| TASK-018 | Add audit storage stress/probe for multi-writer behavior. | RSK-012 | AC-016 | Multi-process writer test or documented unsupported fixture. |
| TASK-019 | Make plugin strict mode default in CI and release profiles. | RSK-009 | AC-008 | Strict profile plugin test. |
| TASK-020 | Add release-channel status source file. | RSK-011 | AC-010 | Metadata validator. |
| TASK-021 | Validate README, maturity matrix, and package classifier against release status. | RSK-011 | AC-010 | Docs metadata test. |
| TASK-022 | Add a warning-budget file for tool lint warnings. | RSK-010 | AC-012 | Tool lint budget check. |
| TASK-023 | Convert remaining tool lint warnings into fixes or tracked exceptions. | RSK-010 | AC-012 | `teaagent tool lint --root .`. |
| TASK-024 | Create a claim-to-evidence matrix for public safety and maturity claims. | RSK-013, RSK-019 | AC-013 | Docs validator. |
| TASK-025 | Link each risk register row to owner, status, due date, and release-blocking flag. | RSK-018 | AC-014 | Risk-register validation. |
| TASK-026 | Map P0/P1/P2 acceptance tests to risk severity. | RSK-013 | AC-019 | Risk-to-test matrix check. |
| TASK-027 | Add release evidence bundle script. | RSK-017 | AC-020 | Script smoke test. |
| TASK-028 | Store command versions and test counts in the evidence bundle. | RSK-017 | AC-020 | Snapshot test. |
| TASK-029 | Add CI job or scheduled workflow for full acceptance tier. | RSK-017 | AC-015 | CI config check. |
| TASK-030 | Add ADR for managed-runtime trust boundaries. | RSK-007, RSK-009, RSK-012 | AC-015 | ADR presence check. |
| TASK-031 | Add policy denial reason codes to audit events. | RSK-015 | AC-017 | Policy denial acceptance test. |
| TASK-032 | Add operator-facing "why denied" explain command or output path. | RSK-015 | AC-017 | CLI acceptance test. |
| TASK-033 | Add docs generator guardrails for date markers and generated-matrix links. | RSK-014 | AC-011 | Generator unit test. |
| TASK-034 | Add docs pre-commit or local verification target. | RSK-002, RSK-014 | AC-011 | Make/script smoke test. |
| TASK-035 | Run release-candidate verification and publish residual risks. | All | AC-020 | Full profile gates. |

## Implementation status (2026-05-31)

| ID | Status |
| --- | --- |
| TASK-001 | Done (docs validators green) |
| TASK-002–004 | Done (`ToolRegistry.execute` + `tests/test_hooks.py`) |
| TASK-005 | Open (audit hook mutation fields) |
| TASK-006–008 | Done (per-root graph, `stateful`, lint) |
| TASK-009–011 | Done (code_parse validation, backend timeouts) |
| TASK-012–013 | Open (cx doctor CLI) |
| TASK-014–016 | Open (remote MCP trust defaults) |
| TASK-017 | Done Phase A (L3 docfix; encryption optional) |
| TASK-018–030 | Open |
| TASK-031–032 | Done (denial `reason_code`, `approval why-denied`) |
| TASK-033 | Open |
| TASK-034 | Done (`scripts/verify_docs.sh`) |
| TASK-035 | Open |

## Suggested Sequencing

### Phase 0 - Restore green documentation gates

- TASK-001
- TASK-033
- TASK-034

Exit criteria: docs consistency and competitive docs refresh pass locally.

### Phase 1 - Close high-risk execution contract gaps

- TASK-002
- TASK-003
- TASK-004
- TASK-005
- TASK-009
- TASK-010
- TASK-011

Exit criteria: hook behavior and backend failures are covered by tests and
classified errors.

### Phase 2 - Make hidden state and trust boundaries explicit

- TASK-006
- TASK-007
- TASK-008
- TASK-014
- TASK-015
- TASK-016
- TASK-031
- TASK-032

Exit criteria: stateful tools, remote MCP tools, and policy denials have visible
governance controls.

### Phase 3 - Align claims, profiles, and release evidence

- TASK-017
- TASK-019
- TASK-020
- TASK-021
- TASK-022
- TASK-023
- TASK-024
- TASK-025
- TASK-026
- TASK-027
- TASK-028
- TASK-029
- TASK-030
- TASK-035

Exit criteria: release claims have evidence, release profiles are explicit, and
accepted risks are visible.

## Risk-to-Test Backlog

| Risk | New Test Needed |
| --- | --- |
| RSK-001 | `test_tool_registry_applies_hook_mutations`. |
| RSK-003 | `test_code_graph_is_scoped_by_workspace_root`. |
| RSK-004 | `test_stateful_non_idempotent_tools_require_governance_annotation`. |
| RSK-005 | `test_external_backend_timeout_is_classified`. |
| RSK-006 | `test_workspace_code_parse_missing_action_args_are_actionable`. |
| RSK-007 | `test_remote_mcp_unannotated_mutation_requires_trust_profile`. |
| RSK-008 | `test_audit_level_privacy_claim_matches_behavior`. |
| RSK-009 | `test_release_profile_enables_plugin_strict_mode`. |
| RSK-010 | `test_tool_lint_warning_budget_is_enforced`. |
| RSK-011 | `test_release_status_metadata_is_consistent`. |
| RSK-012 | `test_audit_writer_concurrency_contract`. |
| RSK-013 | `test_public_claims_have_acceptance_evidence`. |
| RSK-014 | `test_generated_docs_markers_are_canonical`. |
| RSK-015 | `test_policy_denial_audit_includes_reason_code`. |
| RSK-016 | `test_remote_tool_manifest_coverage_report`. |
| RSK-017 | `test_release_profile_contains_required_gates`. |
| RSK-018 | `test_risk_register_rows_have_owner_status_due_date`. |
| RSK-019 | `test_claim_to_evidence_matrix_has_no_unowned_claims`. |
| RSK-020 | `test_code_analysis_doctor_reports_cx_database_issue`. |

## Definition of Done

A task is done only when:

- The code or docs change is narrow and linked to a risk ID.
- Acceptance criteria are updated or already cover the change.
- Relevant tests pass locally.
- New residual risks are added to the risk register.
- Public docs avoid claims that the tests do not support.

## Open Decisions

| Decision | Options | Recommended Path |
| --- | --- | --- |
| Audit L3 privacy | Implement encryption, or reword level. | Reword immediately, then evaluate encryption as a separate ADR. |
| Stateful graph governance | Mark destructive, add stateful annotation, or require capability gate. | Add explicit stateful annotation and root/run scoping. |
| Remote MCP unknown tools | Allow by policy mode, deny by default, or require manifest. | Require trust profile or manifest for mutation-capable unknowns. |
| Release maturity status | Keep Alpha classifier, promote classifier, or split package/product status. | Create canonical release status file before changing classifier. |
| Full acceptance cadence | Every PR, main only, nightly, release only. | P0 on PR, P1 on main/protected, all nightly and release. |

## Immediate Next PR Candidate

The smallest high-value follow-up PR should include:

1. Hook registry integration tests.
2. `ToolRegistry.execute` hook return-value wiring.
3. Docs consistency regression for the survey marker.
4. Backend action-specific validation tests for missing arguments.

This PR would close the most concrete correctness gap while keeping the change
small enough for focused review.
