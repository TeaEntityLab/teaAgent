# Agent Ecosystem Acceptance Roadmap - 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. The
> acceptance roadmap items were absorbed into the daily-driver workstreams
> (P0-A through P2-C) and the Phase 0 trust repair work. For current acceptance
> coverage, use `docs/acceptance.md`. For active work, use
> `docs/plans/ticket-plans/index.md` and
> `docs/plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md`.

**Status:** Partially implemented - See `docs/analysis/agent-ecosystem-roadmap-cross-reference-2026-05-31.md` for detailed status

**Update 2026-06-01:** P0 acceptance tests created for Issue-to-Plan Intake, Plan Review and Revision, Guided Recovery, Execution evidence summary, and Daily cockpit parity.

This roadmap expands TeaAgent's acceptance backlog from component stories into
ecosystem and daily-use journeys.

## Planning Goal

Build enough workflow, feature, integration, and acceptance coverage that a
daily user can trust TeaAgent across setup, planning, execution, approval,
background work, integrations, recovery, and reporting.

## Personas

| Persona | Job to be Done |
| --- | --- |
| Local developer | Use TeaAgent every morning to inspect, plan, edit, test, and recover in a repo. |
| Maintainer | Review PRs, update docs, triage bugs, and delegate bounded work. |
| Security reviewer | Prove what tools ran, what was approved, and what data crossed trust boundaries. |
| Platform engineer | Run MCP, IDE, cloud/background, gateway, and managed runtime surfaces safely. |
| Team lead | Understand progress, cost, risk, and evidence across multiple agent runs. |
| Extension author | Publish skills/plugins/MCP tools with governance and rollback. |

## Journey Acceptance Matrix

