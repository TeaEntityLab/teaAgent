# Future Roadmap, Risk, and Usability Backlog - 2026-05-31

This backlog extends the existing TeaAgent roadmap with competitor/community
feedback, local risk audits, and daily-user usability needs. It is intentionally
large so future work can be sliced into issues, milestones, acceptance tests,
and release gates.

## Goal

Make TeaAgent transparent, risk-controllable, systematic, and easy to use as a
daily agent system without diluting its product contract:

- Governance-first coding-agent harness.
- Local-first by default.
- Tool-boundary centered.
- Audit-first.
- Permission-mode enforced.
- Not a general no-code workflow framework.

## Inputs

| Input | Source |
| --- | --- |
| Product contract | `docs/product-contract.md` |
| Current acceptance catalog | `docs/acceptance.md` |
| Use-case and competitive traceability | `docs/use-cases.md`, `docs/use-case-matrix.md` |
| Maturity matrix | `docs/maturity-matrix.md` |
| Threat model | `docs/threat-model.md` |
| System transparency audit | `docs/analysis/system-transparency-risk-audit-2026-05-31.md` |
| Ecosystem daily-use gap review | `docs/analysis/agent-ecosystem-daily-use-gap-review-2026-05-31.md` |
| Competitor/community synthesis | `docs/analysis/competitor-community-feedback-synthesis-2026-05-31.md` |

## North Star

A daily user should always be able to answer these questions without reading
raw logs:

1. What is TeaAgent doing now?
2. Why is this action safe or blocked?
3. What did this run change?
4. What did it cost?
5. Which context, memory, skill, MCP tool, plugin, hook, or subagent influenced
   the result?
6. How do I recover, undo, resume, or safely stop?
7. Which known risks are accepted, mitigated, or release-blocking?

## Roadmap Horizons

| Horizon | Name | Target outcome | Exit evidence |
| --- | --- | --- | --- |
| H0 | Claim and risk hygiene | Public claims, risk register, docs gates, and tool warnings are owned. | Risk register rows have owner/status/due date, docs checks pass, warning budget is enforced. |
| H1 | Daily operator loop | Setup, daily cockpit, plan, execute, approve, verify, recover, and remember are one coherent journey. | Journey acceptance tests pass across CLI/TUI baseline. |
| H2 | Multi-surface continuity | CLI, TUI, IDE, dashboard, background, cloud, and gateway share one run-state contract. | Surface parity tests prove identity, permissions, audit, cost, and recovery continuity. |
| H3 | Ecosystem trust | MCP, plugins, skills, hooks, subagents, and automations are explainable, revocable, and testable. | Trust-onboarding and activation-explain acceptance tests pass. |
| H4 | Durable team operations | Long-running and team workflows have durable execution, control-plane views, policy, audit, and cost attribution. | Background/cloud/team lifecycle tests pass with evidence bundle export. |
| H5 | Quality and eval loop | Prompt/runtime/model changes cannot silently degrade daily outcomes. | Prompt/config eval gates, long-session tests, repo-map benchmarks, and scope-creep tests run in release profile. |
| H6 | Packaging and adoption | Desktop/client-server and external-facing release channels have supply-chain, update, and support plans. | SBOM/signing/update docs, packaged smoke tests, and onboarding metrics exist. |

## Prioritization Rules

Use this order when work competes:

1. Prevent irreversible or hidden side effects.
2. Preserve trust boundaries: tools, MCP, plugins, hooks, skills, subagents,
   automations, and background workers.
3. Improve daily recoverability before adding new orchestration power.
4. Make cost, context, and progress visible before optimizing fancy workflows.
5. Add acceptance tests before marketing a surface as stable.
6. Prefer small, reviewable vertical slices over broad rewrites.

## Milestone Plan

### M0 - Immediate Control Plane for Claims and Risk

Target: 1-2 weeks.

Outcome:
- Risk register becomes operational.
- Release claims are traceable.
- Tool lint warnings are budgeted.
- Hook/backend/MCP trust gaps have failing tests before implementation.

Exit criteria:
- `python3 scripts/validate_docs_consistency.py`
- `python3 scripts/refresh_competitive_docs.py --check`
- `teaagent tool lint --root .`
- New claim/risk validators or documented manual review checklist.

### M1 - Daily Cockpit and Evidence Summary

Target: 2-6 weeks.

Outcome:
- Daily user sees status, blockers, risk, approvals, context pressure, cost,
  recent runs, next safest command, and recovery options in one contract.
- Completed runs emit a human-sendable evidence summary.

Exit criteria:
- CLI/TUI cockpit parity acceptance.
- Run evidence summary acceptance.
- Guided recovery acceptance.

### M2 - Context, Scope, and Planning Reliability

Target: 4-10 weeks.

Outcome:
- Long sessions get context-health checks and rollover suggestions.
- Plans are hash-bound, reviewable, and comparable.
- Scope creep is measurable and blockable.

Exit criteria:
- Long-session context guard acceptance.
- Scope budget acceptance.
- Plan revision and intent-drift acceptance.

### M3 - Extension and Subagent Trust

Target: 8-14 weeks.

Outcome:
- MCP, plugins, skills, hooks, and subagents show activation reasons, trust
  source, allowed tools, cost, and disable/revoke commands.
- Subagent parent review/merge becomes a first-class workflow.

Exit criteria:
- Extension activation explain acceptance.
- MCP trust onboarding acceptance.
- Subagent review/merge and cost attribution acceptance.

### M4 - Background, Cloud, Gateway, and Team Operations

Target: 12-22 weeks.

Outcome:
- Background and cloud tasks are durable and attachable.
- Message intake becomes auditable run tickets.
- Team/control-plane views show cost, risk, status, and evidence.

Exit criteria:
- Background full lifecycle acceptance.
- Gateway task intake acceptance.
- Control-plane operator cockpit acceptance.

### M5 - Evaluation, Benchmark, and Release Quality Loop

Target: ongoing.

Outcome:
- Prompt/runtime/model/provider changes are gated.
- Repo-map quality is benchmarked.
- Release evidence bundles are reproducible.

Exit criteria:
- Prompt change regression suite.
- Repo-map benchmark corpus.
- Release evidence bundle generated in release profile.

### M6 - Desktop and Distribution Readiness

Target: after M1-M4 foundations.

Outcome:
- Desktop/client-server packaging has trust, update, rollback, session attach,
  and support paths.

Exit criteria:
- Packaged launch smoke.
- Signing/SBOM/update docs.
- Desktop session attach acceptance.

