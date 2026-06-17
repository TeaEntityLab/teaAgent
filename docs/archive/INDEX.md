# Historical Evidence Index
# 2026-06-17

> **Claim class:** evidence-snapshot
> **Owns:** docs
> **Last reviewed:** 2026-06-17
> **Review trigger:** New dated review packages, supersession links, completed plans, or front-door documentation changes.

This index keeps historical documentation discoverable without asking every
reader or agent to reread it as current truth. It does not move, delete, or
rewrite the original evidence files. For current truth, start at
[docs/INDEX.md](../INDEX.md).

## Reader Contract

| Question | Use |
| --- | --- |
| What should I trust now? | [docs/INDEX.md](../INDEX.md), [Daily-Driver Current Status](../daily-driver-current-status.md), [Roadmap Status](../roadmap-status.md), and active ticket indexes. |
| Why was a decision made? | The dated package below that matches the date/topic. |
| Is an old finding still open? | Prefer current ledgers first; use the dated package only for provenance. |
| Where is every file? | [Docs Inventory](../generated/docs-inventory.md). |

## Package Map

| Package | Read when | Primary index or entry | Current-truth replacement |
| --- | --- | --- | --- |
| Harness-first direction trail | You need the reasoning that led to owner-operator scope. | [Intent Critical Review](../analysis/intent-critical-review-and-worklist-2026-06-12.md), [Intent Reassessment](../analysis/intent-reassessment-and-worklist-2026-06-11.md), [Intent Verification Delta](../analysis/intent-verification-delta-2026-06-12.md) | [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) |
| June 10 system critical review | You need the latest broad dated audit package. | [System Critical Review 2026-06-10](../analysis/system-critical-review-2026-06-10-INDEX.md) | [Work Direction Execution Index](../plans/work-direction-execution-index-2026-06-10.md), [Roadmap Status](../roadmap-status.md) |
| June 6 system critical review | You need the prior broad audit baseline. | [System Critical Review 2026-06-06](../analysis/system-critical-review-2026-06-06-INDEX.md) | [System Critical Review 2026-06-10](../analysis/system-critical-review-2026-06-10-INDEX.md) |
| June 4 total review | You need the cross-examination of the supplied project analysis. | [Total Review 2026-06-04](../analysis/total-review-2026-06-04-INDEX.md) | [System Critical Review 2026-06-10](../analysis/system-critical-review-2026-06-10-INDEX.md) |
| June 1 daily-driver review | You need the early daily-driver evidence trail. | [Daily-Driver Review Package](../analysis/daily-driver-review-INDEX-2026-06-01.md) | [Daily-Driver Current Status](../daily-driver-current-status.md), [Operator Friction Log](../work-log/operator-friction-log.md) |
| Documentation system package | You need why the docs corpus has front doors, inventories, aging checks, and claim rules. | [Documentation State Review](../analysis/documentation-state-review-2026-06-04.md), [Documentation Critical Questioning](../reviews/documentation-critical-questioning-2026-06-04.md), [Documentation Optimization Master Plan](../plans/documentation-optimization-master-plan-2026-06-04.md), [Documentation Optimization Work Items](../work-log/documentation-optimization-work-items-2026-06-04.md) | [Documentation Operating Model](../governance/documentation-operating-model-2026-06-04.md), [Documentation Taxonomy And Ownership](../governance/doc-taxonomy-and-ownership.md), this index |
| Competitor and market surveys | You need historical market/UX hypotheses, not current positioning. | [Competitor Analyses vs Self Consolidation](../analysis/competitor-analyses-vs-self-consolidation-2026-06-10.md), [Competitor Signal Survey 2026-06-06](../analysis/competitor-signal-survey-2026-06-06.md), [Community Agent Pain Points Survey](../analysis/community-agent-pain-points-survey-2026-06-05.md) | [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md); refresh sources before external claims. |
| Dynamic skill and long-result work | You need the evidence behind dynamic skill quarantine, lifecycle, and long-result concerns. | [Dynamic Skill Audit](../analysis/dynamic-skill-generation-and-long-result-audit-2026-06-05.md), [Dynamic Skill Critical Questioning](../reviews/dynamic-skill-critical-questioning-2026-06-05.md), [Dynamic Skill Work Items](../plans/dynamic-skill-and-long-result-work-items-2026-06-05.md) | Active skill docs and tests; use current code before dated findings. |
| Seven control loops package | You need the historical design hypothesis for spec, review, memory, and goal loops. | [Seven Control Loops Product Direction](../strategy/seven-control-loops-product-direction-2026-06-05.md), [Seven Control Loops Critical Questioning](../reviews/seven-control-loops-critical-questioning-2026-06-05.md), [Seven Control Loops Work Items](../plans/seven-control-loops-work-items-2026-06-05.md) | Current architecture, active ticket indexes, and owner friction evidence. |

