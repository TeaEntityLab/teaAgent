# Roadmap Status

> **Claim class:** Current truth for roadmap horizon, milestone, and track status.
>
> **Owns:** Which workstreams are complete, in progress, or pending, and their
> next gates.
>
> **Does not own:** Daily-user command recommendations (`daily-driver-current-status.md`)
> or historical review reasoning in dated analysis files.
>
> **Review trigger:** Roadmap horizon, milestone, or track status changes.
> **Last reviewed:** 2026-06-14

**Status:** Canonical roadmap tracking document
**Last updated:** 2026-06-14 (harness-first alignment: owner-operator is the current validated persona; external adoption and hosted/team expansion remain future hypotheses until real owner friction or explicit external evidence reopens them. Prior acceptance tier snapshot `628 passed` at `85109e4` on 2026-06-10 is historical evidence, not a current collection; full-suite count unverified — see [suite truncation analysis](analysis/suite-truncation-root-cause-2026-06-10.md))
**Owner:** TBD

> **Canonical source of truth.** All other status docs (`docs/security/risk-register-and-threat-model-2026-06-02.md`, `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md`, `docs/analysis/active-findings-status-ledger-2026-06-06.md`) defer to this document for overall completion status. Per-item test evidence lives in the risk register §9.

> **Direction note, 2026-06-14.** Roadmap rows describe owner-operator harness work unless explicitly labeled future or aspirational. External adoption, hosted deployment, enterprise/team operations, and broad daily-driver claims are not current goals.

## Purpose

Provide a single source of truth for roadmap item status, ownership, confidence, and next gates. Every roadmap item should have exactly one owner surface and status.

## Roadmap Horizons

| Horizon | Name | Target Outcome | Owner | Status | Confidence | Next Gate | Exit Evidence |
|---------|------|----------------|-------|--------|------------|-----------|---------------|
| H0 | Claim and risk hygiene | Public claims, risk register, docs gates, and tool warnings are owned | governance | Complete | High | H1 | H0 exit evidence met; all M0 checks pass |
| H1 | Daily operator loop | Setup, daily cockpit, plan, execute, approve, verify, recover, and remember are one coherent journey | governance | Complete | High | H2 | Journey acceptance tests pass across CLI/TUI baseline; acceptance tier snapshot `628 passed` at `85109e4` (2026-06-10) |
| H2 | Multi-surface continuity | CLI, TUI, IDE, dashboard, background, cloud, and gateway share one run-state contract | TBD | Partially fixed — M2 foundation wired | Medium | WDA-002 | M2 acceptance complete; full surface parity (IDE/dashboard/cloud) still open |
| H3 | Ecosystem trust | MCP, plugins, skills, hooks, subagents, and automations are explainable, revocable, and testable for the owner-operator | TBD | Partially fixed — M3 tests pass | Medium | WDC-002 | M3 acceptance complete; owner-operator trust onboarding simplification still open |
| H4 | Durable owner/agent operations | Long-running owner-operator and co-maintainer-agent workflows have durable execution, control-plane views, policy, audit, and cost attribution | TBD | Partially fixed — shadow wired | Low | WDA-004 | Policy/RBAC shadow-wired (WDA-002/003); consensus deferred (ADR 0029); shadow mode exit criteria defined (ADR 0031, expiry 2026-09-12) |
| H5 | Quality and eval loop | Prompt/runtime/model changes cannot silently degrade daily outcomes | TBD | Partially fixed — release gate wired | Low | WDA-005 | Release eval gate in CI (WDA-004/WDD-001); offline conversational corpus |
| H6 | Owner packaging and local distribution | Desktop/client-server and local release channels have supply-chain, update, rollback, and support plans for owner-operated use | TBD | Partially fixed — unwired | Low | WDA-005 | `update/*` package implemented but unwired; no owner-platform proof yet |

## Milestones

