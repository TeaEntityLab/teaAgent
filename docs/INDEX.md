# TeaAgent Documentation Index
# 2026-06-04

This is the curated front door for TeaAgent documentation. It is intentionally
not an exhaustive file list. Use it to find the current source of truth, then
follow dated evidence documents only when you need the reasoning trail.

## Start Here

| Need | Start here | Status rule |
| --- | --- | --- |
| What can a daily user trust today? | [Daily-Driver Current Status](daily-driver-current-status.md) | Current truth; update whenever TUI, chat, agent mode, approval, cost, undo, or resume behavior changes. |
| What is the current documentation-state assessment? | [Documentation State Review](analysis/documentation-state-review-2026-06-04.md) | Current dated evidence for corpus shape, drift risks, and consolidation priorities. |
| What is the documentation operating model? | [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md) | Governance rulebook for claim types, TTL, owners, supersession, and CI guard targets. |
| What should be done next? | [Documentation Optimization Master Plan](plans/documentation-optimization-master-plan-2026-06-04.md) | Execution plan for reducing drift and improving discoverability. |
| What are the concrete work items? | [Documentation Optimization Work Items](work-log/documentation-optimization-work-items-2026-06-04.md) | Task ledger with priority, status, dependencies, and acceptance criteria. |

## Current Truth

| Question | Canonical source |
| --- | --- |
| Current daily-driver behavior | [Daily-Driver Current Status](daily-driver-current-status.md) |
| Acceptance flow inventory | [Acceptance Coverage](acceptance.md) |
| Roadmap state | [Roadmap Status](roadmap-status.md) |
| Ticket execution order | [Ticket Execution Plans](plans/ticket-plans/index.md) |
| Module ownership and inspection paths | [Module Documentation Index](modules/INDEX.md) |
| Release gates | [Release Checklist](release-checklist.md) and [Daily-Driver Release Gates](governance/daily-driver-release-gates-2026-06-02.md) |
| Permission and approval behavior | [Permission And Approval Playbook](permission-and-approval-playbook.md) |
| Operator trust model | [Operator Trust Model](operator-trust-model.md) |

## Evidence And Review

| Topic | Evidence package |
| --- | --- |
| June 4 project-state fact check | [Project State Cross-Review Fact Check](analysis/project-state-cross-review-fact-check-2026-06-04.md) |
| June 4 total review | [Total Review Index](analysis/total-review-2026-06-04-INDEX.md) |
| June 4 documentation critique | [Documentation Critical Questioning](reviews/documentation-critical-questioning-2026-06-04.md) |
| June 1 daily-driver review package | [Daily-Driver Review Package Index](analysis/daily-driver-review-INDEX-2026-06-01.md) |
| Markdown governance review | [Markdown Status Review](analysis/markdown-status-review-2026-06-02.md) |
| Competitor signal survey | [Competitor Signal Survey](analysis/competitor-signal-survey-2026-06-04.md) |
| Product principles | [TeaAgent Product Principles](strategy/teaagent-product-principles-2026-06-04.md) |

## Governance

| Rule surface | Purpose |
| --- | --- |
| [Governance Index](governance/README.md) | Standards and process entry point. |
| [Document State Model](governance/document-state-model.md) | Canonical state vocabulary for findings, risks, issues, tickets, and roadmap rows. |
| [Risk Issue Roadmap Workflow](governance/risk-issue-roadmap-workflow.md) | Pipeline from finding to issue, ticket, roadmap, verification, and supersession. |
| [Documentation Taxonomy And Ownership](governance/doc-taxonomy-and-ownership.md) | Where each document type belongs and who owns it. |
| [Documentation Maintenance Policy](governance/doc-maintenance-policy-2026-06-02.md) | Short policy for adding, updating, and validating docs. |
| [Documentation Operating Model](governance/documentation-operating-model-2026-06-04.md) | Practical rules for claim classes, freshness windows, source-of-truth conflicts, and CI guard scope. |
| [Coverage Omit Ledger](governance/coverage-omit-ledger.md) | Governance ledger for files and directories omitted from test coverage reporting. |

## Plans And Work

| Plan | Use it for |
| --- | --- |
| [Documentation Optimization Master Plan](plans/documentation-optimization-master-plan-2026-06-04.md) | Prioritizing documentation work by stability, UX, risk, and ROI. |
| [Documentation Optimization Work Items](work-log/documentation-optimization-work-items-2026-06-04.md) | Concrete task execution ledger. |
| [Daily-Driver Complete Work Plan](plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md) | Daily-driver risk, feasibility, ROI, and sequence. |
| [Roadmap Work Items](work-log/roadmap-work-items-2026-06-04.md) | Product roadmap work items and acceptance criteria. |
| [Phase 0 Priority Work Items](work-log/phase-0-priority-work-items-2026-06-04.md) | Trust-repair tasks derived from project-state review. |

## Security And Reliability

| Topic | Start here |
| --- | --- |
| Threat model | [Threat Model](threat-model.md) |
| Security risk register | [Risk Register And Threat Model](security/risk-register-and-threat-model-2026-06-02.md) |
| Phase 0 trust repair | [Phase 0 Trust Repair Risk Brief](security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| FMEA | [FMEA](reliability/fmea-2026-06-02.md) |
| Trust-sensitive invariants | [Trust Sensitive Invariants](reliability/trust-sensitive-invariants-2026-06-02.md) |
| UX stability contract | [UX Stability Contract](ux-stability-contract.md) |
| Dependency audit policy | [Dependency Audit Policy](security/dependency-audit-policy.md) |

## Guides And References

| Surface | Documentation |
| --- | --- |
| CLI | [CLI](cli.md) and [USAGE](USAGE.md) |
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
- Test counts, full-suite claims, dependency audit results, and competitor
  observations must include a date, command, and commit or they should be
  treated as stale.
- When adding a new document, link it from one active front door or explicitly
  mark it as archived evidence.

## Validation

After governance-sensitive documentation edits, run:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```
