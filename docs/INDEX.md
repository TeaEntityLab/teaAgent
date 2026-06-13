# TeaAgent Documentation Index
# 2026-06-06

> **Last reviewed:** 2026-06-06
> **Review trigger:** New front-door docs, supersession links, or validation command changes.

This is the curated front door for TeaAgent documentation. It is intentionally
not an exhaustive file list. Use it to find the current source of truth, then
follow dated evidence documents only when you need the reasoning trail.

## Start Here

| Need | Start here | Status rule |
| --- | --- | --- |
| What can the owner-operator trust today? | [Daily-Driver Current Status](daily-driver-current-status.md) | Current truth for owner-operated daily use; update whenever TUI, chat, agent mode, approval, cost, undo, or resume behavior changes. |
| What is the current documentation-state assessment? | [Documentation State Review](analysis/documentation-state-review-2026-06-04.md) | Current dated evidence for corpus shape, drift risks, and consolidation priorities. |
| What is the documentation operating model? | [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md) | Governance rulebook for claim types, TTL, owners, supersession, and CI guard targets. |
| What should be done next? | [Work Direction Execution Index](plans/work-direction-execution-index-2026-06-10.md) | Sprint 1 truth pass (WDA-001, WDB-001, WDB-003, WDG-001/002) after the June 10 critical review. |
| How should ADR 0032 M1-M6 be executed? | [ADR 0032 M1-M6 Work Plan](plans/adr-0032-m1-m6-work-plan-2026-06-13.md) | Event-spine migration plan for audit, receipts/evidence, gates, hooks, ContextBus, and webhooks. |
| Documentation corpus optimization | [Documentation Optimization Master Plan](plans/documentation-optimization-master-plan-2026-06-04.md) | Execution plan for reducing drift and improving discoverability. |
| What are the concrete work items? | [Documentation Optimization Work Items](work-log/documentation-optimization-work-items-2026-06-04.md) | Task ledger with priority, status, dependencies, and acceptance criteria. |
| Exhaustive docs inventory (generated) | [Docs Inventory](generated/docs-inventory.md) | Deterministic catalog; not current truth — use this index table first. |
| Documentation aging dashboard (generated) | [Docs Aging Dashboard](generated/docs-aging-dashboard.md) | Current-truth review freshness grouped by owner surface. |
| Command snippet inventory (generated) | [Command Snippet Inventory](generated/command-snippet-inventory.md) | Guide command coverage vs smoke/manual registry. |

## Status vocabulary

Active indexes and work-item ledgers use the canonical states in
[Document State Model](governance/document-state-model.md). When updating a
ledger row, map legacy labels instead of introducing new synonyms:

| Legacy label | Canonical state |
| --- | --- |
| OPEN | Active |
| DONE / Complete / Closed | Fixed |
| Pending | Proposed |
| In Progress | Active |
| PARTIAL | Partially fixed |
| Stale | Superseded |

Roadmap tables may keep horizon-specific wording (`In Progress`, `Pending`) but
governance ledgers should prefer the canonical set above.

## Current Truth

| Question | Canonical source |
| --- | --- |
| Current owner-operated daily behavior | [Daily-Driver Current Status](daily-driver-current-status.md) |
| Acceptance flow inventory | [Acceptance Coverage](acceptance.md) |
| Roadmap state | [Roadmap Status](roadmap-status.md) |
| Ticket execution order for current harness work | [Ticket Execution Plans](plans/ticket-plans/index.md) |
| Work direction Sprint 1 tickets | [Work Direction Execution Index](plans/work-direction-execution-index-2026-06-10.md) |
| Module ownership and inspection paths | [Module Documentation Index](modules/INDEX.md) |
| Release gates | [Release Checklist](release-checklist.md) and [Daily-Driver Release Gates](governance/daily-driver-release-gates-2026-06-02.md) |
| Permission and approval behavior | [Permission And Approval Playbook](permission-and-approval-playbook.md) |
| Operator trust model | [Operator Trust Model](operator-trust-model.md) |
| Owner friction intake | [Operator Friction Log](work-log/operator-friction-log.md) |

