# Roadmap Status

**Status:** Canonical roadmap tracking document
**Last updated:** 2026-06-05 (fixed-item evidence added; unverified claims registry added; all other status docs link here)
**Owner:** TBD

> **Canonical source of truth.** All other status docs (`docs/security/risk-register-and-threat-model-2026-06-02.md`, `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md`, `docs/analysis/daily-driver-findings-status-ledger-2026-06-01.md`) defer to this document for overall completion status. Per-item test evidence lives in the risk register §9.

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

## Critical Path — Current Completion Evidence

| Item | Status | Completion % | Evidence Type | Owner | Notes |
|------|--------|:---:|---|---|---|
| SEC-01 Audit HMAC persistence | VERIFY/CLOSE | 90% | Code + pending test | TBD | Key persisted at `audit.py:165`; test sign-off pending |
| SEC-02 MCP trust expiry | **Fixed** | 100% | Code + passing test | — | `mcp_trust.py:148,168`; `test_server_trust_expiry()` |
| SEC-04 Budget default | **Fixed** | 100% | Code + passing tests | — | Default 500 cents; `test_budget_zero_cents_rejects_any_spend()` |
| SEC-06 JIT isolation | **Fixed** | 100% | Code + passing tests | — | `test_subagent_jit_approval_isolation_sec06()` |
| SEC-07 Docker hardening | **Fixed** | 100% | Code + passing tests | — | `_isolation.py:234-241`; `test_docker_isolation_*()` |
| SEC-10 Shell allowlist | **Fixed** | 100% | Code + passing tests | — | `_shell.py:175`; `test_all_inspect_commands_classified_as_inspect()` |
| DS-02 TUI controller routing | **Fixed** | 100% | Code + passing tests | — | `tui/__init__.py:996`; controller-based cost/undo/task |
| DS-05 TUI undo via journal | **Fixed** | 100% | Code + passing tests | — | `tui/__init__.py:860`; `test_tui_undo_uses_journal()` |
| DS-09 Background UUID rejection | **Fixed** | 100% | Code + passing test | — | `test_agent_run_background_rejects_known_run_or_suspension_id()` |
| DS-12 Empty-path approval | **Fixed** | 100% | Code + passing tests | — | `test_empty_path_globs_rejected_ds12()` |
| DS-13 Budget zero semantics | **Fixed** | 100% | Code + passing tests | — | `None`=unlimited, `0`=no-spend |
| DS-01 TUI cost accumulation | Active | 0% | None | TICKET-12 | `_session_cost_cents` not incremented |
| DS-08 resume always errors | Active | 0% | None | TICKET-16 | `run_started` event schema mismatch |
| DS-11 Initial task dropped | Active | 0% | None | TASK-DD2-001 | `chat_command` never reads `args.task` |
| H0 Claim + risk hygiene | In Progress | 60% | Partial | TBD | Risk register updated; validation script exists; claim registry TBD |
| M0 Risk register operational | In Progress | 70% | Partial | TBD | Register has evidence; `validate_docs_consistency.py` exists; GOV-002 pending |

**Merge gate:** `python3 scripts/validate_docs_consistency.py` must pass before any PR that updates roadmap or risk register status.

**Unverified ecosystem claims:** See `docs/security/risk-register-and-threat-model-2026-06-02.md` Appendix C for a full list of aspirational claims that must not be marked as shipped without test evidence.

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