## Master Work List

### Track A - Roadmap Governance and Claim Hygiene

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| GOV-001 | Create a canonical roadmap status table with horizon, owner, status, confidence, and next gate. | Every roadmap item has exactly one owner surface and status. | Docs validator or manual release checklist. | Medium |
| GOV-002 | Add a risk-register schema for owner, status, due date, release-blocking, mitigation, and verification. | Rows missing required fields fail validation. | `test_risk_register_schema_flow.py`. | High |
| GOV-003 | Add a claim-to-evidence matrix for README, docs, maturity labels, and package metadata. | Each public claim maps to tests or an explicit known gap. | `test_public_claims_have_evidence_flow.py`. | High |
| GOV-004 | Define local, PR, main, nightly, release, and managed-runtime verification profiles. | Each profile lists required commands and risk gates. | `test_release_profile_required_gates_flow.py`. | High |
| GOV-005 | Add warning-budget ownership for `teaagent tool lint`. | Warnings are fixed or explicitly owned with expiry. | Tool lint budget check. | Medium |
| GOV-006 | Create release-channel source of truth for Alpha/Beta/Stable labels. | README, maturity matrix, and package classifier cannot drift silently. | Metadata consistency validator. | Medium |
| GOV-007 | Make competitive survey freshness a release checklist blocker. | Minor release checklist includes refreshed source dates. | Docs consistency check. | Medium |
| GOV-008 | Add "decision expiry" dates to high-impact ADRs and roadmap assumptions. | Stale assumptions are visible before release. | ADR freshness review. | Medium |
| GOV-009 | Add an issue template for roadmap tasks with acceptance, tests, risk, and human-review gate. | New tasks can be converted into issues without reformatting. | Template smoke review. | Low |
| GOV-010 | Tag backlog items by user journey: setup, plan, run, approve, verify, recover, remember, report. | Journey coverage can be summarized by script. | Backlog taxonomy check. | Low |
| GOV-011 | Create a "do not claim" list for experimental surfaces. | Docs clearly separate implemented, beta, foundation, and spec-only surfaces. | Release checklist review. | Medium |
| GOV-012 | Add release residual-risk summary generated from risk register. | Release notes include open and accepted risks. | Evidence bundle snapshot. | High |

### Track B - First-Run and Daily Usability

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| UX-001 | Define one daily cockpit JSON contract shared by CLI, TUI, dashboard, and IDE. | Same workspace returns same status fields across surfaces. | `test_daily_cockpit_parity_flow.py`. | High |
| UX-002 | Add a one-command readiness check for provider, git, workspace, shell policy, MCP, IDE, budget, and docs gates. | Output ranks blockers before warnings. | `test_daily_readiness_check_flow.py`. | Medium |
| UX-003 | Add next-safest-command recommendations to every failed setup path. | User gets an executable recovery command or a clear manual action. | Extend first-run acceptance. | Medium |
| UX-004 | Add "why this mode" guidance for read-only, workspace-write, prompt, allow, and danger-full-access. | Mode output includes blast radius, approvals, rollback, and recommended use. | `test_permission_mode_decision_guide_flow.py`. | High |
| UX-005 | Add a first-task wizard that turns vague goals into plan, risk, and acceptance checklist. | No write action occurs before plan acceptance. | `test_issue_to_plan_acceptance_flow.py`. | Medium |
| UX-006 | Add daily "stale workspace" warning for dirty git state, branch divergence, and pending approvals. | Cockpit shows state without modifying files. | Daily CLI/TUI extension. | Medium |
| UX-007 | Add "what changed since last run" summary. | User sees files, memory updates, approvals, and failed tasks since last run. | `test_recent_changes_summary_flow.py`. | Low |
| UX-008 | Add short recovery recipes directly to common error output. | Errors include category, cause, next command, and link to docs. | Error recovery acceptance. | Medium |
| UX-009 | Add "new chat/session suggested" guidance when context pressure or session age is high. | Long session shows safe rollover path and handoff bundle. | `test_context_rollover_recommendation_flow.py`. | Medium |
| UX-010 | Add no-model-call dry run for "what would TeaAgent do?" | User can inspect intended permissions, tools, budget, and plan gates. | `test_no_model_dry_run_preview_flow.py`. | Low |
| UX-011 | Add human-readable "blocked because" explanations before stack traces. | Common setup and policy failures remain actionable. | Snapshot tests for CLI output. | Medium |
| UX-012 | Add "open work" dashboard card: pending approvals, blocked runs, stale automations, and risks. | Daily output has deterministic ordering. | Dashboard parity test. | Medium |
| UX-013 | Add copy-paste safe command formatting with shell quoting. | Suggested commands work for paths with spaces. | CLI output fixture. | Low |
| UX-014 | Add "learning path" docs for developer, maintainer, security reviewer, platform engineer, and extension author. | Each persona has a 15-minute path. | Docs checklist. | Low |
| UX-015 | Add exit-code taxonomy for scripts and CI consumers. | Automation can distinguish blocked, denied, failed, partial, and success. | CLI status tests. | Medium |
| UX-016 | Add "support bundle" export for bug reports. | Bundle redacts secrets and includes version, config, run summary, and diagnostics. | `test_support_bundle_export_flow.py`. | Medium |

### Track C - Context, Session, and Memory Reliability

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| CTX-001 | Add context-health score: token pressure, stale files, old observations, memory confidence, and hidden large attachments. | Score appears in cockpit and run evidence. | `test_context_health_score_flow.py`. | Medium |
| CTX-002 | Add session rollover bundle with goal, plan hash, active files, decisions, risks, and pending approvals. | New session can resume without copying raw chat. | `test_session_rollover_bundle_flow.py`. | High |
| CTX-003 | Add stale context detector when files changed after context pack creation. | Agent warns before using old repo facts. | Extend context pack tests. | High |
| CTX-004 | Add memory review inbox for accepted, edited, rejected, expired, and pending memories. | Rejected/expired memory is never injected. | `test_memory_review_inbox_flow.py`. | Medium |
| CTX-005 | Add memory injection explain: why selected, confidence, source run, expiry, and disable path. | User can audit context influence. | Memory explain acceptance. | Medium |
| CTX-006 | Add failure-card conflict detector when old failure advice contradicts new passing evidence. | Conflicting cards are quarantined. | Failure-card invalidation test. | Medium |
| CTX-007 | Add context-pack diff between plan and execution. | Running from stale plan requires re-acceptance or warning. | `test_plan_context_diff_flow.py`. | Medium |
| CTX-008 | Add attachment provenance for images/files entering model context. | Evidence summary lists attachment names, hashes, and redaction state. | `test_attachment_provenance_flow.py`. | Medium |
| CTX-009 | Add context-size budget by source: repo map, memory, docs, attachments, chat, generated plan. | User can see which source consumes tokens. | Cost/context ledger test. | Medium |
| CTX-010 | Add compaction quality eval with before/after task-relevant facts. | Compaction preserves required recent observations. | Extend context compaction SLO. | High |
| CTX-011 | Add "context poison" quarantine for untrusted web/MCP outputs before memory persistence. | Untrusted content cannot become auto-memory without review. | Security memory acceptance. | High |
| CTX-012 | Add pinned-file expiry and stale path warnings. | Deleted/renamed pinned files are visible. | Pinned file tests. | Low |
| CTX-013 | Add repo-map freshness metrics and cache invalidation explain. | User sees index age and invalidation cause. | Repo-map quality tests. | Medium |
| CTX-014 | Add cross-session identity of tasks and plans. | Resume can show task lineage, not only run IDs. | Session continuity acceptance. | Medium |

