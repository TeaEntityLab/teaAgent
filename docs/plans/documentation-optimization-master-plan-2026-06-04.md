# Documentation Optimization Master Plan
# 2026-06-04

## Objective

Make TeaAgent's documentation corpus useful for daily users, maintainers, and
future agents by reducing status drift, clarifying current truth, and turning
review insight into executable work.

This plan optimizes for:

1. User trust.
2. Runtime and documentation stability.
3. Agent maintainability.
4. Risk visibility.
5. Cost-effective governance.

## Strategy

Do not aggressively merge historical docs. Historical evidence is valuable. The
high-ROI move is to create a small number of trusted entry points and make
volatile claims harder to stale silently.

## Investment Thesis

| Investment | Cost | ROI | Reason |
| --- | --- | --- | --- |
| Curated `docs/INDEX.md` | Low | High | Reduces search cost immediately. |
| Fix stale current-status claims | Low | High | Prevents direct user and maintainer confusion. |
| Operating model for claims and freshness | Low | High | Gives future agents reusable rules. |
| Guarded volatile prose claims | Medium | High | Prevents the most damaging doc/test contradictions. |
| Generated exhaustive docs index | Medium | Medium | Useful after the curated model stabilizes. |
| Full semantic stale-claim parser | High | Medium | Valuable but brittle; defer until targeted guards prove useful. |
| Mass merge of dated docs | High | Low | Destroys evidence and creates review risk. |

## Priority Summary

| Priority | Theme | Goal |
| --- | --- | --- |
| P0 | Current-truth repair | Remove known misleading status claims and create front doors. |
| P1 | Drift prevention | Add guardrails for volatile claims and status ownership. |
| P2 | Automation and scale | Generate inventories, link checks, stale dashboards, and release bundles. |

## P0 Work Packages

### DOCOPT-001: Curated Documentation Index

Status: Done in this pass.

Files:

- `docs/INDEX.md`

Acceptance criteria:

- Current-truth, governance, plan, evidence, security, reliability, guide, and
  reference front doors are linked.
- Dated-doc reading rules are explicit.
- Validation commands are listed.

### DOCOPT-002: Acceptance Status Repair

Status: Done in this pass.

Files:

- `docs/acceptance.md`

Acceptance criteria:

- The stale `3255 passed, 26 failed, 76 skipped` paragraph no longer appears as
  current status.
- Acceptance count remains `441 passed`.
- Full-suite evidence is clearly labeled as dated evidence, not current release
  proof.

### DOCOPT-003: Total-Review Evidence Cleanup

Status: Done in this pass.

Files:

- `docs/analysis/total-review-2026-06-04-INDEX.md`
- `docs/analysis/total-review-real-situation-2026-06-04.md`
- `docs/analysis/total-review-claim-verification-2026-06-04.md`
- `docs/analysis/total-review-critique-and-interrogation-2026-06-04.md`
- `docs/analysis/total-review-future-outlook-2026-06-04.md`

Acceptance criteria:

- English headings.
- No generation artifact tags.
- Baseline commit and current inventory are not conflated.

### DOCOPT-004: Module Index Supersession Note

Status: Done in this pass.

Files:

- `docs/modules/INDEX.md`

Acceptance criteria:

- The generated module index warns readers that its risk summary is inventory,
  not current closure truth.
- The stale memory-derived bug list is replaced with current front-door links.

### DOCOPT-005: Documentation Operating Model

Status: Done in this pass.

Files:

- `docs/governance/documentation-operating-model-2026-06-04.md`

Acceptance criteria:

- Defines claim classes, evidence hierarchy, freshness windows, guarded claims,
  merge policy, and documentation definition of done.

### DOCOPT-006: Roadmap H0 Documentation Hygiene Linkage

Status: Done.

Files:

- `docs/roadmap-status.md`
- `docs/plans/documentation-optimization-master-plan-2026-06-04.md`
- `docs/work-log/documentation-optimization-work-items-2026-06-04.md`

Acceptance criteria:

- H0 claim and risk hygiene explicitly references documentation-current-truth
  work.
- Doc-vs-HEAD guard work has a roadmap row or work-item link.

## P1 Work Packages

### DOCOPT-007: Guarded-Claim Registry

Status: Done.

Goal:

Create a small registry of volatile doc claims that must be checked by CI.

Initial claim types:

- Acceptance count.
- Full-suite result if stated as current.
- Provider count.
- Base dependency audit status.
- Optional-extra dependency audit status.
- Release-readiness claims.

Acceptance criteria:

- Registry format documented. ✅ (`docs/governance/guarded-claims-registry.md`)
- At least one prose full-suite claim is guarded. ✅ (`validate_guarded_claims` enforces full-suite failure prose on README, acceptance, daily-driver-current-status, roadmap-status)
- A deliberately stale acceptance/full-suite phrase fails the test. ✅ (`GUARDED_STALE_FAILURE_PROSE` regex rejects `N failed` with `N > 0`)

