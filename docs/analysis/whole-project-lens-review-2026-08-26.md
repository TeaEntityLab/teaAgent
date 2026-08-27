# Whole-Project Lens Review — 2026-08-26

> **Claim class:** Dated panel evidence. Verdicts are advisory synthesis over
> repository evidence; they do not change roadmap authority or prove runtime
> behavior. Adopted wording is pinned by
> `tests/test_docs_consistency.py::test_whole_project_review_candidate_adoption_state`.
>
> **Target:** whole-project features, goals, intents, and worth-doing next
> steps at commit `39358ad` (clean tree).
>
> **Method:** Parallel Lens Review packet protocol — one shared evidence packet
> (O1–O14), six independent read-only lenses, coordinator-executed
> deterministic checks, candidate adjudication C1–C6.
>
> **Action register:** G-P2-9
>
> **Falsifiability:** this record is wrong if an adopted candidate's wording is
> absent from its named surface, if a rejected candidate ships without
> re-litigation, or if a lens verdict below misquotes the lens deliverable.

## Panel Consensus

- **Decision:** `AGREE WITH CHANGES` from all six lenses on the packet's
  direction I3 (EFX live proof → ADR-0031 preparation → doc-truth repairs →
  north-star visibility → nothing new).
- **Use-case recommendation:** `adopt` for the doc-truth batch (C1–C5 as
  adjudicated below); `owner-gated` for all runtime-affecting work (EFX live
  proof, ADR-0031 decision, any deletion).

Lenses: EvidenceAuditor, ArchitectureReviewer, OwnerValueReviewer,
GovernanceReviewer, ReproducibilityEngineer, StrategicSynthesis — all ran as
read-only subagents against the shared packet; three deliverables were
recovered from schema-coerced yields via artifact fields and two via DM-wake
(protocol tier 1). No live provider calls occurred; role labels are lens
names, not model identities.

## Shared Findings

1. **Acceptance posture drift (O4).** `docs/maturity-matrix.md` claimed
   `88 test files / 276 collected tests` while reality is **131 files / 669
   collected** (`pytest tests/acceptance --collect-only -q`). Failed the
   number/text evidence dimension; no validator pinned these numbers (O14).
2. **Malformed parity table (O5).** `docs/use-cases.md` market-standard table
   declared 8 columns; all 13 rows carry 5 cells, so test filenames rendered
   under "Blast Radius" and three governance columns were silently empty —
   an extrapolation failure (implied vetting that never existed).
3. **North-star goals untracked (O6/O7).** Owner-ratified G1–G6 had zero
   status rows in any current-truth surface. G3 ("one event spine") was
   rescoped by owner-reviewed M4/M5 work-logs (enforcement bridge assessed
   unsuitable; spine is a typed observability read-model with audit
   dual-write) — but the rescope was recorded nowhere current-truth.
4. **Subpackage reality (ArchitectureReviewer).** Sampled classification:
   `teaagent/tournament/` (6 files, 1,064 LOC) **dormant** — imported only by
   `teaagent/swarm.py`, which has no production callers; `marketplace/`,
   `gateway/`, `html_dashboard/` **frozen-but-wired** (CLI-reachable, tested).
   ADR-0029 Option D is a validated, reusable deletion-review template.
5. **Owner-value asymmetry (OwnerValueReviewer).** Zero of C1–C6 map to
   recorded owner friction; all are truth-hygiene or agent-governance assets.
   The only action that expands daily capability is owner-gated EFX live
   proof. Doc-truth fixes are justified by DR-006 "truth before features",
   not by ergonomics.
6. **Front-door coherence (StrategicSynthesis).** product-contract, README,
   and harness-first tell one consistent owner-operator story; no current-truth
   surface sells retired intents (enterprise/team/external adoption) as
   present-tense. Residual cosmetic tension: README's "Enterprise NIST
   mapping" artifact links beside "not an enterprise platform" disclaimers —
   accepted as-is (artifact labels, not capability claims).

## Candidate Adoption Ledger