### Track D - Planning, Scope Control, and Acceptance Design

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| PLAN-001 | Add plan revision diffs with accepted hash binding. | Execution from modified plan fails closed until re-accepted. | `test_plan_review_revision_flow.py`. | High |
| PLAN-002 | Add scope budget fields: allowed files, allowed commands, non-goals, max risk, max spend, max duration. | Run blocks actions outside scope or asks for explicit expansion. | `test_scope_budget_enforcement_flow.py`. | High |
| PLAN-003 | Add intent-drift detector comparing current action to accepted plan. | Drift is audited with approve/deny decision. | `test_intent_drift_gate_flow.py`. | High |
| PLAN-004 | Add ambiguity scoring for issue/task intake. | Missing acceptance criteria are blockers, not buried warnings. | Issue-to-plan acceptance. | Medium |
| PLAN-005 | Add user-story generator with persona, job, acceptance, tests, and risk. | Output can be converted to backlog issue. | Snapshot test. | Low |
| PLAN-006 | Add "test plan required" gate for code changes above risk threshold. | High-risk writes require linked test plan. | Plan gate tests. | High |
| PLAN-007 | Add "do not implement yet" mode for review-only plans. | The run cannot call write tools. | Plan mode read-only acceptance. | Medium |
| PLAN-008 | Add plan dependency graph for multi-step work. | Blocked steps show dependency reason. | Plan CLI tests. | Low |
| PLAN-009 | Add risk-adjusted acceptance tier mapping. | P0/P1/P2 test selection follows risk. | Risk-to-test matrix check. | Medium |
| PLAN-010 | Add plan stale-date warning for old plans. | Plans older than policy threshold require refresh. | Plan age test. | Low |
| PLAN-011 | Add plan-to-evidence trace in final summary. | Summary lists accepted plan hash and deviations. | Evidence summary tests. | Medium |
| PLAN-012 | Add "rejected alternatives" capture to reduce repeated debate. | Plans include alternatives and rejection reasons. | Docs/template review. | Low |

### Track E - Execution, Recovery, and Evidence

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| RUN-001 | Add run evidence summary for success, failure, cancellation, and pending approval. | Summary includes changed files, commands, tests, approvals, costs, and rollback. | `test_run_evidence_summary_flow.py`. | High |
| RUN-002 | Add guided recovery wizard for failed/partial runs. | User sees resume, undo, inspect, retry, or escalate options. | `test_guided_recovery_flow.py`. | High |
| RUN-003 | Add loop detector for repeated tool calls, repeated patches, repeated test failures, and stuck updates. | Run pauses or asks for new plan before looping. | `test_agent_loop_detection_flow.py`. | High |
| RUN-004 | Add safe retry classification: transient, deterministic, policy-denied, approval-needed, context-stale. | Retry path is not generic. | Error taxonomy tests. | Medium |
| RUN-005 | Add rollback availability check before risky writes. | If rollback unavailable, output says why and requires approval. | Undo acceptance extension. | High |
| RUN-006 | Add run timeline view with iterations, tool calls, approvals, waits, and heartbeats. | Timeline can be exported as JSON and human text. | Trace/export tests. | Medium |
| RUN-007 | Add "partial success" final state. | User can distinguish done, failed, cancelled, blocked, and partial. | CLI status tests. | Medium |
| RUN-008 | Add test-result parser summary for common frameworks. | Evidence summary extracts pass/fail counts when possible. | Fixture tests. | Low |
| RUN-009 | Add command timeout policy by risk and profile. | Long external commands cannot hang silently. | Backend timeout tests. | High |
| RUN-010 | Add final-answer claim checker against actual command/test output. | Agent cannot claim unrun tests as passing. | Verifier/evidence test. | High |
| RUN-011 | Add "what I did not verify" required field for final result. | Final summary never hides verification gaps. | Final report snapshot. | Medium |
| RUN-012 | Add protected path write explanation. | Denials include path rule and safe alternative. | Protected path test extension. | Medium |
| RUN-013 | Add run resume conflict detection when workspace changed after failure. | Resume warns and asks for re-plan if necessary. | Resume continuity extension. | High |
| RUN-014 | Add undo dry-run preview. | User can inspect files/patches before undo. | Undo CLI test. | Medium |
| RUN-015 | Add "artifact manifest" for plans, evidence, exports, screenshots, logs, and risk notes. | Every run can list produced artifacts. | Run store tests. | Low |
| RUN-016 | Add per-run redaction report. | User sees what was redacted and which fields were suppressed. | Audit redaction tests. | Medium |

