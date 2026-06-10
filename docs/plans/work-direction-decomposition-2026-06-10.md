# Work Direction Decomposition
# 2026-06-10

> **Claim class:** Proposal (execution backlog candidate).
> **Derived from:** the [2026-06-10 System Critical Review Package](../analysis/system-critical-review-2026-06-10-INDEX.md).
> **Succeeds:** [System Improvement Work Directions (2026-06-06)](system-improvement-work-directions-2026-06-06.md) — that backlog's WS1/WS2/WS3 spine is substantially executed (see refresh docs for per-item evidence); WS0/WS4/WS5/WS6 items not restated here remain valid.
>
> Every direction below names its source finding, a falsifiable acceptance
> gate, and an explicit "do not do" boundary, per the governed-engineering
> framework.

---

## Priority Stack

| Priority | Direction | Why first |
| --- | --- | --- |
| P0 | WD-A Wire-or-quarantine the H4/H5/H6 islands | Largest live integrity gap; blocks every team-ops and eval claim |
| P0 | WD-B Status-truth automation | The drift that WD-A fixes once will recur without a gate |
| P0 | WD-G Suite health and tiering | Suite status at HEAD was unprovable on first attempt; everything else depends on trustworthy verification |
| P1 | WD-C General-user conversation simplification | Largest adoption gap that is actually in TeaAgent's control |
| P1 | WD-D Eval gate as public differentiator | Only axis where TeaAgent can set the market benchmark |
| P2 | WD-E Remote-capable approval backend | The single highest-leverage remote investment; everything else remote stays non-goal |
| P2 | WD-F Source-tree consolidation | Root sprawl (183 top-level modules) compounds every other cost |
| P3 | WD-H Positioning refresh and external validation | Only after WD-A/WD-B make claims provable |

---

## WD-A — Wire or Quarantine H4/H5/H6 (P0)

**Source:** ENG-R1, multi-agent refresh §H4 cluster, UX refresh UX-R3.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDA-001 | Label every unwired module (`rbac`, `policy_engine`, `policy_routing`, `consensus_validation`, `eval_suite`, `release_gate`, `scope_creep`, `prompt_regression`, `repo_map_benchmark`, `update/*`) `experimental — unwired` in docstring + roadmap. | Validator (WDB-001) passes; roadmap rows show honest status. |
| WDA-002 | Wire policy engine into the approval path in **shadow mode** (log decisions, enforce nothing). | Shadow decisions appear in run receipts; zero behavior change proven by existing acceptance suite. |
| WDA-003 | Wire RBAC checks onto subagent launch parameters (shadow first, then enforce). | A role-violating launch is denied in enforce mode; acceptance test cites H4-002. |
| WDA-004 | Wire `release_gate` + `prompt_regression` into a CI release profile. | Release workflow fails on seeded regression fixture. |
| WDA-005 | Wire `update/` into a real packaging proof: one signed artifact, one delta update, one rollback, on one platform. | Documented end-to-end run with hashes; H6 row may then claim "single-platform proof", nothing more. |
| WDA-006 | Decide and document: consensus validation either gates destructive actions behind the existing approval queue or is explicitly deferred. | ADR with expiry date. |

**Do not:** claim H4/H5/H6 "Complete" while any cluster member is
shadow-mode or unwired; build more H4 features before WDA-002/003 land.

## WD-B — Status-Truth Automation (P0)

**Source:** ENG-R2; standing doc-drift memory across four review cycles.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDB-001 | Wiring validator: walk the import graph from entry points (CLI, TUI, runner, gateway, scripts, CI); fail on any `teaagent/*` module that is unreachable and unlabeled. | CI red on an unlabeled island fixture; green at HEAD after WDA-001. |
| WDB-002 | Claim-commit gate: a commit message matching `H\d|M\d|Complete|Implement Horizon` must touch `docs/roadmap-status.md` or carry an explicit `Roadmap-Status: unchanged` trailer. | Hook/CI check with fixture tests. |
| WDB-003 | Fix the current roadmap contradictions (H2/H3 vs M2/M3; H4–H6 vs commit log) with evidence-cited rows. | `validate_docs_consistency.py` extended to cross-check horizon vs milestone status. |
| WDB-004 | Add suite-status freshness rule: any doc quoting a test count must cite run date + commit; validator warns after 72 h. | Validator test. |

## WD-C — General-User Conversation Simplification (P1)

**Source:** UX refresh UX-R1/R2/R4/R5.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDC-001 | Ten-minute stranger test: record every concept a new user must confront in their first session; publish the list as the reduction target. | Dated findings doc; baseline concept count measured. |
| WDC-002 | Three-concept onboarding path (ask / approve / undo) with progressive disclosure of receipts, budgets, tenants, trust tiers. | Stranger-test concept count ≤ 3 for the happy path; acceptance test for lazy disclosure. |
| WDC-003 | Plain-language first line on every receipt and approval prompt; JSON behind `--json`. | Snapshot tests on receipt/approval rendering. |
| WDC-004 | Terminology freeze: one pass over `docs/terminology.md` declaring canonical nouns (tenant, workspace, session, run, goal, background); docs lint enforces. | Lint rule + zero violations. |

