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
| DOW-012 | P0 | Fixed | Add a guarded-claim registry for volatile prose facts. | DOW-007 | A stale full-suite prose claim can fail CI. |
| DOW-013 | P1 | Fixed | Audit High/Critical module risks for upward links. | DOW-004 | Every P0/P1 module risk links to central risk, roadmap, ticket, or defer decision. |
| DOW-014 | P1 | Fixed | Add required-field guard for roadmap rows. | DOW-011 | Rows missing owner/status/confidence/next gate/exit evidence fail docs tests. |
| DOW-015 | P1 | Fixed | Resolve stale proposed-ADR status claims. | None | ADR 0010, 0012, 0014, 0015, 0017, and 0018 are closed in the ADR index; ADR 0025 reflects implemented REPL/TUI controller state. |
| DOW-016 | P1 | Fixed | Document coverage omit re-entry plan. | None | Each omit pattern has reason, owner surface, target sprint, smoke-test candidate, and validator coverage. |
| DOW-017 | P1 | Fixed | Document optional-extra dependency audit lane. | None | Base and optional-extra audit scopes are separated, scheduled, and reflected in the security workflow. |
| DOW-018 | P1 | Fixed | Create successor findings ledger for June 4 status. | DOW-005 | Stale June 1 ledger rows are mapped to current state or superseded. |
| DOW-019 | P1 | Fixed | Add "current truth" banners to stable front doors. | DOW-007 | Current truth docs clearly say what they own and what they do not own. |
| DOW-020 | P1 | Fixed | Shorten daily-user guides that contain too much history. | DOW-019 | Guides answer command choice and recovery first; history moves to analysis. |
| DOW-021 | P2 | Fixed | Generate exhaustive docs inventory. | DOW-001 | Generated inventory is deterministic and secondary to curated index. |
| DOW-022 | P2 | Fixed | Add internal link health check. | DOW-021 | Current-truth broken links are blocking; historical links start as warnings. |
| DOW-023 | P2 | Fixed | Add documentation aging dashboard. | DOW-019 | Current-truth docs show last-reviewed and stale triggers. |
| DOW-024 | P2 | Fixed | Add release documentation evidence bundle. | DOW-012, DOW-014 | `scripts/build_release_docs_evidence_bundle.py` → `docs/generated/release-docs-evidence.md`; linked from release checklist. |
| DOW-025 | P2 | Fixed | Add competitor survey freshness policy. | None | Positioning claims name source date or explicitly state "not refreshed." |
| DOW-026 | P2 | Fixed | Add command-snippet smoke inventory. | DOW-020 | `generate_command_snippet_inventory.py` + registry; CI `--check` via verify_docs.sh. |
| DOW-027 | P2 | Fixed | Normalize old status labels in active indexes. | DOW-007 | INDEX status vocabulary + work-log canonical state validator. |
| DOW-028 | P2 | Fixed | Add docs ownership field to stable current-truth docs. | DOW-019 | Aging dashboard + validator enforce Owns/Owner banners on scanned docs. |
| DOW-029 | P2 | Fixed | Review non-English or mixed-language durable docs. | None | Governance/current-truth language scan in validate_docs_consistency.py. |
| DOW-030 | P2 | Fixed | Create a periodic documentation audit cadence. | DOW-023 | documentation-audit-cadence doc linked from release checklist + verify_docs.sh. |

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

## Status Log

- 2026-06-04 — **DOW-012 Fixed.** Added
  `docs/governance/guarded-claims-registry.md` and a `validate_guarded_claims`
  guard in `scripts/validate_docs_consistency.py` that fails CI when a guarded
  current-truth doc keeps stale non-zero full-suite failure prose. Covered by
  `tests/test_docs_consistency.py::test_validate_guarded_claims_detects_stale_failure_prose`
  and three sibling cases.
- 2026-06-04 — **DOW-013 Fixed.** Audited all module risk docs; added an
  `Upstream` link column / `Upstream:` line to every High/Critical (and adjacent
  Medium-high) module risk so each traces to the central risk register,
  phase-0 trust-repair brief, or severity rubric.

## Notes

- DOW-001 through DOW-009 are fixed in the same documentation pass that created
  this ledger.
- DOW-012 remains the highest-value next documentation-validator task because it
  generalizes guarded claims beyond coverage and dependency audit scope.
- 2026-06-06 — **DOW-014 Fixed.** `validate_roadmap_required_fields` in
  `scripts/validate_docs_consistency.py` parses roadmap tables and fails when
  owner/status/confidence/next gate/exit-or-risk columns are empty or status is
  unrecognized. Covered by `tests/test_docs_consistency.py` roadmap guard tests.