### Track F - Subagents and Multi-Agent Workflows

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| SUB-001 | Add parent subagent review command: list child results, diffs, tests, risk, and cost. | Parent can compare without applying changes. | `test_subagent_review_merge_flow.py`. | High |
| SUB-002 | Add child patch apply/reject with conflict detection and rationale. | Reject and apply decisions are audited. | Subagent merge acceptance. | High |
| SUB-003 | Add per-child cost and token ledger. | Parent evidence summary attributes cost per child. | `test_subagent_cost_attribution_flow.py`. | Medium |
| SUB-004 | Add per-child tool scope explain. | User sees allowed and denied tools for each child. | Subagent definition tests. | Medium |
| SUB-005 | Add child run heartbeat and stale-worker detection. | Parent sees running, blocked, idle, failed, and completed states. | Team lifecycle tests. | Medium |
| SUB-006 | Add subagent "scope budget" inheritance. | Child cannot exceed parent-approved scope without escalation. | Scope budget tests. | High |
| SUB-007 | Add multi-agent output dedupe and contradiction detector. | Parent flags conflicting claims before merge. | Critic/verifier fixture. | Medium |
| SUB-008 | Add subagent memory isolation policy. | Child memory writes are pending review by default. | Memory review tests. | High |
| SUB-009 | Add subagent result quality score using tests, diff size, risk, and evidence. | Parent can rank alternatives without hiding rationale. | Tournament comparator tests. | Medium |
| SUB-010 | Add "no recursive orchestration" guard for child agents unless explicitly enabled. | Child outputs recommend handoff rather than spawning chains. | Subagent governance test. | Medium |
| SUB-011 | Add subagent cleanup/expiry for abandoned worktrees and logs. | Stale child resources are visible and removable. | Worktree cleanup test. | Low |
| SUB-012 | Add subagent prompt/config diff in evidence. | Parent can explain different child behavior. | Evidence bundle test. | Low |
| SUB-013 | Add team run cancellation propagation. | Cancelling parent marks child runs consistently. | Cancel flow extension. | High |
| SUB-014 | Add subagent UI tree parity in TUI/dashboard. | CLI/TUI/dashboard show same lineage. | Surface parity test. | Medium |

### Track G - Background, Cloud, Automation, and Durable Execution

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| BG-001 | Write background/cloud operator guide with start, detach, attach, approve, cancel, resume, export. | Guide has commands and failure paths. | Docs checklist. | Medium |
| BG-002 | Add background full lifecycle acceptance. | Run ID persists immediately and attach works after detach. | `test_background_full_lifecycle_flow.py`. | High |
| BG-003 | Add cloud/local background parity contract. | Status, permission, audit, cost, and cancellation fields align. | `test_cloud_background_parity_flow.py`. | High |
| BG-004 | Add durable execution checkpoints for long-running task steps. | Restart can resume from safe checkpoint or explain no-resume. | Managed runtime tests. | High |
| BG-005 | Add fixed endpoint/port policy for hosted workers. | Operator can expose services safely and audit port use. | Runtime network fixture. | High |
| BG-006 | Add missed-run remediation for automations. | Stale or missed automation run shows recovery choices. | Automation lifecycle acceptance. | Medium |
| BG-007 | Add automation owner, renewal, transfer, pause, resume, expire, and review states. | Lifecycle transitions are audited. | `test_automation_lifecycle_review_flow.py`. | Medium |
| BG-008 | Add automation no-op evidence. | Skipped runs explain gate reason and input hash. | Existing automation skip tests extension. | Low |
| BG-009 | Add automation skill/memory/tool allowlist parity with foreground runs. | Cron cannot access more than equivalent foreground run. | Automation parity tests. | High |
| BG-010 | Add background notification preference and escalation policy. | Users control notify channels and severity. | Notify tests. | Low |
| BG-011 | Add cloud task credential boundary guide. | Hosted tasks document auth, token storage, and revocation. | Security docs review. | High |
| BG-012 | Add background cost cap with stop/pause policy. | Cost cap triggers visible state and audit event. | Cost tracking extension. | Medium |
| BG-013 | Add background task artifact collection. | Evidence summary includes logs, patches, tests, and exported bundle. | Evidence bundle test. | Medium |
| BG-014 | Add "safe wake" gate for automations that touch external systems. | External side effects require fresh trust and scope. | Provenance gate tests. | High |

### Track H - MCP, Plugins, Skills, Hooks, and Extension Trust

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| EXT-001 | Add unified extension activation explain for MCP, skills, plugins, hooks, and memories. | Output shows source, reason, trust, cost, and disable command. | `test_extension_activation_explain_flow.py`. | High |
| EXT-002 | Add MCP trust onboarding journey. | User can inspect, trust, call, revoke, and audit remote server tools. | `test_mcp_trust_onboarding_flow.py`. | High |
| EXT-003 | Add conservative classification for unannotated remote MCP mutation-like tools. | Unknown mutation requires explicit trust profile. | Remote MCP trust tests. | High |
| EXT-004 | Add per-server MCP defaults and expiry. | Trust can expire and be renewed. | MCP trust CLI tests. | Medium |
| EXT-005 | Add MCP auth failure recovery for expired token, missing scope, revoked server, and bad resource indicator. | Errors are actionable. | MCP client tests. | Medium |
| EXT-006 | Add remote prompt/resource trust decision. | TeaAgent explicitly supports or rejects MCP prompts/resources with policy. | ADR plus acceptance. | High |
| EXT-007 | Add plugin strict mode to CI/release/managed profiles. | Unknown plugin source fails closed in strict profile. | Plugin strict tests. | High |
| EXT-008 | Add plugin capability manifest coverage report. | Every plugin tool maps to capability and trust boundary. | Tool lint extension. | Medium |
| EXT-009 | Add skill review provenance: author, source, hash, eval result, approved-by, expiry. | Skill activation can be audited. | Skill install/security tests. | Medium |
| EXT-010 | Add skill rollback command. | User can disable/revert a skill and see impacted runs. | Skill rollback test. | Medium |
| EXT-011 | Add hook mutation execution test through `ToolRegistry.execute`. | Hook arg/result mutations affect real tool calls. | Hook integration tests. | High |
| EXT-012 | Add hook audit records for veto, mutation, post-process, and error. | Hook influence is visible without leaking secrets. | Audit fixture. | High |
| EXT-013 | Add hook timeout and failure policy. | Slow hooks cannot hang tool execution silently. | Hook timeout test. | Medium |
| EXT-014 | Add duplicate/shadowed extension detector. | Conflicting skills/plugins/hooks are reported. | Extension catalog test. | Medium |
| EXT-015 | Add extension safe-mode startup. | User can boot with extensions disabled to recover. | CLI smoke test. | Medium |
| EXT-016 | Add extension marketplace trust tiers. | Catalog separates local, reviewed, signed, and unknown assets. | Catalog validator. | Medium |