| Milestone | Target | Outcome | Owner | Status | Confidence | Next Gate | Exit Criteria |
|-----------|--------|---------|-------|--------|------------|-----------|---------------|
| M0 | 1-2 weeks | Risk register operational, release claims traceable, tool lint warnings budgeted | governance | Complete | High | M1 complete | All 3 checks pass: `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` |
| M1 | 2-6 weeks | Daily cockpit parity, run evidence summary, guided recovery | TBD | Complete | High | M2 complete | CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance |
| M2 | 4-10 weeks | Long-session context health, hash-bound plans, scope creep measurement | TBD | Complete | High | M3 complete | Long-session context guard acceptance, scope budget acceptance, plan revision acceptance |
| M3 | 8-14 weeks | Extension activation explain, MCP trust onboarding, subagent review/merge | TBD | Complete | High | M4 complete | Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance |
| M4 | 12-22 weeks | Background/cloud durability, gateway task intake, control-plane operator cockpit | TBD | Pending | Low | BG-001 complete | Background full lifecycle acceptance, gateway task intake acceptance, control-plane operator cockpit acceptance |
| M5 | Ongoing | Prompt/runtime/model/provider gating, repo-map benchmarking, release evidence bundles | TBD | Pending | Low | EVAL-001 complete | Prompt change regression suite, repo-map benchmark corpus, release evidence bundle in release profile |
| M6 | After M1-M4 | Desktop/client-server packaging for owner-operated trust, update, rollback, session attach | TBD | Pending | Low | PKG-001 complete | Packaged launch smoke, signing/SBOM/update docs, desktop session attach acceptance |

## Track A - Roadmap Governance and Claim Hygiene

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| GOV-001 | Create canonical roadmap status table | TBD | Complete | High | GOV-002 | Medium |
| GOV-002 | Add risk-register schema | docs / governance | Complete | High | release audit | High |
| GOV-003 | Add claim-to-evidence matrix | docs / governance | Complete | High | release audit | High |
| GOV-004 | Define verification profiles | docs / governance | Complete | High | release audit | High |
| GOV-005 | Add warning-budget ownership | docs / governance | Complete | High | release audit | Medium |
| GOV-006 | Create release-channel source of truth | docs / governance | Complete | High | release audit | Medium |
| GOV-007 | Make competitive survey freshness a release checklist blocker | docs / governance | Complete | High | release audit | Medium |
| GOV-008 | Add decision expiry dates to ADRs | docs / governance | Complete | High | ADR review | Medium |
| GOV-009 | Add issue template for roadmap tasks | docs / governance | Complete | High | backlog refinement | Low |
| GOV-010 | Tag backlog items by user journey | docs / governance | Complete | High | backlog refinement | Low |
| GOV-011 | Create "do not claim" list | docs / governance | Complete | High | release audit | Medium |
| GOV-012 | Add release residual-risk summary | docs / governance | Complete | High | release audit | High |
| GOV-013 | Create curated documentation front door | docs | Complete | High | GOV-014 | Low |
| GOV-014 | Add doc-vs-HEAD guarded claim registry | docs / verification | Complete | High | release audit | High |
| GOV-015 | Audit High/Critical module risks for upward links | docs / module owners | Complete | High | GOV-016 | High |

## Track H3 - Ecosystem Trust And Dynamic Skills

The June 5 dynamic-skill research narrows the first H3 proof point: TeaAgent
should not expand ecosystem breadth until generated skills, long results, and
skill-output verification are testable against the RSS failure case.
DSK-P0-001 through DSK-P0-007 (lifecycle state machine, write quarantine,
offline RSS fixture, long-result envelope, output validators, explainability,
and decision-visibility) form the first ecosystem-trust spine.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| DSK-P0-001 | Skill lifecycle state machine distinguishes loaded, activated, used, and verified. | skills / audit | Complete | High | lifecycle event tests | High |
| DSK-P0-002 | Direct active-skill writes are blocked, quarantined, or labeled unmanaged. | workspace tools / skill writer | Complete | High | protected path acceptance | High |
| DSK-P0-003 | Offline RSS fixture acceptance proves source-backed skill output. | tests / skills | Complete | High | fixture summary test | High |
| DSK-P0-004 | Long-result envelope preserves preview, full artifact, hash, and cursor. | tools / audit | Complete | High | large result fixture test | High |
| DSK-P0-005 | Output artifact validators for source-backed tasks. | tests / verifier | Complete | High | validator test suite | High |
| DSK-P0-006 | Unmanaged skill explainability state labels candidate, shadowed, and blocked skills. | skill loader / CLI | Complete | High | explainability state test | High |
| DSK-P0-007 | Invalid tool-decision failure is visible in skill flows, not silently successful. | chat agent / runner | Complete | High | invalid-decision test | High |
| DSK-P1-001 | Behavioral skill eval compares with-skill and without-skill results. | skill eval | Complete | High | deterministic eval harness | Medium |
| DSK-P1-002 | Skill invocation audit records activation cause and output artifact links. | audit / run store | Complete | High | run evidence integration | Medium |
| DSK-P1-003 | Explicit skill activation UX is available through CLI/task config first. | CLI / runner | Complete | High | explicit activation acceptance | Medium |