### DOCOPT-008: Module Risk Upward-Link Audit

Status: Proposed.

Goal:

Ensure P0/P1 module risks link to a central risk register, roadmap row, ticket,
or explicit defer decision.

Acceptance criteria:

- Every High/Critical module risk has an upward link or documented defer.
- `docs/modules/INDEX.md` distinguishes "inventory risk" from "active risk."

### DOCOPT-009: Roadmap Required-Field Guard

Status: Proposed.

Goal:

Prevent roadmap rows from losing owner, status, confidence, next gate, or exit
evidence fields.

Acceptance criteria:

- `docs/roadmap-status.md` table rows are parsed.
- Missing required fields fail a docs test.
- Status values map to `document-state-model.md`.

### DOCOPT-010: ADR Proposed-State Cleanup

Status: Done.

Goal:

Resolve the stale "six proposed ADRs" claim by checking the ADR source of truth
and closing the index drift.

Acceptance criteria:

- ADR 0010, 0012, 0014, 0015, 0017, and 0018 are no longer represented as
  Proposed in the ADR index.
- ADR 0025 reflects the implemented REPL and TUI controller state.
- ADR index categorizes ADR 0025 under chat surfaces.

### DOCOPT-011: Coverage Omit Re-Entry Plan

Status: Done.

Goal:

Give every coverage omit pattern a reason, owner surface, and target re-entry
sprint.

Acceptance criteria:

- 16 omit patterns listed.
- Each has reason, risk, owner surface, target, and first smoke-test candidate.
- `scripts/validate_docs_consistency.py` checks the ledger against
  `pyproject.toml`.

### DOCOPT-012: Optional Dependency Audit Lane

Status: Done.

Goal:

Preserve the zero-dependency base claim while governing optional extras such as
managed runtimes and web stacks.

Acceptance criteria:

- Base audit and optional-extra audit scopes are documented separately.
- Security workflow or nightly job has a clear optional-extra audit plan.
- Security workflow uses a base lockfile export for PR gating and a non-blocking
  optional-extra matrix for scheduled/manual visibility.

## P2 Work Packages

### DOCOPT-013: Generated Exhaustive Documentation Inventory

Status: Proposed.

Goal:

Generate an exhaustive `docs` inventory after the curated index stabilizes.

Acceptance criteria:

- Script generates deterministic inventory.
- Generated output says it is not the current-truth source.
- Stale generated output fails only when the generator is part of CI.

### DOCOPT-014: Link Health Check

Status: Proposed.

Goal:

Detect broken internal links across Markdown without blocking normal work on
low-risk historical docs.

Acceptance criteria:

- Internal links in current-truth docs are blocking.
- Historical evidence links are reported first, then optionally made blocking.

### DOCOPT-015: Documentation Aging Dashboard

Status: Proposed.

Goal:

Show which current-truth docs have not been reviewed after relevant code
changes.

Acceptance criteria:

- Current-truth docs have review triggers.
- Dashboard groups stale docs by owner surface.

### DOCOPT-016: Release Documentation Evidence Bundle

Status: Proposed.

Goal:

Before release, produce a compact evidence bundle covering test status,
dependency audit scope, roadmap status, known risks, and documentation freshness.

Acceptance criteria:

- Release checklist links the bundle.
- Bundle includes commands, dates, commits, and residual risks.

## Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| More docs create more drift | Medium | Every new doc must be linked from a front door or marked historical. |
| Validators become brittle | Medium | Guard high-value claims first; avoid parsing arbitrary prose. |
| Current-truth docs become too long | High | Move history to analysis; keep user docs operational. |
| Generated indexes become unreadable | Medium | Keep curated index primary; generated inventory secondary. |
| Module risks stay unmanaged | High | Require upward links for P0/P1 module risks. |
| Roadmap remains stale | High | Add documentation-current-truth rows to H0 and require exit evidence. |

## Verification Plan

Run after this documentation pass:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

Recommended later:

```bash
cx overview docs --limit 120
cx symbols --kind heading --name '*Status*' --limit 120
cx symbols --kind heading --name '*Risk*' --limit 120
cx symbols --kind heading --name '*Roadmap*' --limit 120
```

## Exit Criteria

Documentation optimization is successful when:

1. A reader can find current truth from `docs/INDEX.md` in less than five
   minutes.
2. No stable current-truth doc contains a known stale test, safety, release, or
   roadmap claim.
3. High-severity risks have owners or explicit defer decisions.
4. Roadmap rows have exit evidence.
5. Dated evidence remains preserved but clearly scoped.
6. Future agents can add docs without inventing a new status system.