### Track I - Surface Parity: CLI, TUI, IDE, Desktop, Gateway, and Dashboard

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| SURF-001 | Define shared run-state schema for all surfaces. | CLI/TUI/IDE/dashboard use same field names. | Surface contract tests. | High |
| SURF-002 | Add IDE command parity for daily, preflight, plan, run, status, approvals, evidence, and undo. | VS Code commands match CLI semantics. | `test_ide_command_parity_flow.py`. | Medium |
| SURF-003 | Add dashboard cockpit parity. | Dashboard displays same blockers, costs, approvals, and recommendations. | Dashboard parity test. | Medium |
| SURF-004 | Add desktop/client-server launch recipes. | User can start local server, attach client, and run smoke workflow. | `test_desktop_packaged_launch_flow.py`. | Medium |
| SURF-005 | Add packaged desktop smoke before claiming desktop readiness. | App can attach to workspace and run read-only daily command. | Packaged launch test. | High |
| SURF-006 | Add gateway task intake from Slack/Telegram/Discord into scoped run ticket. | Message provenance, identity, plan, and approval are recorded. | `test_gateway_task_intake_flow.py`. | High |
| SURF-007 | Add gateway ambiguity blocker. | Vague remote tasks do not run writes without clarification. | Gateway intake tests. | High |
| SURF-008 | Add browser/dashboard "open evidence bundle" route. | User can view bundle without raw filesystem knowledge. | Dashboard route test. | Low |
| SURF-009 | Add approval UX parity across CLI/TUI/dashboard/IDE. | Same approval request can be handled from any supported surface. | Approval parity test. | High |
| SURF-010 | Add attach/resume parity across CLI/TUI/IDE. | Run can be started in one surface and resumed in another. | Attach/resume tests. | Medium |
| SURF-011 | Add surface capability explain. | Each surface lists supported commands and known gaps. | Docs validator. | Low |
| SURF-012 | Add remote-client auth guide for HTTP surfaces. | Operators know token, mTLS, and reverse-proxy requirements. | Docs review. | High |
| SURF-013 | Add per-surface error rendering snapshots. | Critical errors remain readable in compact UI. | Snapshot tests. | Medium |
| SURF-014 | Add progress streaming contract. | Surfaces render the same progress event taxonomy. | Streaming tests. | Medium |
| SURF-015 | Add file/attachment handling parity. | IDE/desktop/gateway inputs preserve provenance and redaction. | Attachment tests. | Medium |
| SURF-016 | Add mobile/narrow dashboard layout QA if dashboard is user-facing. | Text does not overlap and key state remains visible. | Playwright screenshot test. | Low |

### Track J - Observability, Cost, and Operator Control

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| OBS-001 | Add operator cockpit for running, blocked, waiting, failed, stale, and completed runs. | Cockpit answers "what needs attention?" | `test_operator_cockpit_flow.py`. | High |
| OBS-002 | Add per-tool, per-agent, per-provider, and per-surface cost ledger. | Cost can be traced to source. | `test_cost_attribution_flow.py`. | Medium |
| OBS-003 | Add budget policy: warn, pause, stop, or approval-needed. | Budget action is configurable and audited. | Cost tracking extension. | Medium |
| OBS-004 | Add token contributor report for context sources. | Users can reduce token pressure deliberately. | Context ledger tests. | Low |
| OBS-005 | Add run SLO dashboard: latency, tool wait, approval wait, retries, failures, cost. | SLOs can be exported as JSON. | P0 SLO extension. | Medium |
| OBS-006 | Add OpenTelemetry profile docs and safe default config. | Operators can enable telemetry without secret leakage. | Docs and redaction tests. | Medium |
| OBS-007 | Add audit query CLI for "why allowed/denied?" | Policy decisions are explainable after the fact. | Policy denial reason tests. | High |
| OBS-008 | Add structured error taxonomy across tools, model adapters, policy, MCP, plugins, and runtime. | Errors have category, severity, recoverability, and remediation. | Error taxonomy tests. | Medium |
| OBS-009 | Add "known degraded" status for partial outages. | Provider/MCP/plugin issues appear in cockpit. | Provider fallback tests. | Medium |
| OBS-010 | Add fleet/control-plane RBAC model before shared deployment. | Operator roles and permissions are documented and tested. | Control-plane auth tests. | High |
| OBS-011 | Add tenant-level audit and cost partitioning. | Multi-tenant runs cannot leak state or cost attribution. | Tenant control-plane tests. | High |
| OBS-012 | Add evidence bundle viewer for compliance. | Bundle verifies hash chain and redaction state. | Audit export tests. | Medium |
| OBS-013 | Add "stale automation" and "stale risk" alerts. | Operator sees unattended risk/work. | Cockpit alert tests. | Medium |
| OBS-014 | Add local-only monitoring path for users avoiding cloud observability. | All core metrics can be inspected locally. | Local metrics smoke. | Low |

### Track K - Security, Privacy, Supply Chain, and Risk Controls

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| SEC-001 | Decide audit L3: implement encryption or reword privacy level. | Docs and code agree. | Audit privacy consistency test. | High |
| SEC-002 | Add encrypted audit export option if L3 remains encryption-backed. | Export can be decrypted only with configured key. | Crypto fixture. | High |
| SEC-003 | Add remote MCP restricted-resource policy. | Restricted resources require auth and trust review. | MCP auth tests. | High |
| SEC-004 | Add external backend subprocess timeout and classified error. | `cx`/`qmd` cannot hang indefinitely. | Backend timeout tests. | High |
| SEC-005 | Add root/run scoping for code-analysis graph state. | Separate roots cannot contaminate graph answers. | Graph isolation test. | High |
| SEC-006 | Add stateful-tool governance annotation. | Non-idempotent stateful tools are visible to lint/policy. | Tool lint tests. | Medium |
| SEC-007 | Add plugin/skill/MCP supply-chain SBOM for release bundles. | Release bundle lists third-party executable surfaces. | Evidence bundle test. | Medium |
| SEC-008 | Add desktop signing and update policy before packaging. | Signing, revocation, update, and rollback are documented. | Release checklist. | High |
| SEC-009 | Add dependency vulnerability scan profile and triage policy. | Critical dependency CVEs are release blockers. | CI/profile check. | Medium |
| SEC-010 | Add secret redaction regression corpus. | Common token formats are redacted without destroying debuggability. | Redaction tests. | Medium |
| SEC-011 | Add prompt-injection fixture corpus for tools, MCP, memory, and web content. | Harness blocks malicious tool intent. | Security acceptance tests. | High |
| SEC-012 | Add policy reason codes for every denial. | Denials are machine-readable and human-readable. | Policy-as-code extension. | High |
| SEC-013 | Add high-risk human review gate registry. | Risky changes list required reviewer type. | Risk validator. | Medium |
| SEC-014 | Add data-retention policy for run logs, audit, memory, automation artifacts, and support bundles. | Users can inspect and prune stored data. | Retention tests. | Medium |
| SEC-015 | Add tenant boundary tests for control plane and gateway. | One tenant cannot read another tenant's runs. | Tenant tests. | High |
| SEC-016 | Add NFS/multi-writer unsupported-mode detector. | Selftest warns when audit storage is unsafe. | Selftest fixture. | High |
| SEC-017 | Add sandbox capability matrix by platform. | Operators see what isolation is actually active. | Sandbox doctor tests. | Medium |
| SEC-018 | Add incident response runbook for compromised plugin, skill, MCP server, or release artifact. | Revocation and user notification steps are documented. | Tabletop checklist. | High |