## Evidence And Review

| Topic | Evidence package |
| --- | --- |
| **June 12 reflective intent critical review** | [Intent Critical Review and Worklist 2026-06-12](analysis/intent-critical-review-and-worklist-2026-06-12.md) |
| **June 10 system critical review package (current)** | [System Critical Review Package 2026-06-10](analysis/system-critical-review-2026-06-10-INDEX.md) |
| June 10 engineering critique refresh | [Engineering Architecture Critique Refresh](analysis/engineering-critique-refresh-2026-06-10.md) |
| June 10 remote multi-agent readiness refresh | [Remote Multi-Agent Readiness Refresh](analysis/remote-multi-agent-readiness-refresh-2026-06-10.md) |
| June 10 conversation experience refresh | [General-User Conversation Experience Refresh](analysis/conversation-experience-refresh-2026-06-10.md) |
| June 10 competitor analyses vs self consolidation | [Competitor Analyses vs Self Consolidation](analysis/competitor-analyses-vs-self-consolidation-2026-06-10.md) |
| June 10 public reasoning ledger | [System Review Reasoning Ledger 2026-06-10](analysis/system-review-reasoning-ledger-2026-06-10.md) |
| June 10 work direction decomposition | [Work Direction Decomposition](plans/work-direction-decomposition-2026-06-10.md) |
| June 4 project-state fact check | [Project State Cross-Review Fact Check](analysis/project-state-cross-review-fact-check-2026-06-04.md) |
| June 4 total review | [Total Review Index](analysis/total-review-2026-06-04-INDEX.md) |
| June 4 documentation critique | [Documentation Critical Questioning](reviews/documentation-critical-questioning-2026-06-04.md) |
| June 1 daily-driver review package | [Daily-Driver Review Package Index](analysis/daily-driver-review-INDEX-2026-06-01.md) |
| Active daily-driver finding closure | [Active Findings Status Ledger](analysis/active-findings-status-ledger-2026-06-06.md) |
| Markdown governance review | [Markdown Status Review](analysis/markdown-status-review-2026-06-02.md) |
| Competitor signal survey | [Competitor Signal Survey](analysis/competitor-signal-survey-2026-06-06.md) (June 4 snapshot: [2026-06-04](analysis/competitor-signal-survey-2026-06-04.md)) |
| Product principles | [TeaAgent Product Principles](strategy/teaagent-product-principles-2026-06-04.md) |
| Dynamic skill and long-result audit | [Dynamic Skill Generation And Long Result Audit](analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md) |
| RSS dynamic skill failure case study | [RSS Dynamic Skill Failure Case Study](analysis/rss-failure-case-study-2026-06-05.md) |
| Agent ecosystem core values | [Agent Ecosystem Core Values](strategy/agent-ecosystem-core-values-2026-06-05.md) |
| Dynamic skill critical questioning | [Dynamic Skill Critical Questioning](reviews/dynamic-skill-critical-questioning-2026-06-05.md) |
| Seven control loops competitor survey | [Seven Control Loops Competitor Survey](analysis/seven-control-loops-competitor-survey-2026-06-05.md) |
| Seven control loops product direction | [Seven Control Loops Product Direction](strategy/seven-control-loops-product-direction-2026-06-05.md) |
| Seven control loops critical questioning | [Seven Control Loops Critical Questioning](reviews/seven-control-loops-critical-questioning-2026-06-05.md) |
| Community agent pain points | [Community Agent Pain Points Survey](analysis/community-agent-pain-points-survey-2026-06-05.md) |
| June 6 system critical review package | [System Critical Review Package](analysis/system-critical-review-2026-06-06-INDEX.md) |
| June 6 source-backed competitor self-comparison | [Competitor Self-Comparison Matrix](analysis/competitor-self-comparison-matrix-2026-06-06.md) |
| June 6 competitive claim hygiene | [Competitive Claim Audit](analysis/competitive-claim-audit-2026-06-06.md) |
| June 6 public reasoning ledger | [System Review Reasoning Ledger](analysis/system-review-reasoning-ledger-2026-06-06.md) |
| June 6 critical-question map | [System Interrogation Map](analysis/system-interrogation-map-2026-06-06.md) |
| June 6 engineering architecture critique | [Engineering Architecture Critique](analysis/engineering-architecture-critique-2026-06-06.md) |
| June 6 multi-agent coordination critique | [Multi-Agent Coordination Critique](analysis/multi-agent-coordination-critique-2026-06-06.md) |
| June 6 conversation UX analysis | [User Experience And Conversation Patterns](analysis/user-experience-and-conversation-patterns-2026-06-06.md) |
| June 6 risk and trust model critique | [Risk And Trust Model Critique](analysis/risk-and-trust-model-critique-2026-06-06.md) |
| Phase 0-to-1 outlook | [Phase 0 To Phase 1 Outlook](strategy/phase-0-to-phase-1-outlook-2026-06-04.md) |
| Malleable governed agent harness | [Malleable Governed Agent Harness](strategy/malleable-governed-agent-harness-2026-06-03.md) |
| Historical daily-driver roadmap rationale | [Daily-Driver Roadmap Rationale](strategy/daily-driver-roadmap-rationale-2026-06-04.md) |
| Historical daily-driver critique and counterarguments | [Daily-Driver Critique And Counterarguments](reviews/daily-driver-critique-and-counterarguments-2026-06-04.md) |
| Historical daily-driver docs package review | [Daily-Driver Docs Package Review](reviews/daily-driver-docs-package-review-2026-06-02.md) |
| Historical daily-driver red-team review | [Daily-Driver Red Team Review](reviews/daily-driver-red-team-review-2026-06-02.md) |