Current evidence package:

- [Dynamic Skill Generation And Long Result Audit](analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md)
- [RSS Dynamic Skill Failure Case Study](analysis/rss-failure-case-study-2026-06-05.md)
- [Agent Ecosystem Core Values](strategy/agent-ecosystem-core-values-2026-06-05.md)
- [Dynamic Skill Critical Questioning](reviews/dynamic-skill-critical-questioning-2026-06-05.md)
- [Dynamic Skill And Long Result Work Items](plans/dynamic-skill-and-long-result-work-items-2026-06-05.md)
- [Dynamic Skill Lifecycle And Result Flow](architecture/dynamic-skill-lifecycle-and-result-flow-2026-06-05.md)

## Cross-Horizon Track - Seven Control Loops

The June 5 competitor pass identifies seven control loops that should become
TeaAgent's architecture and product governance model across H0-H5:
spec-first direction, dynamic workflow breadth, loop/goal depth, model routing,
synthesis review, precise memory, and human review gates. This track is
cross-horizon because each loop touches multiple existing modules rather than a
single roadmap horizon.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| SCL-P0-001 | Bind high-risk runs to a spec or plan receipt. | plan gate / runner | Complete | High | failing high-risk no-spec test | High |
| SCL-P0-002 | Add repo-grounding checks before spec tasks execute. | plan gate / code map | Complete | High | stale-spec fixture test | High |
| SCL-P0-003 | Link dynamic skill lifecycle and long-result work as the H3 proof path. | skills / docs | Complete | High | DSK-P0 link audit | High |
| SCL-P0-004 | Define persisted goal records for loop state, evidence, and stop criteria. | runner / run store | Complete | High | goal record schema test | High |
| SCL-P0-005 | Add model-route receipts to audit and run evidence. | model routing / audit | Complete | High | deterministic route fixture | Medium |
| SCL-P0-006 | Define synthesis review artifacts for high-risk answers. | review / evidence | Complete | High | contradictory-source fixture | High |
| SCL-P0-007 | Define human review gate packets for irreversible actions. | approval / TUI | Complete | High | destructive action packet test | High |
| SCL-P1-001 | Add typed memory metadata: scope, source, confidence, TTL, supersession, owner. | memory | Complete | High | memory promotion tests | High |
| SCL-P1-002 | Add memory quarantine and promotion flow. | memory / review | Complete | High | unreviewed memory injection test | High |
| SCL-P1-003 | Add goal status and evidence inspection commands. | CLI / TUI | Complete | High | status command acceptance | Medium |
| SCL-P1-004 | Add role-aware model routing tests. | model routing | Complete | High | route matrix tests | Medium |
| SCL-P1-005 | Require synthesis review for source-backed high-risk research. | review / docs | Complete | High | review requirement validator | Medium |
| SCL-P1-006 | Add gate packets to skill install and memory promotion. | skills / memory / approval | Complete | High | gate packet acceptance | High |
| SCL-P2-001 | Build a TUI cockpit for spec, goal, route, review, memory, and approval state. | TUI | Complete | High | cockpit prototype | Medium |
| SCL-P2-002 | Add release evidence bundle for all seven loops. | release / docs | Complete | High | release bundle check | Medium |

Current evidence package:

- [Seven Control Loops Competitor Survey](analysis/seven-control-loops-competitor-survey-2026-06-05.md)
- [Seven Control Loops Product Direction](strategy/seven-control-loops-product-direction-2026-06-05.md)
- [Seven Control Loops TeaAgent Integration Map](architecture/seven-control-loops-teaagent-integration-map-2026-06-05.md)
- [Seven Control Loops Critical Questioning](reviews/seven-control-loops-critical-questioning-2026-06-05.md)
- [Seven Control Loops Work Items](plans/seven-control-loops-work-items-2026-06-05.md)

## Cross-Horizon Track - Community Pain Point Overlay