### Track L - Evals, Benchmarks, and Regression Gates

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| EVAL-001 | Add prompt/runtime/config change eval gate. | Prompt changes cannot merge without baseline comparison. | `test_prompt_change_eval_gate_flow.py`. | High |
| EVAL-002 | Add long-session quality benchmark. | Agent performance is checked after context grows. | `test_long_session_quality_flow.py`. | High |
| EVAL-003 | Add scope-creep benchmark based on authorized vs unauthorized actions. | Overeager behavior is measured and blocked. | `test_scope_creep_guard_flow.py`. | High |
| EVAL-004 | Add repo-map benchmark corpus with target files, top-K hit rate, latency, and miss taxonomy. | Report is reproducible. | `test_repo_map_benchmark_corpus_flow.py`. | Medium |
| EVAL-005 | Add provider fallback eval for outage, schema drift, capability mismatch, and cost cap. | Fallback never silently increases risk. | `test_provider_fallback_recovery_flow.py`. | Medium |
| EVAL-006 | Add MCP malicious-server fixture. | Unknown tools and prompt-injection payloads fail closed. | MCP security tests. | High |
| EVAL-007 | Add memory poisoning eval. | Untrusted memory cannot influence future writes without review. | Memory security tests. | High |
| EVAL-008 | Add subagent merge-conflict eval. | Parent detects and reports conflict before applying child patch. | Subagent review tests. | Medium |
| EVAL-009 | Add recovery quality eval for common failures. | Recovery recommendation is specific, not generic. | Guided recovery tests. | Medium |
| EVAL-010 | Add UI snapshot tests for TUI/dashboard critical states. | Blocked/approval/cost/risk states remain readable. | Headless TUI / browser tests. | Low |
| EVAL-011 | Add release evidence bundle smoke. | Bundle includes versions, commands, test counts, risks, and artifacts. | `test_release_evidence_bundle_flow.py`. | Medium |
| EVAL-012 | Add benchmark trend storage. | Regressions are visible across releases. | Trend fixture or docs. | Low |
| EVAL-013 | Add failure replay corpus from real failed runs with redaction. | Fixed bugs become replayable regressions. | Replay acceptance. | Medium |
| EVAL-014 | Add "claim checker" eval for final reports. | Final report assertions match evidence. | Final report verifier tests. | High |

### Track M - Documentation, Community, and Adoption

| ID | Work item | Acceptance | Tests / evidence | Risk |
| --- | --- | --- | --- | --- |
| DOC-001 | Write "TeaAgent vs workflow frameworks" guide. | Users know when to use TeaAgent, LangGraph, CrewAI, or custom app logic. | Docs review. | Low |
| DOC-002 | Write background/cloud walkthrough with failure paths. | Operator can execute lifecycle end to end. | Docs smoke with commands. | Medium |
| DOC-003 | Write MCP trust onboarding tutorial. | User can connect, inspect, trust, revoke, and troubleshoot. | Docs linked to acceptance. | High |
| DOC-004 | Write extension safety guide for skills, plugins, hooks, and MCP. | Supply-chain posture is understandable. | Docs checklist. | Medium |
| DOC-005 | Write subagent review/merge guide. | Parent workflow is understandable before implementation. | Docs plus acceptance plan. | Medium |
| DOC-006 | Write cost and context optimization guide. | Users can reduce token use without unsafe shortcuts. | Docs review. | Low |
| DOC-007 | Write "recover from stuck agent" guide. | Common loops and failures have recipes. | Error recovery docs. | Medium |
| DOC-008 | Write release evidence guide for maintainers. | Maintainers know required gates and artifacts. | Release checklist. | Medium |
| DOC-009 | Add community feedback refresh checklist. | Competitor/community sources are refreshed before roadmap updates. | Docs freshness check. | Low |
| DOC-010 | Add known limitations page. | Non-goals and partial surfaces are honest. | Public claim validator. | Medium |
| DOC-011 | Add example support bundle and redaction explanation. | Users know what can be shared safely. | Docs fixture. | Low |
| DOC-012 | Add adoption metrics plan: first-run time, recovery success, stale-run rate, cost visibility, failed setup reasons. | Future roadmap can be guided by measured friction. | KPI doc. | Low |

## New User Stories

| ID | Story | Acceptance |
| --- | --- | --- |
| US-FR-001 | As a first-time user, I want one command to tell me whether my workspace is ready so I do not debug setup by reading architecture docs. | Readiness output lists blockers, warnings, next command, and no hidden model call unless requested. |
| US-DAY-001 | As a daily developer, I want a cockpit that shows run status, cost, risk, context pressure, and approvals so I can decide what to do next. | CLI and TUI show the same state for the same run store. |
| US-PLAN-001 | As a maintainer, I want every plan revision hashed and reviewable so execution cannot drift from accepted intent. | Modified plan requires re-acceptance before write tools run. |
| US-SCOPE-001 | As a maintainer, I want a scope budget so the agent cannot expand work beyond the issue. | Out-of-scope file or command requires explicit scope expansion. |
| US-RUN-001 | As a user, I want a final evidence summary so I can trust what changed. | Summary includes changed files, tests, approvals, cost, failures, and rollback. |
| US-REC-001 | As a user with a failed run, I want recovery options ranked by safety. | Recovery wizard recommends resume, undo, inspect, retry, or stop with reasons. |
| US-CTX-001 | As a long-session user, I want context rollover guidance before the session becomes slow or stale. | Rollover bundle can seed a new session with key facts and risks. |
| US-MEM-001 | As a user, I want to review auto memories before they affect future runs. | Pending memories can be accepted, edited, rejected, expired, and explained. |
| US-SUB-001 | As a maintainer, I want to compare child-agent outputs before merging. | Parent sees child diffs, tests, cost, risk, and rationale before applying. |
| US-SUB-002 | As a cost-sensitive user, I want per-child token attribution. | Child costs appear in parent cockpit and evidence summary. |
| US-BG-001 | As a user running long work, I want to detach, attach, approve, cancel, and export evidence later. | Background lifecycle preserves run identity and audit. |
| US-AUTO-001 | As an operator, I want automations to expire or renew intentionally. | Stale automations are surfaced and cannot run forever unnoticed. |
| US-MCP-001 | As a user connecting a remote MCP server, I want to inspect and trust tools before calls are allowed. | Unknown mutation-like tools require explicit trust. |
| US-EXT-001 | As a user, I want to know why a skill, hook, plugin, MCP tool, or memory activated. | Explain output shows source, reason, trust, cost, and disable path. |
| US-IDE-001 | As an IDE user, I want the same daily workflow as CLI. | IDE commands cover daily, plan, run, status, approval, evidence, and undo. |
| US-GW-001 | As a team member, I want a Slack message to become a scoped run ticket. | Gateway records identity, provenance, ambiguity, plan, approval, and audit. |
| US-OBS-001 | As an operator, I want to see all blocked and running work in one view. | Cockpit lists state, blocker, owner, cost, and next action. |
| US-SEC-001 | As a security reviewer, I want every denial to explain its reason. | Audit records include machine-readable and human-readable reason codes. |
| US-REL-001 | As a maintainer, I want release evidence bundles. | Bundle includes versions, commands, test counts, artifacts, risks, and claims. |
| US-PKG-001 | As a desktop user, I want signed packaging and rollback guidance. | Desktop release docs include signing, update, revocation, and support path. |