## Processes

| Process | Document |
|---|---|
| Signal-to-acceptance-gap conversion | [Signal To Acceptance Gap](processes/signal-to-acceptance-gap.md) |
| Competitor gap watch | [OpenCode Gap Watch](processes/opencode-gap-watch.md) |
| Community presence and dev-rel | [Community Presence](processes/community-presence.md) |
| Post-fix re-audit | [Postfix Reaudit Process](processes/postfix-reaudit-process.md) |
| Owner-operated daily verification | [Daily-Driver Verification](processes/daily-driver-verification.md) |
| Owner-operated manual QA smoke | [Daily-Driver Manual QA Smoke](processes/daily-driver-manual-qa-smoke.md) |
| Quarterly competitor refresh | [Quarterly Competitor Refresh Process](processes/quarterly-competitor-refresh.md) · [Release Checklist](release-checklist.md) |
| Trust and audit whitepaper | [Trust and Audit Whitepaper](governance/trust-and-audit-whitepaper.md) |
| When not to use TeaAgent | [When Not to Use TeaAgent](guides/when-not-to-use-teaagent.md) |

## Governance

| Rule surface | Purpose |
| --- | --- |
| [Governance Index](governance/README.md) | Standards and process entry point. |
| [Document State Model](governance/document-state-model.md) | Canonical state vocabulary for findings, risks, issues, tickets, and roadmap rows. |
| [Risk Issue Roadmap Workflow](governance/risk-issue-roadmap-workflow.md) | Pipeline from finding to issue, ticket, roadmap, verification, and supersession. |
| [Documentation Taxonomy And Ownership](governance/doc-taxonomy-and-ownership.md) | Where each document type belongs and who owns it. |
| [Documentation Maintenance Policy](governance/doc-maintenance-policy-2026-06-02.md) | Short policy for adding, updating, and validating docs. |
| [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md) | Practical rules for claim classes, freshness windows, source-of-truth conflicts, and CI guard scope. |
| [Documentation Audit Cadence](governance/documentation-audit-cadence-2026-06-06.md) | When to run docs gates and which evidence artifacts to keep. |
| [Command Snippet Registry](governance/command-snippet-registry.md) | Smoke vs manual coverage for high-value guide commands. |
| [Coverage Omit Ledger](governance/coverage-omit-ledger.md) | Governance ledger for files and directories omitted from test coverage reporting. |
| [Architecture Decision Records](adr/README.md) | Index of ADRs and their current accepted/closed states. |