## High-Overlap Clusters

These clusters are intentionally indexed instead of merged. They preserve
different dates and evidence scopes, but only one current source should answer
today's operational question.

| Cluster | Files | Treatment |
| --- | --- | --- |
| Daily-driver status and plans | `analysis/daily-driver-*`, `plans/daily-driver-*`, `reviews/daily-driver-*` | Keep as historical evidence; current behavior lives in [Daily-Driver Current Status](../daily-driver-current-status.md). |
| Competitor and positioning surveys | `analysis/competitor-*`, `analysis/*market*`, `strategy/competitive-*` | Keep as dated hypothesis/evidence; do not cite externally without same-day refresh. |
| Documentation governance work | `analysis/documentation-*`, `reviews/documentation-*`, `plans/documentation-*`, `work-log/documentation-*` | Keep the package for provenance; current rules live in governance docs and this index. |
| Broad system reviews | `analysis/system-critical-review-*`, `analysis/total-review-*`, `analysis/engineering-*`, `analysis/risk-and-trust-*` | Prefer the latest package index, then drill into older packages only for deltas. |
| Completed implementation plans | Dated `plans/*-2026-*` and `work-log/*-2026-*` | Keep as execution receipts; current execution truth lives in ticket and roadmap indexes. |

## Consolidation Queue

These are not moved by this archive index. They are the next best shrink targets
because they overlap by purpose or title. Preserve the stronger canonical source
and turn the weaker source into a short pointer or recipe-specific supplement.

| Priority | Overlap | Best treatment |
| --- | --- | --- |
| 1 | `docs/DOCUMENTATION_STRATEGY.md`, `docs/governance/documentation-operating-model-2026-06-04.md`, `docs/governance/doc-taxonomy-and-ownership.md` | Keep the operating model and taxonomy as canonical; shrink `DOCUMENTATION_STRATEGY.md` into a stable overview/pointer. |
| 2 | `docs/api/integration-guide.md`, `docs/guides/integration-guide.md` | Keep API guide as reference; keep user guide as recipes and link to the reference for contract details. |
| 3 | `docs/troubleshooting.md`, `docs/ops/troubleshooting.md`, `docs/daily-driver-troubleshooting.md` | Keep root troubleshooting as canonical; shrink ops to ops-only incidents; keep daily-driver page narrow. |
| 4 | `docs/use-cases.md`, `docs/guides/use-cases.md` | Rename or reframe root `use-cases.md` as traceability/evidence; keep `guides/use-cases.md` user-facing. |
| 5 | `docs/permission-and-approval-playbook.md`, `docs/guides/approval-policy-design.md` | Keep playbook as operational truth; trim duplicated mode/grant material from the design guide. |
| 6 | `docs/guides/performance-tuning.md`, `docs/ops/performance-tuning.md` | Keep both audiences, but trim repeated tuning knobs and cross-link one canonical explanation. |

## Minimality Rules

- Do not add a new dated analysis doc when an existing package index can receive
  a row or supersession note.
- Do not link individual historical files from [docs/INDEX.md](../INDEX.md)
  unless they are the latest package index or a current direction record.
- If a historical file contradicts current code or current truth docs, add a
  supersession note to the file or this index; do not rewrite the old claim.
- If two active docs answer the same current question, choose one canonical
  source and turn the other into a pointer.

## Validation

After changing this index or front-door documentation, run:

```bash
python3 scripts/verify_docs.sh
```
