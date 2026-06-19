# Documentation Taxonomy And Ownership
# 2026-06-02

This file defines where each kind of document belongs and which file should be
treated as authoritative when documents disagree.

## Taxonomy

| Type | Purpose | Primary location | Source-of-truth rule |
|------|---------|------------------|----------------------|
| User guide | Help a daily user choose commands and recover. | `docs/`, `docs/guides/` | Must reflect current behavior, not historical plans. |
| How-to / recipe | Give a task-specific procedure. | `docs/guides/`, `docs/ops/`, `docs/debugging/` | Must link to a current reference or runbook when safety matters. |
| Reference | Define commands, APIs, schemas, terms, or module surfaces. | `docs/api/`, `docs/modules/`, `docs/terminology.md` | Should be stable and version-aware. |
| Explanation | Explain architecture, tradeoffs, or history. | `docs/architecture/`, `docs/analysis/`, `docs/decisions/` | May be historical; current status must link to ledgers. |
| Analysis / audit | Dated evidence from a review pass. | `docs/analysis/`, `docs/reviews/` | Preserve as evidence; do not treat as current truth without an index. |
| Risk register | Rank and own risks. | `docs/analysis/`, `docs/security/`, `docs/reliability/` | P0/P1 risks must link to ticket, roadmap, or Human Review decision. |
| FMEA | Rank failure modes by severity, occurrence, and detection. | `docs/reliability/` | Use for prioritization; link high RPN items to tickets. |
| Threat model | Classify security threats and trust boundaries. | `docs/security/`, `docs/threat-model.md` | Security-sensitive changes require review notes. |
| ADR | Record accepted or rejected architecture decisions. | `docs/adr/`, `docs/decisions/` | Current decisions should not be contradicted by plans. |
| Spec | Define expected behavior before implementation. | `docs/specs/` | Must include acceptance criteria and non-goals. |
| Ticket plan | Define reviewable implementation work. | `docs/plans/ticket-plans/` | Execution truth lives in the ticket index. |
| Roadmap | Track horizons, ownership, gates, and exit evidence. | `docs/roadmap-status.md`, `docs/plans/` | Roadmap truth lives in `docs/roadmap-status.md`. |
| Runbook | Explain repeatable operations or incident response. | `docs/ops/`, `docs/processes/` | Must include observable success/failure signals. |
| Module docs | Assign subsystem behavior, APIs, risks, and inspection paths. | `docs/modules/<module>/` | Module-local truth only; central P0/P1 risks need links upward. |
| Review log | Capture review decisions, residual risk, and verification. | `docs/reviews/`, `docs/analysis/` | Historical unless referenced by an active ledger. |

## Ownership model

Use this lightweight DRI/RACI shape when a document drives future work.

| Role | Meaning |
|------|---------|
| DRI | Directly responsible for keeping the artifact current. |
| Reviewer | Required reviewer for risky state changes. |
| Consulted | Domain owner who should be checked for major edits. |
| Informed | Audience that relies on the artifact but does not approve it. |

If the actual person is unknown, write `TBD` but still assign an owner surface,
such as `TUI`, `security`, `docs`, `runner`, `modules`, or `release`.

## Default owners by document type

| Document type | Default owner surface | Required reviewer when high risk |
|---------------|----------------------|----------------------------------|
| Daily-driver current status | docs / product | TUI or agent surface owner |
| Findings ledger | docs / verification | affected module owner |
| Ticket plan | implementation owner | verifier |
| Roadmap status | roadmap / release | maintainer |
| Security risk | security | maintainer / Human Review |
| Reliability FMEA | reliability | test owner |
| ADR | architecture | maintainer |
| Module spec/API | module owner | architecture if cross-module |
| Module risks | module owner | security or reliability if P0/P1 |
| Runbook | ops | affected surface owner |

## Front doors

Users and agents should start here:

| Need | Start here |
|------|------------|
| Daily-use truth | `docs/daily-driver-current-status.md` |
| Daily-driver review package | `docs/analysis/daily-driver-review-INDEX-2026-06-01.md` |
| Execution order | `docs/roadmap-status.md` (historical closures: `docs/plans/ticket-plans/index.md`) |
| Roadmap status | `docs/roadmap-status.md` |
| Module ownership | `docs/modules/INDEX.md` |
| Governance policy | `docs/governance/doc-maintenance-policy-2026-06-02.md` |

## Merge and update policy

Merge documents only when they compete for the same current-truth question.
Do not merge merely because two files mention the same risk.

Prefer these actions:

| Situation | Action |
|-----------|--------|
| Old dated audit conflicts with current status | Keep audit; add supersession note or index mapping. |
| Two active indexes answer the same status question | Pick one canonical index; turn the other into a pointer. |
| Module risk appears in central risk register | Keep both; module doc owns local detail, central register owns priority. |
| Ticket plan repeats a long analysis | Keep ticket concise; link to the analysis. |
| Roadmap repeats implementation steps | Replace steps with ticket links and exit evidence. |
| User guide includes historical caveats | Move history to analysis; keep guide focused on current behavior. |

## Minimum metadata

New governance-sensitive docs should include:

- Date.
- Purpose.
- Scope.
- Current owner surface or `TBD`.
- Source documents.
- Status vocabulary or link to `document-state-model.md`.
- Verification command or manual review rule.

Short user guides may omit metadata when it would make the guide harder to use.

## Naming rules

Use:

- Dated filenames for audits, reviews, surveys, and reports.
- Stable filenames for current entry points and policies.
- Stable IDs for findings, risks, tickets, ADRs, and roadmap rows.

Do not create a new ID namespace unless an existing namespace cannot represent
the item without ambiguity.

## Review cadence

| Artifact | Review trigger |
|----------|----------------|
| Daily current status | Any change to TUI, chat, agent mode, approval, cost, undo, or resume behavior. |
| Ticket index | Any ticket state transition. |
| Roadmap status | Any release gate, horizon, or exit evidence change. |
| Risk register | Any P0/P1 discovery, mitigation, or new exploit path. |
| Module risk docs | Any module behavior, API, or ownership change. |
| User guides | Any command grammar or output wording change. |

## Validation

Run these after governance-sensitive doc edits:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

Use `cx overview docs --limit 100` and heading searches to confirm new documents
are discoverable from the corpus.