| ID | Candidate | Status | Evidence / adopted surface | Next action or trigger |
| --- | --- | --- | --- | --- |
| C1 | Shrink use-cases market-standard table header to the 5 real columns | **adopted** | `docs/use-cases.md` header `\| Use Case \| User Goal \| Required Acceptance Coverage \| Priority \| Status \|`; no fabricated blast-radius data | none |
| C2 | Refresh maturity-matrix acceptance posture + deterministic pin | **adopted** | `docs/maturity-matrix.md` states 131 files / 669 collected; cross-doc guard `test_maturity_matrix_acceptance_counts_match_acceptance_doc`; registry class extended in `docs/governance/guarded-claims-registry.md` | guard fails if counts drift from `docs/acceptance.md` or the file glob |
| C3 | North-Star Goals (G1–G6) status section in roadmap-status | **adopted** | `docs/roadmap-status.md` `## North-Star Goals (G1-G6)`; G3 marked "Rescoped by owner decision" citing M4/M5 work-logs; pinned by `test_roadmap_status_north_star_goals_section` | update rows only with cited evidence; G1/G2 remain Unmeasured until owner-run metrics exist |
| C4 | Product-contract permission bullet gains external-effect gating + review bump | **adopted** (GovernanceReviewer dissent recorded below) | `docs/product-contract.md` permission bullet names fail-closed external-effect gating (EFX-002), Last reviewed 2026-08-26; wording makes no live-proof claim | revisit wording when EFX live proof lands |
| C5 | Dormant-surface deletion review as trigger-only lane | **adopted (trigger row only)** | `docs/plans/current-roadmap-execution-plan-2026-08-26.md` Phase 3 table row "Dormant-surface deletion review" citing ADR-0029 Option D contract | activates only when the owner names a surface with cited friction or maintenance cost; no deletion scheduled |
| C6 | G1 measurement cadence note in friction log | **rejected** | none — friction intake stays event-driven; owner already attests ad hoc (2026-07-22) | re-litigate only if the owner requests a cadence |

## Disagreements / Residual Risks

- **C4 split (4 adopt / 1 defer).** GovernanceReviewer preferred deferring any
  constitution-tier edit until EFX live proof to avoid maturity-signal churn.
  Adopted anyway because the bullet was factually incomplete about landed,
  tested fail-closed behavior; the adopted wording claims gating exists, not
  that live-provider safety is proven. Risk accepted: one extra
  constitution-tier review cycle.
- **Proactive vs trigger-only cleanup.** ArchitectureReviewer's strongest
  objection: leaving ~30 frozen/dormant subpackages wired and tested is an
  ongoing maintenance tax (every typing/refactor pass processes dead surface
  like `tournament/`), and a proactive cleanup lane would fit the
  thin-harness invariant better. Held at trigger-only per DR-006 — no owner
  friction citation exists yet. The C5 lane makes activation cheap.
- **Meta-work objection (StrategicSynthesis/EvidenceAuditor).** Recursive
  document perfectionism can simulate progress; the panel itself is meta-work.
  Mitigation adopted: this batch is docs+tests only, bounded, and the
  execution plan's "empty scheduled queue is an acceptable result" stays
  binding. No new review ritual was created (C6 rejected).
- **G1/G2 remain unmeasured.** The two owner-experience goals have no metric;
  their rows say so honestly. Fabricating a measurement harness was rejected
  as maintainer-vanity (OwnerValueReviewer).

## Worth-Doing Next (panel-ranked)

1. **EFX-001..003 live-provider evidence run** `[owner-gated]` — DR-006 P0
   governance-gap; execution plan Phase 1. The only item that expands daily
   capability.
2. **ADR-0031 H4 evidence packet before 2026-09-12** `[agent-preparable]` —
   receipts/coverage/latency/rollback via existing `scripts/*h4*`; owner
   decides promote/extend/revert.
3. **Doc-truth batch C1/C2/C4** `[done in this change]`.
4. **North-star visibility C3** `[done in this change]`.
5. **Queue freeze** — reject speculative work; empty queue acceptable
   (execution plan §7).

## Evidence Actually Checked

- Coordinator-executed: `git status -sb`; `pytest tests/acceptance
  --collect-only -q` (669); glob count (131); `docs/use-cases.md:107-124:raw`;
  tier counts from `docs/generated/docs-inventory.md` (constitution 8 /
  evidence 6 / archive 259); top-level CLI roster via `build_parser()` (60
  groups; golden-path commands exist); grep sweeps for G1–G6, dual-write,
  HookRegistry; `wc -l` hot files.
- Lens-read: m4/m5 work-logs, ADR-0029 + disposition spec, DR-006, action
  register rules (`G-P0-2` Done → new ID required), `high_risk_paths.yaml`
  (no candidate touches high-risk paths), friction log entries F2–F8,
  `_events.py` header, import graphs for 4 sampled subpackages.
- Not executed: no live provider calls, no full-suite run in this batch
  (docs+tests only; focused guards run instead), no deletion.

## Related documents

| Document | Role |
| --- | --- |
| [Roadmap Status](../roadmap-status.md) | owns G1–G6 status rows added by C3 |
| [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) | ratified G1–G6 wording (unchanged) |
| [Current Roadmap Execution Plan](../plans/current-roadmap-execution-plan-2026-08-26.md) | Phase 3 trigger table extended by C5 |
| [Roadmap Rethink Lens Review](roadmap-rethink-lens-review-2026-08-26.md) | prior panel (EFX scope); method precedent |
| [Guarded Claims Registry](../governance/guarded-claims-registry.md) | acceptance-count guard class extended by C2 |