The June 5 community pass adds a user-pain overlay to the seven control loops.
The work is deliberately receipt-oriented: make routing, memory, review, cost,
skill/MCP, approval, goal, and proof-of-use behavior visible before widening
autonomy.

| ID | Work Item | Owner | Status | Confidence | Next Gate | Risk |
|----|-----------|-------|--------|------------|-----------|------|
| CPP-P0-001 | Add route evidence panel to run summary. | model routing / run evidence | Complete | High | model route fixture | High |
| CPP-P0-002 | Add goal checkpoint receipt. | runner / run store | Complete | High | long-goal checkpoint test | High |
| CPP-P0-003 | Add memory write quarantine rule for agent-created project memory. | memory / approval | Complete | High | pending-memory test | High |
| CPP-P0-004 | Add review artifact minimum schema. | review / subagents | Complete | High | missing-evidence review test | High |
| CPP-P0-005 | Add approval authority receipt. | approval / audit | Complete | High | exact-scope authority test | High |
| CPP-P0-006 | Add dynamic asset provenance summary. | skills / MCP / audit | Complete | High | dynamic asset evidence test | High |
| CPP-P0-007 | Add proof-of-use requirement for skill-backed outputs. | skills / runner | Complete | High | skill-backed output test | High |
| CPP-P0-008 | Add intent-drift pre-write check for high-risk runs. | plan gate / policy | Complete | High | out-of-scope write test | High |
| CPP-P1-001 | Add review repeat suppression. | review / evidence | Complete | High | repeated finding state test | Medium |
| CPP-P1-002 | Add phase budget thresholds. | budget / model routing | Complete | High | phase budget test | Medium |
| CPP-P1-003 | Add context pressure score. | context bus / TUI | Complete | High | context score test | Medium |
| CPP-P1-004 | Add untrusted-source memory tests. | tests / memory | Complete | High | memory poisoning fixture | High |
| CPP-P1-005 | Add risk-adaptive spec exemption UX. | plan gate / CLI | Complete | High | low-risk exemption test | Medium |
| CPP-P2-001 | Add control-plane cockpit. | TUI | Complete | High | cockpit acceptance test | Medium |

Current evidence package:

- [Community Agent Pain Points Survey](analysis/community-agent-pain-points-survey-2026-06-05.md)
- [Community Pain Points Response Plan](plans/community-pain-points-response-plan-2026-06-05.md)

## Status Definitions

- **Proposed**: Item is documented and not yet accepted as implementation-ready
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
| SEC-01 Audit HMAC persistence | **Fixed** | 100% | Code + passing tests | — | Key persisted at `audit.py:165`; RISK-01 hardening: key-save OSError now logs warning (no silent pass); `HMACKeySaveTests::test_chain_key_save_failure_logs_warning` |
| SEC-17 ApprovalPolicy thread leak | **Fixed** | 100% | Code + passing tests | — | ENG-01: `__del__` shuts down executor; `ApprovalPolicyThreadLeakTests` |
| SEC-18 Zero cost rates (fake/ollama/vllm) | **Fixed** | 100% | Code + passing tests | — | RISK-02: nominal non-zero rates; `ProviderCostRateTests` |
| SEC-19 JIT approval no timeout | **Fixed** | 100% | Code + passing tests | — | OPS-01: 60s default timeout, auto-deny; `JITApprovalTimeoutTests` |
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
| DS-01 TUI cost accumulation | **Fixed** | 100% | Code + passing tests | — | TICKET-12; `test_task003_cost_truth.py` |
| DS-08 resume always errors | **Fixed** | 100% | Code + passing tests | — | TICKET-16 Phase 2; `test_repl_suspend_resume_roundtrip` |
| DS-11 Initial task dropped | **Fixed** | 100% | Code + passing tests | — | TASK-DD2-001; chat task forwarding tests |
| H0 Claim + risk hygiene | Complete | 100% | Code + docs | governance | All H0 items done; risk register has Owner/Due; M0 checks pass |
| M0 Risk register operational | Complete | 100% | Code + docs | governance | All 3 M0 checks verified passing |

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
- Full pytest collection is expected to run from the development environment
  declared in `pyproject.toml`; `hypothesis` already appears under
  `project.optional-dependencies.dev`, so the June 11 collection failure was an
  environment provisioning gap rather than a missing dependency declaration.