## New Integration and Acceptance Test Backlog

| ID | Proposed test | Purpose |
| --- | --- | --- |
| AT-001 | `test_daily_cockpit_parity_flow.py` | Prove CLI/TUI/dashboard/IDE daily state shares one contract. |
| AT-002 | `test_daily_readiness_check_flow.py` | Validate one-command readiness and next-safest-command output. |
| AT-003 | `test_permission_mode_decision_guide_flow.py` | Verify mode risk guide covers blast radius, rollback, and audit. |
| AT-004 | `test_context_health_score_flow.py` | Prove context pressure, stale context, and memory risk are visible. |
| AT-005 | `test_session_rollover_bundle_flow.py` | Prove long session handoff works without raw chat copying. |
| AT-006 | `test_memory_review_inbox_flow.py` | Verify pending memory review lifecycle. |
| AT-007 | `test_plan_review_revision_flow.py` | Verify plan hash binding and revision diff. |
| AT-008 | `test_scope_budget_enforcement_flow.py` | Block work outside authorized scope. |
| AT-009 | `test_intent_drift_gate_flow.py` | Detect action drift from accepted plan. |
| AT-010 | `test_run_evidence_summary_flow.py` | Validate final evidence summary for all terminal states. |
| AT-011 | `test_guided_recovery_flow.py` | Validate ranked recovery options. |
| AT-012 | `test_agent_loop_detection_flow.py` | Stop repeated tool/update/fix loops. |
| AT-013 | `test_subagent_review_merge_flow.py` | Validate parent review, apply, reject, and conflict path. |
| AT-014 | `test_subagent_cost_attribution_flow.py` | Attribute tokens and cost to child work. |
| AT-015 | `test_background_full_lifecycle_flow.py` | Validate detach/attach/approve/resume/cancel/export. |
| AT-016 | `test_cloud_background_parity_flow.py` | Ensure cloud/local background state parity. |
| AT-017 | `test_automation_lifecycle_review_flow.py` | Cover renew, pause, resume, transfer, expire, and explain skip. |
| AT-018 | `test_mcp_trust_onboarding_flow.py` | Cover inspect, trust, call, revoke, and expired auth. |
| AT-019 | `test_extension_activation_explain_flow.py` | Explain skills, hooks, plugins, MCP tools, and memory injection. |
| AT-020 | `test_hook_registry_execution_path_flow.py` | Ensure hook mutations affect real tool execution. |
| AT-021 | `test_ide_command_parity_flow.py` | Verify IDE daily workflow parity. |
| AT-022 | `test_desktop_packaged_launch_flow.py` | Verify packaged app launch and workspace attach. |
| AT-023 | `test_gateway_task_intake_flow.py` | Convert message into scoped auditable ticket. |
| AT-024 | `test_operator_cockpit_flow.py` | Verify operator dashboard for blocked/running/stale work. |
| AT-025 | `test_cost_attribution_flow.py` | Trace cost by provider, tool, surface, and subagent. |
| AT-026 | `test_public_claims_have_evidence_flow.py` | Prevent unsupported public maturity claims. |
| AT-027 | `test_release_profile_required_gates_flow.py` | Validate named release verification profiles. |
| AT-028 | `test_release_evidence_bundle_flow.py` | Generate reproducible release evidence. |
| AT-029 | `test_prompt_change_eval_gate_flow.py` | Prevent prompt/config regressions from merging unseen. |
| AT-030 | `test_long_session_quality_flow.py` | Measure agent quality under context pressure. |
| AT-031 | `test_scope_creep_guard_flow.py` | Measure and block overeager behavior. |
| AT-032 | `test_repo_map_benchmark_corpus_flow.py` | Benchmark top-K repo-map quality. |
| AT-033 | `test_provider_fallback_recovery_flow.py` | Ensure safe provider fallback without silent risk increase. |
| AT-034 | `test_memory_poisoning_guard_flow.py` | Prevent untrusted memory from influencing writes. |
| AT-035 | `test_remote_mcp_malicious_server_flow.py` | Fail closed on untrusted remote tool payloads. |
| AT-036 | `test_support_bundle_export_flow.py` | Redacted diagnostics for bug reports. |
| AT-037 | `test_audit_privacy_level_consistency_flow.py` | Align audit L3 wording and behavior. |
| AT-038 | `test_code_graph_root_isolation_flow.py` | Prove code-analysis graph state cannot cross roots. |
| AT-039 | `test_external_backend_timeout_flow.py` | Bound `cx`/`qmd` subprocess runtime. |
| AT-040 | `test_policy_denial_reason_code_flow.py` | Verify denial reason codes in output and audit. |

## Risk Register Extension