- 2026-06-06 — **DOW-018 Fixed.** Added
  `docs/analysis/active-findings-status-ledger-2026-06-06.md` as the current
  findings roll-up; June 1 ledger carries a supersession note.
- 2026-06-06 — **DOW-019 Fixed.** Current-truth banners added to
  `daily-driver-current-status.md`, `roadmap-status.md`, `acceptance.md`, and
  `plans/ticket-plans/index.md`.
- 2026-06-06 — **DOW-020 Fixed.** Removed stale TUI cost-migration wording from
  `tui-daily-driver-guide.md`; guide now points to current-truth docs for status.
- 2026-06-06 — **DOW-021 Fixed.** Added `scripts/generate_docs_inventory.py` and
  `docs/generated/docs-inventory.md` with CI freshness check via
  `validate_docs_consistency.py`.
- 2026-06-06 — **DOW-022 Fixed.** Expanded `validate_doc_cross_references` to
  cover additional current-truth docs and emit non-blocking warnings for
  historical evidence directories.
- 2026-06-06 — **DOW-025 Fixed.** Quarterly competitor refresh landed as
  [competitor-signal-survey-2026-06-06.md](../analysis/competitor-signal-survey-2026-06-06.md)
  with synchronized survey dates across matrix, catalog, architecture, and
  use-cases docs.
- 2026-06-06 — **DOW-023 Fixed.** Added `scripts/report_docs_aging.py`,
  `docs/generated/docs-aging-dashboard.md`, review triggers on current-truth
  docs, and CI freshness check via `validate_docs_consistency.py`.
- 2026-06-06 — **WS1-001 MVP.** Added `teaagent/run_receipt.py` and
  `teaagent agent status <run_id> --evidence --human` for human-readable run
  receipts (goal, model, cost, audit path, tools, files, approvals, rollback).
- 2026-06-06 — **WS1-002 MVP.** Added `teaagent/approval_selectors.py` with
  numbered pending approvals (`approval pending --human`) and selector-based
  approve (`approval approve --selector N`).
- 2026-06-06 — **DOW-024 Fixed.** Added `scripts/build_release_docs_evidence_bundle.py`
  and linked `docs/generated/release-docs-evidence.md` from the release checklist.
- 2026-06-06 — **DOW-026–030 Fixed.** Command snippet inventory/registry, INDEX status
  vocabulary, language scan, audit cadence doc, and expanded verify_docs gate.
- 2026-06-06 — **WS1-003 MVP.** Added `teaagent/run_progress.py` and
  `teaagent agent status <run_id> --progress [--human]`.
- 2026-06-06 — **WS1-004/005 docs.** Added chat surface semantics and
  background/resume vocabulary guides.
- 2026-06-06 — **WS1-006.** Added `tests/acceptance/test_conversation_ux_flow.py`.
- 2026-06-06 — **WS2-007.** Added remote multi-agent non-goals doc for Phase 0/1.
- 2026-06-06 — **WS2-001–004.** Subagent safety: worktree default on git repos with
  explicit shared isolation, batch deadline/partial results, child budget caps, and
  global depth guard in `teaagent/subagents/`.
- 2026-06-06 — **WS2-005.** Added `ApprovalCoordinationBackend` with file-backed
  default and remote extension point; wired `CentralizedApprovalQueue` + CLI prune.
- 2026-06-06 — **WS2-006.** Added subagent/swarm orchestration unification design
  (`docs/plans/subagent-swarm-orchestration-unification-2026-06-06.md`).
- 2026-06-06 — **WS3-001–006.** Compliance audit mode, strict audit-chain verification,
  schema/path containment tests, cost-state taxonomy, prompt-injection boundaries doc,
  and approval-token exactness tests.
- 2026-06-06 — **WS4-001–005.** Run latency metrics and audit health on receipts;
  approval queue depth/age (CLI + subagents); `audit tail` with classification/redaction;
  `doctor config-lint` for unsafe runtime combinations; tests in
  `tests/test_ws4_observability.py`.
- 2026-06-06 — **WS5-001–005.** Integration contracts in `teaagent/integration/`
  (run setup, event stream, approval strategy, storage adapters, plugin governance);
  wired into `chat_agent` and `load_plugins`; doc at
  `docs/governance/integration-contracts.md`.
- 2026-06-06 — **WS6-001–005.** Governance-first README section; trust/audit
  whitepaper; quarterly competitor refresh process; four persona getting-started
  guides + when-not-to-use page; INDEX and guides index updated.