## Plans And Work

| Plan | Use it for |
| --- | --- |
| **[Work Direction Execution Index](plans/work-direction-execution-index-2026-06-10.md)** | **Current execution order: Sprint 1 truth pass (WDA/WDB/WDG) after June 10 review.** |
| [ADR 0032 M1-M6 Work Plan](plans/adr-0032-m1-m6-work-plan-2026-06-13.md) | Event-spine migration slices from AuditLogger consumer through ContextBus/webhook cleanup. |
| [Work Direction Decomposition](plans/work-direction-decomposition-2026-06-10.md) | Full WD-A … WD-H backlog with acceptance gates. |
| [Documentation Optimization Master Plan](plans/documentation-optimization-master-plan-2026-06-04.md) | Prioritizing documentation work by stability, UX, risk, and ROI. |
| [Documentation Optimization Work Items](work-log/documentation-optimization-work-items-2026-06-04.md) | Concrete task execution ledger. |
| [Daily-Driver Complete Work Plan](plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md) | Historical daily-driver risk, feasibility, ROI, and sequence; use harness-first direction for current persona claims. |
| [Roadmap Work Items](work-log/roadmap-work-items-2026-06-04.md) | Product roadmap work items and acceptance criteria. |
| [Phase 0 Priority Work Items](work-log/phase-0-priority-work-items-2026-06-04.md) | Trust-repair tasks derived from project-state review. |
| [Phase 0 Governance Closure Report](work-log/phase-0-governance-closure-report-2026-06-04.md) | Closure evidence for coverage omit, dependency audit, and ADR-state governance. |
| [Dynamic Skill E2E Test Roadmap](plans/dynamic-skill-e2e-test-roadmap-2026-06-05.md) | Test roadmap for generated skills, RSS fixture checks, and long result handling. |
| [Dynamic Skill And Long Result Work Items](plans/dynamic-skill-and-long-result-work-items-2026-06-05.md) | Task ledger for lifecycle states, direct-write quarantine, RSS acceptance, long-result envelopes, and behavioral evals. |
| [Dynamic Skill Lifecycle And Result Flow](architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md) | Architecture target for candidate install, activation, long-result preservation, and output verification. |
| [Seven Control Loops Work Items](plans/seven-control-loops-work-items-2026-06-05.md) | Cross-cutting task ledger for spec-first, dynamic workflow, goal loops, model routing, review, memory, and human gates. |
| [Seven Control Loops Integration Map](architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md) | Architecture map for integrating the seven control loops into existing TeaAgent surfaces. |
| [Community Pain Points Response Plan](plans/community-pain-points-response-plan-2026-06-05.md) | Work plan for routing opacity, memory pollution, review cost, long-task drift, hook confusion, skill/MCP risk, and fake success. |
| [System Improvement Work Directions](plans/system-improvement-work-directions-2026-06-06.md) | 2026-06-06 workstream and ticket decomposition for trust claims, conversation UX, multi-agent safety, observability, integration contracts, docs governance, and competitive positioning. |
| [System Review Workstream Traceability](plans/system-review-workstream-traceability-2026-06-06.md) | Evidence-to-workstream trace for the June 6 critique package, including proof gates and validation commands. |

### Historical Reference Plans

The following plans are historical evidence from earlier passes. They have
supersession notes linking to current work. Use them for reasoning trail, not
for current status.