| ID | Risk | Mitigation | Release gate |
| --- | --- | --- | --- |
| RISK-FUT-001 | Strong component tests hide broken end-to-end daily journey. | Journey acceptance matrix and cockpit parity. | M1 |
| RISK-FUT-002 | Long sessions degrade quality or speed. | Context-health score, rollover bundle, long-session eval. | M2 |
| RISK-FUT-003 | Agent expands scope beyond user intent. | Scope budget, intent-drift gate, scope-creep benchmark. | M2 |
| RISK-FUT-004 | Subagents consume tokens invisibly. | Per-child cost ledger and parent evidence summary. | M3 |
| RISK-FUT-005 | Subagent work merges unsafe or conflicting changes. | Review/merge workflow with conflict detection. | M3 |
| RISK-FUT-006 | Background/cloud task loses state or authority context. | Durable checkpoints and cloud/local parity contract. | M4 |
| RISK-FUT-007 | Gateway tasks run unbounded prompts from messages. | Scoped run tickets and ambiguity blockers. | M4 |
| RISK-FUT-008 | Remote MCP tools understate destructive behavior. | Trust onboarding and conservative unknown-tool classification. | M3 |
| RISK-FUT-009 | Hooks/plugins/skills activate without user understanding. | Unified activation explain and safe mode. | M3 |
| RISK-FUT-010 | Prompt/runtime config changes degrade quality silently. | Prompt/config eval gate and canary profile. | M5 |
| RISK-FUT-011 | Desktop packaging introduces supply-chain risk. | Signing/SBOM/update/revocation plan before stable claim. | M6 |
| RISK-FUT-012 | Public docs overclaim maturity. | Claim-to-evidence validator and known limitations page. | M0 |
| RISK-FUT-013 | Cost caps are configured but not enforced in background/team work. | Budget action policy and per-agent ledger. | M4 |
| RISK-FUT-014 | Memory poisoning persists malicious or stale guidance. | Memory review inbox and poisoning eval. | M2 |
| RISK-FUT-015 | Audit privacy claims exceed implementation. | L3 decision and consistency tests. | M0 |
| RISK-FUT-016 | Code-analysis state leaks across workspaces. | Root/run-scoped graph state. | M0 |
| RISK-FUT-017 | External analysis tools hang runs. | Timeouts and classified errors. | M0 |
| RISK-FUT-018 | Multi-surface state divergence confuses users. | Shared run-state schema and parity tests. | M2 |
| RISK-FUT-019 | Hosted/control-plane multi-tenancy leaks data. | Tenant RBAC, partitioned audit, and tenant tests. | M4 |
| RISK-FUT-020 | Recovery advice is generic and unsafe. | Guided recovery taxonomy and rollback availability check. | M1 |
| RISK-FUT-021 | Repo-map quality looks good only on local fixtures. | External benchmark corpus and trend storage. | M5 |
| RISK-FUT-022 | Telemetry leaks secrets or pressures users into cloud-only observability. | Local metrics path and redaction tests. | M4 |
| RISK-FUT-023 | Automations continue after owner intent expires. | Renewal/expiry/owner transfer lifecycle. | M4 |
| RISK-FUT-024 | Extension revocation does not affect active runs. | Revocation semantics and active-run explain. | M3 |
| RISK-FUT-025 | Final reports claim tests passed when they were not run. | Claim checker against evidence. | M5 |

## Usability Principles

These principles should shape every roadmap item:

1. Show the next safest action before advanced options.
2. Explain risk with blast radius and rollback, not vague severity words.
3. Treat "blocked" as useful state, not failure noise.
4. Make cost and context pressure visible before the user is surprised.
5. Never force users to read raw logs for routine recovery.
6. Keep extension surfaces inspectable, revocable, and explainable.
7. Prefer shared contracts across surfaces over surface-specific behavior.
8. Make defaults conservative but escape hatches explicit.
9. Distinguish local developer convenience from release/managed-runtime safety.
10. Turn repeated user confusion into tests, docs, or CLI affordances.

## Definition of Ready for New Roadmap Items

A roadmap item is ready only when it has:

- A user or operator pain.
- A scope boundary.
- A risk rating.
- Acceptance criteria.
- Proposed test or evidence.
- Owner surface.
- Human review requirement if high-risk.
- Rollback or safe failure behavior.

## Definition of Done

A roadmap item is done only when:

- Code/docs/tests are updated as appropriate.
- Acceptance criteria are met.
- Relevant docs mention limitations and recovery paths.
- Evidence commands were run and recorded.
- New risks are added to the risk register.
- Public claims are updated or left unchanged intentionally.

## Immediate Next Work Packages

### WP-001 - Claim and Risk Control

Includes:
- GOV-002
- GOV-003
- GOV-005
- SEC-001
- SEC-004
- SEC-005
- EXT-011

Why first:
- These are correctness and trust gaps already grounded in local code/docs.

### WP-002 - Daily Cockpit and Evidence

Includes:
- UX-001
- UX-002
- RUN-001
- RUN-002
- OBS-001
- OBS-007

Why second:
- This gives users transparency before more orchestration is added.

### WP-003 - Context and Scope Discipline

Includes:
- CTX-001
- CTX-002
- PLAN-002
- PLAN-003
- EVAL-002
- EVAL-003

Why third:
- Competitor feedback repeatedly points to long-session degradation and scope
  creep as daily trust breakers.

### WP-004 - Extension and Subagent Explainability

Includes:
- EXT-001
- EXT-002
- EXT-003
- SUB-001
- SUB-002
- SUB-003

Why fourth:
- TeaAgent has the primitives; users need reviewable, safe workflows.

### WP-005 - Background, Cloud, Gateway, and Operator Lifecycle

Includes:
- BG-001
- BG-002
- BG-003
- SURF-006
- OBS-002
- OBS-010

Why fifth:
- Long-running and external-entry work should not proceed without visible state
  and authority boundaries.

## Review Cadence

| Cadence | Activity |
| --- | --- |
| Weekly | Review blocked/high-risk backlog items and update risk status. |
| Every PR | Check whether changed docs or code affect claim-to-evidence matrix. |
| Before main merge | Run P0/P1 acceptance profile and docs checks. |
| Nightly | Run full acceptance, repo-map benchmark, long-session eval, and prompt/config regression suite when available. |
| Before release | Refresh competitive/community signals, regenerate release evidence bundle, and publish residual risks. |

## Go / No-go Policy for High-Risk Work

Go only when:

- Scope is bounded.
- Approval and rollback paths exist.
- Audit evidence can be produced.
- Tests or dry-runs cover the failure mode.
- Human review gate is named when required.

No-go when:

- A remote tool, plugin, hook, or skill cannot be attributed to a trusted source.
- A destructive action lacks rollback or explicit approval.
- A public maturity claim lacks acceptance evidence.
- A background/cloud/gateway task cannot preserve identity, permissions, audit,
  and cancellation semantics.
- A desktop/client-server release lacks signing/update/revocation guidance.
