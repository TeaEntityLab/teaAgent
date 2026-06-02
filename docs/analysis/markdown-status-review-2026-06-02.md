# Markdown Status Review
# 2026-06-02

This review records the repository Markdown status after the docs expansion and
the `cx`-based documentation survey.

## Scope

Reviewed:

- Repository Markdown inventory.
- `docs/analysis`, `docs/plans`, and `docs/modules` structure.
- Existing status and roadmap entry points.
- Existing documentation consistency validation.
- Current git status for Markdown files before this governance implementation.

Not reviewed:

- Live external forum or market feedback.
- Runtime correctness of every issue referenced by historical docs.
- Full link validation across all Markdown files.

## Commands used

```bash
cx overview docs --limit 100
cx overview docs/analysis --limit 120
cx overview docs/plans --limit 120
cx overview docs/modules --limit 120
cx symbols --kind heading --name '*Risk*' --limit 100
cx symbols --kind heading --name '*Roadmap*' --limit 100
cx symbols --kind heading --name '*Status*' --limit 100
cx symbols --kind heading --name '*Issue*' --limit 100
rg --files -g '*.md'
find docs -maxdepth 3 -type d
python3 scripts/validate_docs_consistency.py
```

`cx` required access to its local index/cache outside the default sandbox. The
operations were read-only and used for documentation discovery.

## Inventory facts

| Fact | Evidence |
|------|----------|
| Markdown file count | `rg --files -g '*.md' | wc -l` returned 420. |
| Markdown line count | `rg --files -g '*.md' | xargs wc -l` returned about 61,050 total lines. |
| Heaviest directories by file count | `docs/modules`, `docs/analysis`, `docs/plans`. |
| `docs/modules` shape | `cx overview docs/modules` found 28 module directories plus indexes/maps. |
| `docs/analysis` shape | `cx overview docs/analysis` found 52 files with many dated review layers. |
| `docs/plans` shape | `cx overview docs/plans` found 42 plan/ticket files. |
| Existing docs check | `python3 scripts/validate_docs_consistency.py` passed. |
| Dirty tracked Markdown before implementation | `git status --short` showed only `AGENTS.md` modified. |

## Current front doors

| Question | Current front door |
|----------|--------------------|
| What can a daily user trust now? | `docs/daily-driver-current-status.md` |
| How should the daily-driver review package be read? | `docs/analysis/daily-driver-review-INDEX-2026-06-01.md` |
| What is the execution queue? | `docs/plans/ticket-plans/index.md` |
| What is the roadmap state? | `docs/roadmap-status.md` |
| Which module owns which risk? | `docs/modules/INDEX.md` |
| How should docs be maintained? | `docs/governance/doc-maintenance-policy-2026-06-02.md` |

## Findings

### MSR-001: The corpus is large but not shapeless

The Markdown tree already has recognizable layers: guides, analysis, plans,
specs, module docs, ADRs, security, reliability, governance, ops, and reviews.
The right fix is not mass deletion. The right fix is stronger entry points and
status rules.

State: Active.

Recommended action: keep dated docs as evidence; maintain a small set of active
front doors.

### MSR-002: Status vocabularies drift across document families

Observed vocabularies include:

- `FIXED`, `OPEN`, `PARTIAL`, `OPEN(test)` in findings ledgers.
- `Active`, `Partially fixed`, `Verify/close`, `Fixed`, `Superseded` in daily-driver plans.
- `Complete`, `In Progress`, `Pending`, `Blocked`, `On Hold` in roadmap files.
- `Stale`, `Archived`, `Current`, and ad hoc phrases in analysis files.

State: Active.

Recommended action: add `docs/governance/document-state-model.md` and map older
labels to canonical states instead of editing historical docs.

### MSR-003: Risk material is split across useful but overlapping files

Risk information appears in:

- Dated daily-driver risk registers.
- Security risk register and threat model.
- Reliability FMEA.
- Module `risks.md` files.
- Defeat scenario reports.
- Ticket plans.
- Roadmap/backlog files.

State: Active.

Recommended action: define a risk-to-ticket-to-roadmap workflow. P0/P1 risks in
module docs should link upward to a central register, ticket, or explicit defer
decision.

### MSR-004: Current docs checks pass, but they do not enforce governance flow

The existing consistency script checks important claims, provider counts, dates,
acceptance counts, and required sections. It does not enforce the full lifecycle
from risk discovery to roadmap closure.

State: Proposed.

Recommended action: keep current checks unchanged for this pass. Consider later
validators for canonical status labels, required risk fields, and front-door link
coverage.

### MSR-005: Some large historical docs should remain historical

Large dated reports, market surveys, dependency audits, FMEA documents, and
security reviews are evidence snapshots. Merging them into a single current file
would destroy useful timeline context.

State: Active.

Recommended action: use supersession notes and indexes instead of destructive
merges.

## Recommended consolidation targets

| Target | Recommendation |
|--------|----------------|
| User-facing daily truth | Keep `docs/daily-driver-current-status.md` canonical. |
| Finding status truth | Keep the daily-driver findings ledger or create a dated successor. |
| Ticket execution truth | Keep `docs/plans/ticket-plans/index.md` canonical for ticket order. |
| Roadmap truth | Keep `docs/roadmap-status.md` canonical and link back to ticket plans. |
| Module risk truth | Keep module `risks.md` files local, with upward links for P0/P1. |
| Historical reviews | Preserve dated files; add supersession notes only when needed. |
| Governance rules | Keep `doc-maintenance-policy` short; move detailed rules to dedicated governance docs. |

## Files that should remain historical

Keep these as evidence snapshots unless a maintainer explicitly requests archival
or consolidation:

- Dated market and community feedback surveys.
- Dated daily-driver review passes.
- Dependency and security audits.
- FMEA and threat-model reports.
- Defeat scenario reports.
- ADRs and rejected-alternative records.

## Implementation recommendation

Add the following governance layer:

- `docs/governance/document-state-model.md`.
- `docs/governance/risk-issue-roadmap-workflow.md`.
- `docs/governance/doc-taxonomy-and-ownership.md`.

Then update the existing front doors to link to it:

- `docs/governance/doc-maintenance-policy-2026-06-02.md`.
- `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`.
- `docs/plans/daily-driver/README.md`.

## Residual risks

- `cx` heading discovery confirms structure, not semantic truth.
- The corpus still has many overlapping dated docs; the new rules reduce future
  drift but do not automatically clean every old contradiction.
- A future validator may be needed if status drift continues.
- Owner fields are still mostly owner surfaces, not named people.
