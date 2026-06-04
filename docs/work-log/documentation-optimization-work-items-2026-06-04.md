# Documentation Optimization Work Items
# 2026-06-04

## Purpose

This work log turns the documentation-state review and critical questioning
report into concrete tasks. It should be updated when tasks move state.

Canonical states follow [Document State Model](../governance/document-state-model.md).

## Work Item Ledger

| ID | Priority | State | Work item | Dependencies | Acceptance criteria |
| --- | --- | --- | --- | --- | --- |
| DOW-001 | P0 | Fixed | Add curated `docs/INDEX.md` front door. | None | Index links current truth, evidence, governance, plans, security, guides, and validation. |
| DOW-002 | P0 | Fixed | Remove stale full-suite failure prose from `docs/acceptance.md`. | None | No current paragraph claims `26 failed`; acceptance count still says `441 passed`. |
| DOW-003 | P0 | Fixed | Clean total-review package into English durable evidence. | None | No non-English headings or generation artifact tags remain in total-review docs. |
| DOW-004 | P0 | Fixed | Add supersession note to `docs/modules/INDEX.md`. | None | Generated risk inventory no longer looks like current closure truth. |
| DOW-005 | P0 | Fixed | Add documentation-state review. | DOW-001 | Review records inventory, findings, current front-door model, and consolidation recommendations. |
| DOW-006 | P0 | Fixed | Add critical questioning review. | DOW-005 | Review challenges volume, guarded docs, history/current ambiguity, and roadmap-risk drift. |
| DOW-007 | P0 | Fixed | Add documentation operating model. | DOW-005 | Defines claim classes, evidence hierarchy, freshness windows, source-of-truth matrix, guarded claims, and DoD. |
| DOW-008 | P0 | Fixed | Add master optimization plan. | DOW-005, DOW-007 | Plan ranks P0/P1/P2 work with ROI, risk, and acceptance criteria. |
| DOW-009 | P0 | Fixed | Add this work-item ledger. | DOW-008 | Ledger records tasks, state, dependencies, and acceptance criteria. |
| DOW-010 | P0 | Fixed | Link new documentation governance package from front-door docs. | DOW-001, DOW-007 | Governance README, maintenance policy, current status, daily-driver index, and daily-driver plan index link the new docs. |
| DOW-011 | P0 | Fixed | Update roadmap H0 to include documentation-current-truth work. | DOW-008 | `roadmap-status.md` references documentation optimization and doc-vs-HEAD guard work. |
| DOW-012 | P0 | Proposed | Add a guarded-claim registry for volatile prose facts. | DOW-007 | A stale full-suite prose claim can fail CI. |
| DOW-013 | P1 | Proposed | Audit High/Critical module risks for upward links. | DOW-004 | Every P0/P1 module risk links to central risk, roadmap, ticket, or defer decision. |
| DOW-014 | P1 | Proposed | Add required-field guard for roadmap rows. | DOW-011 | Rows missing owner/status/confidence/next gate/exit evidence fail docs tests. |
| DOW-015 | P1 | Fixed | Resolve stale proposed-ADR status claims. | None | ADR 0010, 0012, 0014, 0015, 0017, and 0018 are closed in the ADR index; ADR 0025 reflects implemented REPL/TUI controller state. |
| DOW-016 | P1 | Fixed | Document coverage omit re-entry plan. | None | Each omit pattern has reason, owner surface, target sprint, smoke-test candidate, and validator coverage. |
| DOW-017 | P1 | Fixed | Document optional-extra dependency audit lane. | None | Base and optional-extra audit scopes are separated, scheduled, and reflected in the security workflow. |
| DOW-018 | P1 | Proposed | Create successor findings ledger for June 4 status. | DOW-005 | Stale June 1 ledger rows are mapped to current state or superseded. |
| DOW-019 | P1 | Proposed | Add "current truth" banners to stable front doors. | DOW-007 | Current truth docs clearly say what they own and what they do not own. |
| DOW-020 | P1 | Proposed | Shorten daily-user guides that contain too much history. | DOW-019 | Guides answer command choice and recovery first; history moves to analysis. |
| DOW-021 | P2 | Proposed | Generate exhaustive docs inventory. | DOW-001 | Generated inventory is deterministic and secondary to curated index. |
| DOW-022 | P2 | Proposed | Add internal link health check. | DOW-021 | Current-truth broken links are blocking; historical links start as warnings. |
| DOW-023 | P2 | Proposed | Add documentation aging dashboard. | DOW-019 | Current-truth docs show last-reviewed and stale triggers. |
| DOW-024 | P2 | Proposed | Add release documentation evidence bundle. | DOW-012, DOW-014 | Release checklist links dated evidence bundle with commands, commit, and residual risks. |
| DOW-025 | P2 | Proposed | Add competitor survey freshness policy. | None | Positioning claims name source date or explicitly state "not refreshed." |
| DOW-026 | P2 | Proposed | Add command-snippet smoke inventory. | DOW-020 | High-value guide commands are either smoke tested or marked manual. |
| DOW-027 | P2 | Proposed | Normalize old status labels in active indexes. | DOW-007 | Active indexes map old labels to canonical states without rewriting dated evidence. |
| DOW-028 | P2 | Proposed | Add docs ownership field to stable current-truth docs. | DOW-019 | Owner surface appears in current-truth docs or their index row. |
| DOW-029 | P2 | Proposed | Review non-English or mixed-language durable docs. | None | Durable governance/current docs are English unless explicitly localization-focused. |
| DOW-030 | P2 | Proposed | Create a periodic documentation audit cadence. | DOW-023 | Cadence triggers after release, roadmap change, or trust-sensitive code changes. |

## Immediate Sequence

1. Run validation commands.
2. If validation passes, leave DOW-012 as the first code-backed follow-up.
3. Use DOW-013 as the first risk-governance audit follow-up.

## Human Review Gates

Human review is required before:

- Marking roadmap claim-hygiene work complete.
- Changing security, approval, or release-readiness claims.
- Deleting dated evidence documents.
- Making validators block release on new categories.
- Reclassifying High/Critical risks as Fixed.

## Verification Commands

Run after this pass:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

Optional discovery checks:

```bash
cx overview docs --limit 120
cx symbols --kind heading --name '*Status*' --limit 120
cx symbols --kind heading --name '*Risk*' --limit 120
cx symbols --kind heading --name '*Roadmap*' --limit 120
```

## Notes

- DOW-001 through DOW-009 are fixed in the same documentation pass that created
  this ledger.
- DOW-012 remains the highest-value next documentation-validator task because it
  generalizes guarded claims beyond coverage and dependency audit scope.
- DOW-013 is the highest-value risk-governance follow-up because module risk
  detail currently exceeds central ownership.
