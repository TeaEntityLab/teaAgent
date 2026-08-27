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
> **Last reviewed:** 2026-08-26

**Status:** Canonical roadmap tracking document
**Last updated:** 2026-08-27 (the owner-operator is the current validated persona; ADR-0031 H4 evidence packet prepared: criteria 2/3/5 pass, criterion 1 has 0 shadow events across 5,690 scanned events (unexercised), criterion 4 remains human sign-off; `promotion_ready=false`; EFX-001–003 remain In Progress with live-provider proof pending; full suite verified 2026-08-26 at `026a8cc`: `6668 passed, 0 failed, 25 skipped`; prior snapshot `628 passed` at `85109e4` on 2026-06-10 is historical — see [suite truncation analysis](analysis/suite-truncation-root-cause-2026-06-10.md))
**Owner:** TBD

> **Canonical source of truth.** All other status docs (`docs/security/risk-register-and-threat-model-2026-06-02.md`, `docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md`, `docs/analysis/active-findings-status-ledger-2026-06-06.md`) defer to this document for overall completion status. Per-item test evidence lives in the risk register §9.

> **Direction note, 2026-06-14.** Roadmap rows describe owner-operator harness work unless explicitly labeled future or aspirational. External adoption, hosted deployment, enterprise/team operations, and broad daily-driver claims are not current goals.

## Purpose

Provide a single source of truth for roadmap item status, ownership, confidence, and next gates. Every roadmap item should have exactly one owner surface and status.

## Scheduling Rule

As of 2026-08-26, EFX-001 through EFX-003 are the only newly known,
authorized, non-held code items. They entered through DR-006's
`governance-gap` lane after deterministic local probes reproduced ambiguous
mutating-tool dispatch, effectful-tool approval bypass, and reusable
argument-blind one-time approval. Runtime guards now exist on the existing
runner, registry, audit, and approval seams with focused tests and providerless
acceptance (`tests/acceptance/test_efx_durable_effect_flow.py`); live
GitHub/browser/provider proof is still required before Complete. They do not authorize an effect
platform, exactly-once claim, distributed outbox, fencing service, actor
supervisor, or second event/workflow framework.