| Plan | Historical value |
| --- | --- |
| [Competitive Positioning Plan](plans/competitive-positioning-plan-2026-05-31.md) | May 2026 competitive baseline; superseded by [Competitor Signal Survey](analysis/competitor-signal-survey-2026-06-04.md). |
| [Remediation Roadmap](plans/remediation-roadmap.md) | Post-audit remediation from 2026-05-29; absorbed into Phase 0 trust repair. |
| [Governance Hardening](plans/governance-hardening.md) | Early governance plan (2026-05-28); superseded by [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md). |
| [Comprehensive Plan All Aspects](plans/comprehensive-plan-all-aspects-2026-05-31.md) | Phase 0 audit consolidation; superseded by [Complete Work Plan](plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md). |
| [UX Improvement Roadmap](plans/ux-improvement-roadmap-2026-05-31.md) | Early UX gap survey; absorbed into P0-A through P1-D workstreams. |
| [System Transparency Engineering Plan](plans/system-transparency-engineering-plan-2026-05-31.md) | Transparency pass; absorbed into P0-B, P0-D, P1-B, P2-B. |
| [Future Roadmap Backlog](plans/future-roadmap-risk-usability-backlog-2026-05-31.md) | Phase 0 horizon roadmap; restructured into P0–P3 priority stack. |
| [Agent Ecosystem Acceptance Roadmap](plans/agent-ecosystem-acceptance-roadmap-2026-05-31.md) | Early ecosystem roadmap; acceptance tracking now in ticket index. |

## Security And Reliability

| Topic | Start here |
| --- | --- |
| Threat model | [Threat Model](threat-model.md) |
| Security risk register | [Risk Register And Threat Model](security/risk-register-and-threat-model-2026-06-02.md) |
| Phase 0 trust repair | [Phase 0 Trust Repair Risk Brief](security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| Severity calibration | [Security Severity Calibration Rubric](security/severity-calibration-rubric.md) |
| Dependency audit scope refresh | [Dependency Audit Scope Refresh](security/dependency-audit-scope-refresh-2026-06-04.md) |
| FMEA | [FMEA](reliability/fmea-2026-06-02.md) |
| Trust-sensitive invariants | [Trust Sensitive Invariants](reliability/trust-sensitive-invariants-2026-06-02.md) |
| UX stability contract | [UX Stability Contract](ux-stability-contract.md) |
| Dependency audit policy | [Dependency Audit Policy](security/dependency-audit-policy.md) |

## Guides And References

| Surface | Documentation |
| --- | --- |
| CLI | [CLI](cli.md) and [USAGE](USAGE.md) |
| Conversation UX | [Chat Surface Semantics](guides/chat-surface-semantics.md) and [Background/Resume Vocabulary](guides/background-resume-vocabulary.md) |
| TUI | [TUI Daily-Driver Guide](tui-daily-driver-guide.md) and [TUI Chat Reference](tui-chat-reference.md) |
| Agent mode | [Agent Mode Operator Guide](agent-mode-operator-guide.md) |
| APIs | [API Index](api/README.md) |
| Module references | [Module Documentation Index](modules/INDEX.md) |
| Tools | [Tool Authoring Guide](tool-authoring.md) |
| Providers | [Provider Authoring Guide](provider-authoring.md) |

## Rules For Reading Dated Documents

- Dated analysis, reviews, surveys, audits, and work logs are evidence snapshots.
- Stable entry points and ledgers own current truth.
- If a dated document contradicts a stable current source, prefer the stable
  source and add a supersession note if the contradiction could mislead.
- Supersession notes follow the convention defined in
  [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md):
  `> Supersession note, YYYY-MM-DD: This file is historical evidence. For current
  status, use <new-source>. The relevant item is now <State> because <short evidence>.`
- Test counts, full-suite claims, dependency audit results, and competitor
  observations must include a date, command, and commit or they should be
  treated as stale.
- When adding a new document, link it from one active front door or explicitly
  mark it as archived evidence.

## Validation

After governance-sensitive documentation edits, run:

```bash
python3 scripts/validate_docs_consistency.py
python3 scripts/detect_stale_plans.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```