| Journey | Priority | Required Outcome | New Acceptance File | Status |
| --- | --- | --- | --- | --- |
| Daily cockpit parity | P0 | CLI, TUI, and dashboard expose the same core run, approval, cost, and warning state. | `test_daily_cockpit_parity_flow.py` | ✅ Acceptance test created (2026-06-01) |
| First-task from issue text | P0 | User pastes an issue, gets ambiguity score, plan artifact, safe command, and acceptance checklist. | `test_issue_to_plan_acceptance_flow.py` | ✅ Acceptance test created (2026-06-01) |
| Plan review and revision | P0 | User can compare two plan revisions before execution and bind run to the accepted plan hash. | `test_plan_review_revision_flow.py` | ✅ Acceptance test created (2026-06-01) |
| Execution evidence summary | P0 | Completed run emits changed files, tests, approvals, costs, failures, and rollback path. | `test_run_evidence_summary_flow.py` | ✅ Acceptance test created (2026-06-01) |
| Guided recovery | P0 | Failed/partial run suggests resume, undo, inspect audit, or retry with safer mode. | `test_guided_recovery_flow.py` | ✅ Acceptance test exists (2026-06-01) |
| Background attach lifecycle | P1 | User starts, detaches, receives notify, attaches, approves, resumes, cancels, and exports evidence. | `test_background_full_lifecycle_flow.py` | 🔄 Similar test exists (`test_background_attach_resume_notify_flow.py`) |
| Cloud/background parity | P1 | Cloud task and local background run preserve permission, audit, status, and cancellation semantics. | `test_cloud_background_parity_flow.py` | 📋 Not implemented |
| Slack/message intake | P1 | Gateway task becomes a scoped run ticket with provenance, approval, and audit lineage. | `test_gateway_task_intake_flow.py` | 📋 Not implemented |
| MCP trust onboarding | P1 | Remote MCP server requires trust review, scoped authorization, list, call, revoke, and audit. | `test_mcp_trust_onboarding_flow.py` | 🔄 Unit test exists (`test_mcp_trust.py`), acceptance test not yet created |
| IDE command parity | P1 | VS Code/ACP can run daily, preflight, plan, run, status, and evidence summary. | `test_ide_command_parity_flow.py` | ⏸️ Blocked (VS Code extension doesn't exist) |
| Subagent review merge | P1 | Parent compares child worktree results, applies one patch, rejects others, records rationale. | `test_subagent_review_merge_flow.py` | 🔄 Similar test exists (`test_subagent_parallel_worktree_merge_flow.py`) |
| Extension activation explain | P1 | Hooks, skills, plugins, and MCP tools show why they activated and how to disable them. | `test_extension_activation_explain_flow.py` | 📋 Not implemented |
| Provider fallback day two | P1 | Provider outage or capability mismatch yields safe fallback suggestion without silent escalation. | `test_provider_fallback_recovery_flow.py` | 📋 Not implemented |
| Memory review inbox | P1 | User can accept, edit, reject, expire, and explain auto-curated memory. | `test_memory_review_inbox_flow.py` | 🔄 Similar test exists (`test_memory_auto_curation_flow.py`) |
| Automation lifecycle | P1 | Automation can be created, dry-run, promoted, paused, resumed, renewed, expired, and explained. | `test_automation_lifecycle_review_flow.py` | 🔄 Unit test exists (`test_automation_lifecycle.py`), acceptance test not yet created |
| Risk-mode decision table | P1 | Docs and CLI explain permission-mode risk, rollback, audit, and recommended use. | `test_permission_mode_decision_guide_flow.py` | 📋 Not implemented |
| Repo-map benchmark corpus | P2 | Benchmark reports top-K target hit rate, latency, misses, and corpus metadata. | `test_repo_map_benchmark_corpus_flow.py` | 🔄 Similar test exists (`test_repo_map_quality_large_repo_flow.py`) |
| Desktop/client-server package | P2 | Packaged desktop/client-server launch can attach to a local workspace and run smoke commands. | `test_desktop_packaged_launch_flow.py` | 🔄 Similar test exists (`test_desktop_client_server_session_flow.py`) |
| Managed runtime deployment guide | P2 | Managed runtime task includes auth, audit, tool context, cancel, and evidence bundle. | `test_managed_runtime_deployment_flow.py` | 🔄 Similar test exists (`test_managed_runtime_flow.py`) |
| Workflow framework boundary | P2 | TeaAgent explains when to use external workflow frameworks and keeps governance central. | `test_workflow_framework_boundary_flow.py` | 📋 Not implemented |
| Release evidence bundle | P2 | Release candidate emits reproducible evidence bundle with tests, docs, versions, and residual risks. | `test_release_evidence_bundle_flow.py` | 📋 Not implemented |

## User Stories

### US-001: Daily Cockpit Parity

- As a local developer, I want CLI, TUI, dashboard, and IDE daily views to report
  the same readiness state so I do not make decisions from stale surface data.
- Acceptance Criteria:
  - Given the same workspace and run store, every surface reports pending
    approvals, last run status, token pressure, harness warnings, and next safest
    command.
  - JSON fields have stable names for automation.
  - Human output explains blockers before warnings.
- Tests:
  - `test_daily_cockpit_parity_flow.py`
  - Extend `test_cli_tui_surface_parity_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-002: Issue-to-Plan Intake

- As a maintainer, I want to paste a GitHub issue or support ticket and receive a
  reviewable plan, risk rating, and test checklist before any write happens.
- Acceptance Criteria:
  - Ambiguity score is included.
  - Plan artifact is saved under `.teaagent/plans/`.
  - Suggested command defaults to read-only or prompt mode.
  - Missing acceptance criteria are surfaced as blockers.
- Tests:
  - `test_issue_to_plan_acceptance_flow.py`
  - `test_plan_cli_flow.py`
- Risk: Low.
- Human Review Required: no.

### US-003: Plan Review and Revision

- As a daily user, I want to revise a plan and compare the accepted version
  before execution so that the agent does not run from outdated intent.
- Acceptance Criteria:
  - Plan revisions include content hashes.
  - `run --from-plan` records accepted hash in audit.
  - Running from a modified plan without re-acceptance fails closed.
- Tests:
  - `test_plan_review_revision_flow.py`
  - Extend `test_from_plan_cli_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-004: Run Evidence Summary

- As a user, I want every completed run to produce a concise evidence summary so
  I can trust, share, or undo the work.
- Acceptance Criteria:
  - Summary includes changed files, commands, tests, approvals, denied actions,
    costs, known failures, and rollback path.
  - Summary exists for successful, failed, cancelled, and pending-approval runs.
  - Sensitive values are redacted.
- Tests:
  - `test_run_evidence_summary_flow.py`
  - Extend `test_audit_chain_integrity_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-005: Guided Recovery

- As a user whose run failed, I want TeaAgent to tell me the safest recovery path
  rather than only showing raw logs.
- Acceptance Criteria:
  - Failure categories map to resume, undo, inspect, retry, or ask-for-approval.
  - Recovery command is copy-pasteable.
  - If rollback is unavailable, the output says why.
- Tests:
  - `test_guided_recovery_flow.py`
  - Extend `test_error_recovery_common_misuse_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-006: Background Full Lifecycle

- As a developer, I want long tasks to continue in the background while I can
  attach, inspect, approve, cancel, and export evidence later.
- Acceptance Criteria:
  - Background run records run ID immediately.
  - Attach streams latest status and logs.
  - Pending approvals can be handled after attach.
  - Cancel leaves an audit event and evidence summary.
- Tests:
  - `test_background_full_lifecycle_flow.py`
  - Extend `test_background_attach_resume_notify_flow.py`
- Risk: High.
- Human Review Required: no.

### US-007: Cloud and Local Background Parity

- As a platform engineer, I want cloud task lifecycle semantics to match local
  background runs so users do not learn two safety models.
- Acceptance Criteria:
  - Submit/list/show/cancel/status fields align.
  - Permission mode, audit correlation, and tool context are preserved.
  - Cancellation and failure reasons use shared taxonomy.
- Tests:
  - `test_cloud_background_parity_flow.py`
  - Extend `test_managed_runtime_cloud_task_flow.py`
- Risk: High.
- Human Review Required: yes for hosted deployment.

### US-008: Gateway Task Intake

- As a team member, I want a Slack or Telegram message to become a scoped,
  auditable run ticket rather than an unbounded prompt.
- Acceptance Criteria:
  - Message provenance is recorded.
  - User identity maps to allowed workspace/tenant.
  - Ambiguity and risk checks run before execution.
  - Destructive actions require approval.
- Tests:
  - `test_gateway_task_intake_flow.py`
  - Extend `test_messaging_gateway_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-009: MCP Trust Onboarding

- As a user connecting remote MCP tools, I want a trust review flow before tools
  become callable.
- Acceptance Criteria:
  - Server identity, transport, auth mode, tools, annotations, and unknown risks
    are shown before trust.
  - Revoking trust disables calls.
  - Missing or expired auth produces actionable recovery.
  - Unannotated mutation-like tools require explicit allow.
- Tests:
  - `test_mcp_trust_onboarding_flow.py`
  - Extend `test_remote_mcp_consumption_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-010: IDE Command Parity

- As an IDE user, I want the extension/ACP surface to run the same safe daily
  workflows as CLI.
- Acceptance Criteria:
  - IDE can trigger daily, preflight, plan, run, status, and evidence summary.
  - Permission mode enum matches CLI.
  - Progress and approval events stream back to the IDE.
- Tests:
  - `test_ide_command_parity_flow.py`
  - Extend `test_vscode_mcp_runtime_smoke_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-011: Subagent Review and Merge

- As a maintainer, I want to delegate multiple approaches and then review, apply,
  or reject child work safely.
- Acceptance Criteria:
  - Parent sees child lineage, diff, tests, and summary.
  - Applying a child patch checks conflicts first.
  - Rejected child outputs remain auditable.
  - Merge rationale is recorded.
- Tests:
  - `test_subagent_review_merge_flow.py`
  - Extend `test_subagent_parallel_worktree_merge_flow.py`
- Risk: High.
- Human Review Required: no.

### US-012: Extension Activation Explain

- As a user, I want to know which skills, hooks, plugins, and MCP tools activated
  for a run.
- Acceptance Criteria:
  - Explain output shows source path, load reason, trust status, token cost, and
    disable command.
  - Duplicate/shadowed extensions are reported.
  - Disabled extensions leave audit evidence.
- Tests:
  - `test_extension_activation_explain_flow.py`
  - Extend `test_skill_activation_explain_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-013: Provider Fallback Recovery

- As a user, I want provider outages and capability mismatches to result in safe
  fallback suggestions, not silent behavior changes.
- Acceptance Criteria:
  - Failed provider health check reports reason and suggested alternatives.
  - Fallback preserves permission mode and budget caps.
  - Higher-risk model/provider changes require explicit confirmation.
- Tests:
  - `test_provider_fallback_recovery_flow.py`
  - Extend `test_model_smoke_gating_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-014: Memory Review Inbox

- As a user, I want to approve, edit, or reject auto-curated memories before they
  influence future runs.
- Acceptance Criteria:
  - New memories can enter pending review state.
  - Accepted memories are searchable.
  - Rejected or expired memories are not injected.
  - Explain output shows why a memory was selected.
- Tests:
  - `test_memory_review_inbox_flow.py`
  - Extend `test_memory_auto_curation_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-015: Automation Lifecycle Review

- As an operator, I want recurring automations to have lifecycle controls and
  renewal review so stale tasks do not run forever.
- Acceptance Criteria:
  - Automation has owner, status, due/expiry, last run, next run, and risk mode.
  - Pause/resume/renew/expire/promote all write audit events.
  - Skipped runs explain unchanged inputs or gate reasons.
- Tests:
  - `test_automation_lifecycle_review_flow.py`
  - Extend `test_automation_status_observability_flow.py`
- Risk: High.
- Human Review Required: yes for production automation.

### US-016: Permission Mode Decision Guide

- As a new user, I want TeaAgent to explain which permission mode fits my task.
- Acceptance Criteria:
  - CLI guide maps read-only/workspace-write/prompt/allow/danger-full-access to
    use cases, risks, approval behavior, rollback, and audit.
  - Docs and CLI output use the same wording.
  - Dangerous modes always include safer alternatives.
- Tests:
  - `test_permission_mode_decision_guide_flow.py`
  - Extend `test_policy_as_code_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-017: Repo-Map Benchmark Corpus

- As a maintainer, I want repo-map quality measured on representative tasks so
  context packing improvements are not anecdotal.
- Acceptance Criteria:
  - Corpus includes fixture repos, target files, query prompts, and expected
    top-K matches.
  - Report includes hit rate, latency, misses, and regression threshold.
  - CI/nightly can run without network.
- Tests:
  - `test_repo_map_benchmark_corpus_flow.py`
  - Extend `test_repo_map_quality_large_repo_flow.py`
- Risk: Low.
- Human Review Required: no.

### US-018: Desktop/Client-Server Packaged Launch

- As a desktop user, I want a packaged client-server launch path rather than
  stitching together MCP HTTP commands manually.
- Acceptance Criteria:
  - Launch starts local server bound to loopback by default.
  - Client can initialize, list tools, run daily/preflight, close session.
  - External bind requires explicit auth and docs.
- Tests:
  - `test_desktop_packaged_launch_flow.py`
  - Extend `test_desktop_client_server_session_flow.py`
- Risk: High.
- Human Review Required: yes before external exposure.

### US-019: Managed Runtime Deployment

- As a platform engineer, I want a managed runtime guide that makes hosted runs
  safe to operate.
- Acceptance Criteria:
  - Deployment guide covers auth, tenant, audit, tool context, cancel, quotas,
    secrets, and evidence export.
  - Stub and real adapters share status schema.
  - Missing provider SDK gives actionable error.
- Tests:
  - `test_managed_runtime_deployment_flow.py`
  - Extend `test_managed_runtime_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-020: Workflow Framework Boundary

- As an architect, I want to know when TeaAgent should orchestrate work directly
  and when an external workflow framework should own domain logic.
- Acceptance Criteria:
  - Docs compare TeaAgent harness, LangGraph-style durable graph, and
    CrewAI-style crews/flows.
  - TeaAgent remains responsible for tool governance, approvals, audit, and run
    evidence.
  - No new framework dependency is added without ADR.
- Tests:
  - `test_workflow_framework_boundary_flow.py`
  - Docs validator for product contract non-goals.
- Risk: Medium.
- Human Review Required: yes for dependency adoption.

### US-021: Release Evidence Bundle

- As a release owner, I want one reproducible artifact proving what was tested,
  what changed, and which risks remain.
- Acceptance Criteria:
  - Bundle includes command versions, acceptance counts, docs checks, tool lint,
    risk register, maturity claims, and residual known failures.
  - Bundle is signed or hash-addressed.
  - Release checklist links to the generated bundle.
- Tests:
  - `test_release_evidence_bundle_flow.py`
  - Extend `test_docs_acceptance_count_accuracy.py`
- Risk: Medium.
- Human Review Required: yes.

### US-022: PR Review and Patch Submission

- As a maintainer, I want TeaAgent to review a PR, suggest fixes, run tests, and
  prepare a patch without bypassing human approval.
- Acceptance Criteria:
  - PR metadata and diff are ingested read-only first.
  - Suggested patch requires plan binding.
  - Review summary separates findings, tests, and residual risk.
  - No push occurs without explicit user action.
- Tests:
  - `test_github_pr_review_patch_flow.py`
  - Extend `test_github_integration_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-023: Dependency Incident Audit

- As a security reviewer, I want TeaAgent to turn a dependency advisory into a
  safe audit plan and patch proposal.
- Acceptance Criteria:
  - Advisory source is recorded.
  - Impacted files and lockfiles are identified.
  - Patch plan includes tests and rollback.
  - Network calls are explicit and auditable.
- Tests:
  - `test_dependency_incident_audit_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-024: Documentation Upkeep Automation

- As a maintainer, I want docs to update only when evidence changes.
- Acceptance Criteria:
  - Generated docs checks detect drift.
  - Proposed docs changes cite source command output.
  - No acceptance count is hand-edited without collection evidence.
- Tests:
  - `test_docs_upkeep_automation_flow.py`
  - Extend `test_docs_acceptance_count_accuracy.py`
- Risk: Medium.
- Human Review Required: no.

### US-025: Multimodal / Visual Task Intake

- As a UI developer, I want to provide screenshots or visual references and get a
  bounded implementation plan with visual verification.
- Acceptance Criteria:
  - Image inputs are recorded as artifacts.
  - Plan includes visual acceptance criteria.
  - Browser screenshot verification is required before done.
- Tests:
  - `test_visual_task_intake_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-026: Cost and Budget Forecast

- As a daily user, I want to know the estimated cost and token risk before a
  task starts.
- Acceptance Criteria:
  - Daily/preflight show cost estimate, caps, and pressure.
  - Run refuses or asks before exceeding caps.
  - Completion summary includes actual vs estimated cost.
- Tests:
  - `test_cost_budget_forecast_flow.py`
  - Extend `test_cost_tracking_flow.py`
- Risk: Medium.
- Human Review Required: no.

### US-027: Tenant-Aware Gateway Run

- As a platform engineer, I want gateway-triggered tasks to preserve tenant
  identity through run, approval, audit, and webhook.
- Acceptance Criteria:
  - Tenant is resolved before execution.
  - Tenant mismatch denies tool access.
  - Audit and status include tenant ID.
- Tests:
  - `test_tenant_gateway_run_flow.py`
  - Extend `test_messaging_gateway_flow.py`
- Risk: High.
- Human Review Required: yes.

### US-028: Tool Capability Manifest Coverage

- As an extension author, I want every tool to have a manifest that describes
  risk, inputs, outputs, state effects, and trust assumptions.
- Acceptance Criteria:
  - Tool lint reports missing capability fields.
  - Remote MCP tools require imported or reviewed capability metadata.
  - Manifest changes are diffable.
- Tests:
  - `test_tool_capability_manifest_coverage_flow.py`
  - Extend `test_external_tool_manifest_compatibility_flow.py`
- Risk: High.
- Human Review Required: yes for remote tools.

### US-029: Run Comparison

- As a maintainer, I want to compare two runs to see which tools, files, costs,
  and tests differed.
- Acceptance Criteria:
  - Compare output handles successful, failed, and cancelled runs.
  - Differences include model/provider, prompt hash, tools, approvals, files,
    tests, and final result.
  - Sensitive values are redacted.
- Tests:
  - `test_run_compare_flow.py`
- Risk: Low.
- Human Review Required: no.

### US-030: Safe Cleanup / Deslop Workflow

- As a maintainer, I want cleanup work to require regression coverage and small
  reversible slices.
- Acceptance Criteria:
  - Cleanup plan lists smells, protected behavior, tests, and rollback.
  - No new dependency is allowed without explicit approval.
  - Completion summary proves tests before and after.
- Tests:
  - `test_cleanup_workflow_acceptance_flow.py`
- Risk: Medium.
- Human Review Required: no.

## Integration Test Backlog

| ID | Integration Test | Purpose |
| --- | --- | --- |
| IT-001 | `test_daily_cockpit_state_contract.py` | Shared state object across CLI/TUI/dashboard/IDE. |
| IT-002 | `test_plan_hash_binding.py` | Plan artifact hash binding and stale-plan rejection. |
| IT-003 | `test_run_evidence_builder.py` | Evidence summary builder over audit/run store. |
| IT-004 | `test_background_status_stream.py` | Background stream and attach state transitions. |
| IT-005 | `test_cloud_local_status_schema.py` | Cloud/local lifecycle schema parity. |
| IT-006 | `test_gateway_provenance_to_run.py` | Message provenance to run audit lineage. |
| IT-007 | `test_mcp_trust_revocation.py` | Revoked trust denies calls. |
| IT-008 | `test_mcp_oauth_error_recovery.py` | Expired or missing token produces actionable error. |
| IT-009 | `test_ide_progress_events.py` | ACP/VS Code progress event parity. |
| IT-010 | `test_subagent_patch_apply_conflict.py` | Parent review patch apply and conflict detection. |
| IT-011 | `test_extension_activation_graph.py` | Hooks/skills/plugins/MCP activation provenance graph. |
| IT-012 | `test_provider_fallback_policy.py` | Fallback preserves policy and budget. |
| IT-013 | `test_memory_pending_review.py` | Pending memory is not injected until accepted. |
| IT-014 | `test_automation_expiry.py` | Expired automation will not run. |
| IT-015 | `test_permission_guide_docs_sync.py` | CLI and docs permission guidance consistency. |
| IT-016 | `test_repo_map_benchmark_report.py` | Benchmark report schema and thresholds. |
| IT-017 | `test_desktop_loopback_auth.py` | Desktop server default loopback and auth behavior. |
| IT-018 | `test_managed_runtime_status_contract.py` | Managed status schema and cancel semantics. |
| IT-019 | `test_workflow_boundary_docs_sync.py` | Product contract non-goal consistency. |
| IT-020 | `test_release_bundle_integrity.py` | Evidence bundle hash/signature verification. |

## Feature Backlog

| ID | Feature | Priority | Acceptance Link |
| --- | --- | --- | --- |
| FEAT-001 | Unified cockpit state contract. | P0 | US-001 |
| FEAT-002 | Plan revision and diff CLI. | P0 | US-003 |
| FEAT-003 | Run evidence summary generator. | P0 | US-004 |
| FEAT-004 | Guided recovery command. | P0 | US-005 |
| FEAT-005 | Background full lifecycle UX. | P1 | US-006 |
| FEAT-006 | Cloud/local status schema parity. | P1 | US-007 |
| FEAT-007 | Gateway run ticket intake. | P1 | US-008 |
| FEAT-008 | MCP trust onboarding wizard. | P1 | US-009 |
| FEAT-009 | IDE command parity adapter. | P1 | US-010 |
| FEAT-010 | Subagent review/merge CLI. | P1 | US-011 |
| FEAT-011 | Extension activation explain graph. | P1 | US-012 |
| FEAT-012 | Provider fallback advisor. | P1 | US-013 |
| FEAT-013 | Memory review inbox. | P1 | US-014 |
| FEAT-014 | Automation lifecycle review. | P1 | US-015 |
| FEAT-015 | Permission mode advisor. | P1 | US-016 |
| FEAT-016 | Repo-map benchmark corpus and report. | P2 | US-017 |
| FEAT-017 | Desktop packaged launch recipe or app shell. | P2 | US-018 |
| FEAT-018 | Managed runtime deployment playbook. | P2 | US-019 |
| FEAT-019 | Workflow framework boundary guide. | P2 | US-020 |
| FEAT-020 | Release evidence bundle generator. | P2 | US-021 |
| FEAT-021 | PR review/patch workflow. | P1 | US-022 |
| FEAT-022 | Dependency incident audit workflow. | P1 | US-023 |
| FEAT-023 | Documentation upkeep automation. | P1 | US-024 |
| FEAT-024 | Multimodal/visual task intake. | P2 | US-025 |
| FEAT-025 | Cost and budget forecast. | P1 | US-026 |
| FEAT-026 | Tenant-aware gateway run flow. | P1 | US-027 |
| FEAT-027 | Tool capability manifest coverage. | P1 | US-028 |
| FEAT-028 | Run comparison command. | P2 | US-029 |
| FEAT-029 | Safe cleanup/deslop workflow. | P1 | US-030 |

## Recommended Implementation Phases

### Phase 1 - Daily Confidence Core

- US-001 Daily cockpit parity
- US-002 Issue-to-plan intake
- US-003 Plan review and revision
- US-004 Run evidence summary
- US-005 Guided recovery
- US-016 Permission mode decision guide

Exit criteria: a new user can start the day, plan work, execute safely, and
understand completion or failure without reading subsystem docs.

### Phase 2 - Long-Running and Cross-Surface Work

- US-006 Background full lifecycle
- US-007 Cloud/local background parity
- US-010 IDE command parity
- US-018 Desktop/client-server packaged launch
- US-026 Cost and budget forecast
- US-029 Run comparison

Exit criteria: local, IDE, desktop, background, and cloud paths share status,
approval, evidence, and recovery semantics.

### Phase 3 - Ecosystem Trust and Extension Governance

- US-008 Gateway task intake
- US-009 MCP trust onboarding
- US-012 Extension activation explain
- US-013 Provider fallback recovery
- US-014 Memory review inbox
- US-015 Automation lifecycle review
- US-027 Tenant-aware gateway run
- US-028 Tool capability manifest coverage

Exit criteria: external inputs, remote tools, automations, memory, and
extensions are explainable and revocable.

### Phase 4 - Quality, Release, and Strategic Positioning

- US-017 Repo-map benchmark corpus
- US-019 Managed runtime deployment
- US-020 Workflow framework boundary
- US-021 Release evidence bundle
- US-022 PR review/patch workflow
- US-023 Dependency incident audit
- US-024 Documentation upkeep automation
- US-025 Multimodal/visual task intake
- US-030 Safe cleanup/deslop workflow

Exit criteria: TeaAgent can make credible ecosystem claims with benchmark,
release, and workflow-boundary evidence.

## Definition of Ready for Each Story

- User and surface are named.
- Permission mode is explicit.
- Trust boundary is named.
- Success and failure path are both testable.
- Audit event expectations are listed.
- Rollback or recovery path is listed.
- Existing acceptance coverage is referenced.

## Definition of Done for Each Story

- Acceptance test added or extended.
- Integration test added for cross-component behavior.
- Docs updated in `README.md`, `docs/USAGE.md`, `docs/acceptance.md`, or
  `docs/use-cases.md` when user-visible.
- Risk and maturity status updated if the story changes release posture.
- `python3 scripts/refresh_competitive_docs.py --check` passes when acceptance
  docs are touched.

## Claim Guardrails

Do not claim a capability is productized unless:

- There is a documented user journey.
- There is a CLI/API/IDE entry point.
- There is at least one acceptance or integration test.
- Failure and recovery behavior are documented.
- Permissions, audit, and rollback are covered for mutating work.