**Do not:** add operator-cockpit breadth until WDC-002 ships (persona-priority
decision — confirm with product owner if contested).

## WD-D — Eval Gate as Public Differentiator (P1)

**Source:** Competitor consolidation §Strategic Readout 2; UX-R3.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDD-001 | Conversational-quality corpus (clarification, interruption, correction, long-context recall) scored via `eval_suite` in CI. | Seeded conversational regression turns CI red. |
| WDD-002 | Publish the eval-gate design + results as a dated public doc — the claim "agent behavior changes are eval-gated, and you can read the gate" — only after WDA-004. | Doc with reproduction commands; claim-audit approved. |
| WDD-003 | Re-verify on publication day that no major competitor exposes user-auditable eval gates (the corpus absence is dated 06-07). | Same-day source-backed note. |

## WD-E — Remote-Capable Approval Backend (P2)

**Source:** Multi-agent refresh §walkthrough; non-goals table.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDE-001 | Implement the named `remote` backend for `coordination/approval_backend.py` (transport candidate: the existing gateway), keeping file backend default. | Approval granted from a second process/machine in an integration test. |
| WDE-002 | Signed approvals: Ed25519 agent/operator identity for queue writes (reuse `tsb_format` primitives). | Forged-writer fixture rejected; non-goals row "cryptographic peer identity" updated with test citation. |
| WDE-003 | Close the open verification gaps: WS2-004 depth/concurrency bypass test; WS2-003 cost-cents inheritance test. | Named acceptance tests; non-goals rows updated. |

**Do not:** start federation, PKI/MCP trust certificates, or multi-operator
conflict resolution until WDE-001/002 are merged and the non-goals doc is
re-scored.

## WD-F — Source-Tree Consolidation (P2)

**Source:** ENG-R3.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDF-001 | ADR: canonical homes for policy/consensus/governance code (`teaagent/governance/`, `teaagent/consensus/`, `teaagent/coordination/`); new root modules forbidden without ADR exception. | ADR merged; lint counts root modules and fails above the frozen baseline (183). |
| WDF-002 | Fold the H4/H5 root modules into their canonical packages with deprecation re-exports. | Import compatibility tests; root count decreases. |

## WD-G — Suite Health and Tiering (P0)

**Source:** ENG-R5; Q10 in the reasoning ledger (first full-suite run produced
no summary line — possible crash at ~49%, exit code masked by pipeline).

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDG-001 | Diagnose the truncated run: reproduce, capture faulthandler output, and either fix the crash or document the harness-side cause. | Root-cause note; clean full-suite summary at HEAD on 3.12. |
| WDG-002 | Tier the suite: `smoke` (<2 min), `full`, `nightly` (mutation + evals); document which tier gates what. | Markers + CI profiles + docs. |
| WDG-003 | Make full-suite runs emit a machine-readable summary artifact (count, failures, duration, commit) consumed by WDB-004. | Artifact produced in CI. |

## WD-H — Positioning Refresh and External Validation (P3)

**Source:** Competitor consolidation §Strategic Readout 1 and 3; reasoning
ledger §unknowns 4.

| ID | Work item | Acceptance gate |
| --- | --- | --- |
| WDH-001 | Stop producing new competitor surveys until WD-A/WD-B/WD-C ship (marginal value near zero; five cycles agree). | Next survey is the WS6-003 quarterly refresh or a publication-triggered one. |
| WDH-002 | First external-user evidence: 3–5 recorded outside-user sessions against the WDC-001 protocol. | Dated findings doc with non-maintainer users. |
| WDH-003 | Publish "when not to use TeaAgent" page (carried from WS6-005, still unmet). | Page lists IDE-first, hosted-delegation, and zero-config personas honestly. |

---

## Sequencing Logic

1. **Truth before features** (WD-A label pass + WD-B + WD-G): one short cycle
   that makes every later claim checkable. Nothing here is large; WDA-001 is
   hours, the validators are days.
2. **Wire in shadow mode** (WDA-002/003) while **simplifying the front door**
   (WD-C) — independent tracks, different files, parallelizable.
3. **Differentiate** (WD-D) once gating is real; **extend remote** (WD-E) once
   identity exists; **consolidate** (WD-F) opportunistically with each wiring
   PR.
4. **Validate externally** (WD-H) last — external users should meet the
   simplified, truth-aligned system, not the current one.

## Definition of Done for This Backlog

- No unlabeled unwired module in `teaagent/`.
- Roadmap, commit log, and import graph tell one story, enforced by CI.
- A stranger can use TeaAgent within ten minutes meeting ≤ 3 concepts.
- One eval gate and one remote approval are demonstrable with tests.
- The next dated review package can be produced mostly from validator output
  instead of manual git forensics.