H0-H6 remain status taxonomy, not sprint menus. Other new work starts only from
cited owner friction, an independently proved governance gap, a dated owner
override, qualifying M4 co-maintainer dogfood, or the existing
[dated decision queue](specs/held-roadmap-forward-spec-index-2026-07-11.md#8-dated-decision-queue).
A trigger opens evaluation outside the proved governance-gap lane; it does not create implementation authority or prove completion.

## Roadmap Horizons

| Horizon | Name | Target Outcome | Owner | Status | Confidence | Next Gate | Exit Evidence |
|---------|------|----------------|-------|--------|------------|-----------|---------------|
| H0 | Claim and risk hygiene | Public claims, risk register, docs gates, and tool warnings are owned | governance | Complete | High | H1 | H0 exit evidence met; all M0 checks pass |
| H1 | Daily operator loop | Setup, daily cockpit, plan, execute, approve, verify, recover, and remember are one coherent journey | governance | Complete | High | H2 | Journey acceptance tests pass across CLI/TUI baseline; acceptance tier snapshot `628 passed` at `85109e4` (2026-06-10) |
| H2 | Multi-surface continuity | CLI, TUI, IDE, dashboard, background, cloud, and gateway share one run-state contract | TBD | On Hold — M2 foundation complete | Medium | Owner-validated continuity need | M2 acceptance complete; full surface parity (IDE/dashboard/cloud) is external/future under harness-first |
| H3 | Ecosystem trust | MCP, plugins, skills, hooks, subagents, and automations are explainable, revocable, and testable for the owner-operator | TBD | On Hold — M3 evidence complete | Medium | Cited owner friction | M3 acceptance complete; further owner-operator trust-onboarding simplification requires real daily-use evidence |
| H4 | Durable owner/agent operations | Long-running owner-operator and co-maintainer-agent workflows have durable run-state continuity, control-plane views, policy, audit, and cost attribution. Run continuity does not imply exactly-once tool execution, external-effect settlement, business acceptance, or reversal; ADR-0042 remains binding | TBD | On Hold — shadow wiring exists; ADR-0031 evidence packet prepared 2026-08-27 | Low | EFX live-proof closure + 2026-09-12 ADR-0031 owner review (promote/extend/revert) | Policy/RBAC shadow-wired (WDA-002/003); EFX-001–003 runtime guards landed on existing seams with live-provider proof pending; generic external-effect reconciliation remains held; ADR-0029 Option D executed; ADR-0031 evidence packet prepared at `.teaagent/reviews/adr-0031/decision-packet.json` — criteria 2 (coverage: 0 gaps), 3 (performance: median 0.50ms < 50ms), 5 (rollback: ok) pass; criterion 1 (shadow window: 0 observed events) and criterion 4 (human sign-off) remain open; `promotion_ready=false` |
| H5 | Quality and eval loop | Prompt/runtime/model changes cannot silently degrade daily outcomes | TBD | Blocked — offline release gate exists | Low | Funded live-provider evidence + owner decision | Release eval gate in CI; offline conversational and deterministic repo-map fixture corpora gated; default no-model gate remains advisory |
| H6 | Owner packaging and local distribution | Desktop/client-server and local release channels have supply-chain, update, rollback, and support plans for owner-operated use | TBD | On Hold — local proof exists; daily CLI unwired | Low | Owner update friction + trust-boundary proof | Single-platform update proof is reproducible via `scripts/prove_update_platform.py`; `update/*` remains intentionally absent from the daily CLI; no desktop packaging/session-attach proof |

## North-Star Goals (G1-G6)

Owner-ratified harness goals from the
[Harness-First Direction](strategy/harness-first-direction-2026-06-13.md) §2.
This table owns their current honest status; the identity document keeps the
ratified wording. Adoption record:
[whole-project lens review](analysis/whole-project-lens-review-2026-08-26.md).

| Goal | Ratified outcome | Status | Evidence / gate |
| --- | --- | --- | --- |
| G1 | Daily task without consulting docs | Pending — Unmeasured | Friction log 5/5 owner entries closed; owner zero-friction attestation 2026-07-22; no doc-lookup metric exists |
| G2 | Any run explained from one artifact | Pending — Unmeasured (surface exists) | `teaagent agent show <run>` plus run evidence summary (`tests/acceptance/test_run_evidence_summary_flow.py`); no one-screen acceptance signal yet |
| G3 | One event spine | Complete — Rescoped by owner decision | Spine is a typed observability read-model with audit dual-write (`teaagent/runner/_events.py`, ADR-0032); approval/budget/hook enforcement stays inline per [M4](work-log/m4-budget-stays-inline-2026-06-13.md) and [M5](work-log/m5-hooks-observability-only-2026-06-13.md) (enforcement bridge assessed unsuitable) |
| G4 | Extensible by hooks, not forks | Complete — tool dispatch scope | 8-event `HookRegistry` wired into tool dispatch (`teaagent/tools.py`); session-lifecycle hooks remain unwired |
| G5 | Docs corpus carries its weight | Complete | Constitution tier 8 ≤ 12; aging dashboard green; ~500-file corpus with 259 archive-tiered |
| G6 | Tests prove behavior, not construction | Complete | 586 test files typed (contract/behavior/adversarial/lifecycle) via `scripts/audit_test_quality.py` |

## Roadmap-Neutral Governance-Gap Intake - Effect Authority

These items do not reopen or renumber H0-H6. `Promote` is the scheduling
disposition under DR-006; implementation status is `In Progress` while focused
runtime and providerless acceptance evidence exists and live-provider proof is
still required for Complete.

| ID | Work Item | Implementation Status | Scheduling | Confidence | Required Exit Evidence |
|----|-----------|-----------------------|------------|------------|------------------------|
| EFX-001 | Refuse blind redispatch after an unmatched mutating-tool start; surface the attempt as unconfirmed/`UNKNOWN` | In Progress — runner sandwich + process-death test | Promote — P0 `governance-gap` | High | `tests/test_efx001_interrupted_dispatch.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-002 | Inventory effectful tools and fail closed when local policy sees external mutation, regardless of misleading read-only/destructive hints | In Progress — local `external_effect` + fail-closed backends | Promote — P0 `governance-gap` | High | `tests/test_efx002_effect_classification.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-003 | Bind one-time approval to run, tool, canonical payload/effect intent, then consume or expire it before dispatch | In Progress — digest-bound consume-once JIT | Promote — P0 `governance-gap` | High | `tests/test_efx003_one_time_approval.py`; providerless `tests/acceptance/test_efx_durable_effect_flow.py`; live GitHub/browser/provider proof still required for Complete |
| EFX-FUTURE | Provider-specific idempotency, settlement, and reconciliation beyond ADR-0042 | Absent | On Hold | Low | Local gaps closed, dated owner promise, provider-enforced identity/status contract, effect-specific fault evidence, and Human Review |

Evidence and adoption status:
[Durable-Effect Roadmap Socratic Review](analysis/durable-effect-roadmap-socratic-review-2026-08-25.md).
Current execution sequence (non-authoritative):
[Current Roadmap Execution Plan](plans/current-roadmap-execution-plan-2026-08-26.md).

## Milestones

| Milestone | Target | Outcome | Owner | Status | Confidence | Next Gate | Exit Criteria |
|-----------|--------|---------|-------|--------|------------|-----------|---------------|
| M0 | 1-2 weeks | Risk register operational, release claims traceable, tool lint warnings budgeted | governance | Complete | High | M1 complete | All 3 checks pass: `validate_docs_consistency.py`, `refresh_competitive_docs.py --check`, `teaagent tool lint --root .` |
| M1 | 2-6 weeks | Daily cockpit parity, run evidence summary, guided recovery | TBD | Complete | High | M2 complete | CLI/TUI cockpit parity acceptance, run evidence summary acceptance, guided recovery acceptance |
| M2 | 4-10 weeks | Long-session context health, hash-bound plans, scope creep measurement | TBD | Complete | High | M3 complete | Long-session context guard acceptance, scope budget acceptance, plan revision acceptance |
| M3 | 8-14 weeks | Extension activation explain, MCP trust onboarding, subagent review/merge | TBD | Complete | High | M4 complete | Extension activation explain acceptance, MCP trust onboarding acceptance, subagent review/merge acceptance |
| M4 | 12-22 weeks | Background/cloud durability, gateway task intake, control-plane operator cockpit | TBD | On Hold except DR-006 dogfood carve-out | Low | Dated BG-001/cockpit dogfood evidence | Only background lifecycle + operator cockpit are eligible under co-maintainer dogfood; cloud/SaaS/multi-tenant GTM remains held. Eligibility is not need or completion |
| M5 | Ongoing | Prompt/runtime/model/provider gating, repo-map benchmarking, release evidence bundles | TBD | Blocked — fixture corpus gated | Low | Funded non-advisory release profile + owner decision | Prompt/conversational regression suite and repo-map fixture corpus are in the release profile; model/provider regression evidence remains external |
| M6 | After M1-M4 | Desktop/client-server packaging for owner-operated trust, update, rollback, session attach | TBD | On Hold — no authorized owner demand | Low | Owner friction or dated override | Packaged launch smoke, signing/SBOM/update docs, and desktop session-attach acceptance remain future contracts |

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

`Complete` below records the implementation state of the listed historical
items. It does not authorize follow-on work. This survey-derived
`legacy-competitive` track remains held unless a new item cites owner friction,
an independently proved governance gap, or a dated owner override.

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

`Complete` below records implementation that already landed; it is not evidence
of current community demand. Follow-on community-survey work is held unless it
passes the same DR-006 authority gate as any other hypothesis-derived item.

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
| SEC-01 Audit HMAC persistence | **Fixed** | 100% | Code + passing tests | — | Key persisted at `teaagent/audit.py:163`; RISK-01 hardening: key-save OSError now logs warning (no silent pass); `HMACKeySaveTests::test_chain_key_save_failure_logs_warning` |
| SEC-17 ApprovalPolicy thread leak | **Fixed** | 100% | Code + passing tests | — | ENG-01: `__del__` shuts down executor; `ApprovalPolicyThreadLeakTests` |
| SEC-18 Zero cost rates (fake/ollama/vllm) | **Fixed** | 100% | Code + passing tests | — | RISK-02: nominal non-zero rates; `ProviderCostRateTests` |
| SEC-19 JIT approval no timeout | **Fixed** | 100% | Code + passing tests | — | OPS-01: 60s default timeout, auto-deny; `JITApprovalTimeoutTests` |
| SEC-02 MCP trust expiry | **Fixed** | 100% | Code + passing test | — | `teaagent/mcp_trust.py:286`, `teaagent/mcp_trust.py:343`; `test_server_trust_expiry()` |
| SEC-04 Budget default | **Fixed** | 100% | Code + passing tests | — | Default 500 cents; `test_budget_zero_cents_rejects_any_spend()` |
| SEC-06 JIT isolation | **Fixed** | 100% | Code + passing tests | — | `test_subagent_jit_approval_isolation_sec06()` |
| SEC-07 Docker hardening | **Fixed** | 100% | Code + passing tests | — | `teaagent/subagents/_isolation.py:347-365`; `test_docker_isolation_*()` |
| SEC-10 Shell allowlist | **Fixed** | 100% | Code + passing tests | — | `teaagent/workspace_tools/_shell.py:174`; `test_all_inspect_commands_classified_as_inspect()` |
| DS-02 TUI controller routing | **Fixed** | 100% | Code + passing tests | — | `teaagent/tui/core.py:996`; controller-based cost/undo/task |
| DS-05 TUI undo via journal | **Fixed** | 100% | Code + passing tests | — | `teaagent/tui/core.py:1057`; `test_tui_undo_uses_journal()` |
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
