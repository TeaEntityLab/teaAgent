# Roadmap Status

**Status:** Canonical roadmap tracking document
**Last updated:** 2026-06-04 (documentation-current-truth and Phase 0 governance closure linked)
**Owner:** TBD

## Purpose

Provide a single source of truth for roadmap item status, ownership, confidence, and next gates. Every roadmap item should have exactly one owner surface and status.

## Roadmap Horizons

| Horizon | Name | Target Outcome | Owner | Status | Confidence | Next Gate | Exit Evidence |
|---------|------|----------------|-------|--------|------------|-----------|---------------|
| H0 | Claim and risk hygiene | Public claims, risk register, docs gates, and tool warnings are owned | TBD | In Progress | Medium | DOCOPT-012 generalized guarded-claim registry | Risk register rows have owner/status/due date, volatile doc claims are guarded, docs checks pass |
| H1 | Daily operator loop | Setup, daily cockpit, plan, execute, approve, verify, recover, and remember are one coherent journey | TBD | In Progress | High | M1 complete | Journey acceptance tests pass across CLI/TUI baseline |
| H2 | Multi-surface continuity | CLI, TUI, IDE, dashboard, background, cloud, and gateway share one run-state contract | TBD | Pending | Medium | M2 complete | Surface parity tests prove identity, permissions, audit, cost, and recovery continuity |
| H3 | Ecosystem trust | MCP, plugins, skills, hooks, subagents, and automations are explainable, revocable, and testable | TBD | Pending | Medium | M3 complete | Trust-onboarding and activation-explain acceptance tests pass |
| H4 | Durable team operations | Long-running and team workflows have durable execution, control-plane views, policy, audit, and cost attribution | TBD | Pending | Low | M4 complete | Background/cloud/team lifecycle tests pass with evidence bundle export |
| H5 | Quality and eval loop | Prompt/runtime/model changes cannot silently degrade daily outcomes | TBD | Pending | Low | M5 complete | Prompt/config eval gates, long-session tests, repo-map benchmarks, and scope-creep tests run in release profile |
| H6 | Packaging and adoption | Desktop/client-server and external-facing release channels have supply-chain, update, and support plans | TBD | Pending | Low | M6 complete | SBOM/signing/update docs, packaged smoke tests, and onboarding metrics exist |

## Milestones

| Milestone | Target | Outcome | Owner | Status | Confidence | Next Gate | Exit Criteria |
|-----------|--------|---------|-------|--------|------------|-----------|---------------|
| M0 | 1-2 weeks | Risk register operational, release claims traceable, tool lint warnings budgeted, trust gaps have failing tests | TBD | Pending | Medium | GOV-002 complete | `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` pass |
| M1 | 2-6 weeks | Daily cockpit parity, run evidence summary, guided recovery | TBD | Complete | High | M2 complete | CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance |
| M2 | 4-10 weeks | Long-session context health, hash-bound plans, scope creep measurement | TBD | Pending | Medium | CTX-001 complete | Long-session context guard acceptance, scope budget acceptance, plan revision acceptance |
| M3 | 8-14 weeks | Extension activation explain, MCP trust onboarding, subagent review/merge | TBD | Pending | Medium | EXT-001 complete | Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance |
| M4 | 12-22 weeks | Background/cloud durability, gateway task intake, control-plane operator cockpit | TBD | Pending | Low | BG-001 complete | Background full lifecycle acceptance, gateway task intake acceptance, control-plane operator cockpit acceptance |
| M5 | Ongoing | Prompt/runtime/model/provider gating, repo-map benchmarking, release evidence bundles | TBD | Pending | Low | EVAL-001 complete | Prompt change regression suite, repo-map benchmark corpus, release evidence bundle in release profile |
| M6 | After M1-M4 | Desktop/client-server packaging with trust, update, rollback, session attach | TBD | Pending | Low | PKG-001 complete | Packaged launch smoke, signing/SBOM/update docs, desktop session attach acceptance |

## Track A - Roadmap Governance and Claim Hygiene

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| GOV-001 | Create canonical roadmap status table | TBD | Complete | High | GOV-002 | Medium |
| GOV-002 | Add risk-register schema | TBD | Pending | Medium | GOV-003 | High |
| GOV-003 | Add claim-to-evidence matrix | TBD | Pending | Medium | GOV-004 | High |
| GOV-004 | Define verification profiles | TBD | Pending | Medium | GOV-005 | High |
| GOV-005 | Add warning-budget ownership | TBD | Pending | Medium | GOV-006 | Medium |
| GOV-006 | Create release-channel source of truth | TBD | Pending | Medium | GOV-007 | Medium |
| GOV-007 | Make competitive survey freshness a release checklist blocker | TBD | Pending | Medium | GOV-008 | Medium |
| GOV-008 | Add decision expiry dates to ADRs | TBD | Pending | Medium | GOV-009 | Medium |
| GOV-009 | Add issue template for roadmap tasks | TBD | Pending | Low | GOV-010 | Low |
| GOV-010 | Tag backlog items by user journey | TBD | Pending | Low | GOV-011 | Low |
| GOV-011 | Create "do not claim" list | TBD | Pending | Medium | GOV-012 | Medium |
| GOV-012 | Add release residual-risk summary | TBD | Pending | Medium | M0 complete | High |
| GOV-013 | Create curated documentation front door | docs | Complete | High | GOV-014 | Low |
| GOV-014 | Add doc-vs-HEAD guarded claim registry | docs / verification | In Progress | Medium | DOCOPT-012 | High |
| GOV-015 | Audit High/Critical module risks for upward links | docs / module owners | Pending | Medium | DOCOPT-013 | High |

## Status Definitions

- **Complete**: Item is fully implemented and verified
- **In Progress**: Item is actively being worked on
- **Pending**: Item is not yet started
- **Blocked**: Item is blocked by dependencies
- **On Hold**: Item is intentionally deferred

## Confidence Definitions

- **High**: High confidence in approach and timeline
- **Medium**: Moderate confidence, some unknowns remain
- **Low**: Low confidence, significant unknowns or dependencies

## Notes

- This document should be updated when roadmap items change status
- Every roadmap item should have exactly one owner surface
- Status changes should be traceable via git history
- This document is referenced by release checklist and docs validators
- Documentation-current-truth work is tracked in
  `docs/plans/documentation-optimization-master-plan-2026-06-04.md` and
  `docs/work-log/documentation-optimization-work-items-2026-06-04.md`
- Phase 0 governance closure evidence is tracked in
  `docs/work-log/phase-0-governance-closure-report-2026-06-04.md`
