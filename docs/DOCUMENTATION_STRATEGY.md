# Documentation Strategy

**Owner:** Documentation governance  
**Last updated:** 2026-06-04  
**Status:** Normative — this file defines the rules for all `docs/` content

---

## 1. Purpose

This document establishes the authoritative rules for how documentation is
created, maintained, and retired in teaagent. Its goal is to prevent
doc⇄reality drift: the failure mode where a document's claims outlive the
code state they describe.

---

## 2. Two-Tier Document Model

All `docs/` files belong to exactly one tier.

### Tier 1 — Canonical Active Truth

These documents are single sources of truth for their domain. They are updated
in-place whenever the underlying state changes, and they are tested by
`scripts/validate_docs_consistency.py`.

| File | Domain |
|---|---|
| `docs/roadmap-status.md` | Roadmap horizons, milestones, and work-item status |
| `docs/security/risk-register-and-threat-model-*.md` | Security risk status and STRIDE model |
| `docs/acceptance.md` | Acceptance test suite status and tier breakdown |
| `docs/governance/coverage-omit-ledger.md` | Coverage omit patterns and owner mapping |
| `docs/governance/guarded-claims-registry.md` | Volatile public-facing claims requiring guards |
| `README.md` | Public product description, provider count, feature list |

**Rules for Tier 1:**
- Every status field must be one of: `Fixed`, `Active`, `In Progress`, `Pending`,
  `Deferred`, `Blocked`, `Complete`.
- Every `Fixed` row must cite at least one test function name (`test_<name>`) or
  a commit hash (7+ hex chars) as evidence.
- Every `Active` or `In Progress` row must cite at least one ticket ID or code
  file reference.
- A Tier 1 document must never contain contradictory status claims between its
  header/summary section and its detailed table rows.

### Tier 2 — Dated Historical Evidence

These documents are time-stamped audit records. They are **never retroactively
edited** except to add a supersession note. They are not subject to
Tier 1 consistency rules because their job is to record what was true at a
point in time.

Examples: `docs/analysis/daily-driver-risk-register-2026-06-01.md`,
`docs/work-log/phase-0-governance-closure-report-2026-06-04.md`,
`docs/analysis/task-evidence-audit-2026-06-04.md`.

**Rules for Tier 2:**
- File name must contain a date (`YYYY-MM-DD`).
- Top of file must state the capture date.
- If a later document supersedes this one, add a `> **Superseded by:** [link]`
  blockquote at the top. Do not delete the file.
- Do not update Tier 2 files to reflect current code state; create a new dated
  file instead.

---

## 3. Claim Completeness Criteria

A "claim" is any status assertion, feature claim, or completion statement in a
Tier 1 document. The following table defines what counts as sufficient proof.

| Claim Type | Minimum Proof Required | Examples |
|---|---|---|
| **Fixed** (was a bug or risk) | One test function name that exercises the fix AND passes in CI, or a commit SHA that lands the fix | `test_empty_path_globs_rejected_ds12`, `cf7623e` |
| **Complete** (roadmap milestone or work item) | Referenced acceptance test file (`tests/acceptance/test_*.py`) that collects in the acceptance tier | `tests/acceptance/test_approval_root_cli_flow.py` |
| **Active / In Progress** | A ticket ID or a code file path showing work is in flight | `TASK-DD2-004`, `teaagent/ergonomics/_approval_state.py` |
| **Pending** | Entry exists with an owner field (TBD is allowed temporarily) | No evidence needed, but owner must not be blank for P0/P1 items |
| **Deferred** | A stated reason and a return condition or milestone | "Deferred until H3 completes; blocked on MCP trust-onboarding spec" |
| **Open** (risk register) | For P0/P1 severity: at least a ticket ID or failing test that demonstrates the gap; code reference acceptable for P2+ | `tests/integration/test_destructive_approval_lifecycle.py:142` |

### What does NOT count as proof

- A prose description of the fix in the same document ("we changed the code to…")
- A referenced doc that itself has no test evidence
- A TODO comment in source code
- A note in a Tier 2 dated document (historical evidence cannot validate current truth)

---

## 4. Header⇄Table Consistency Rule

**Critical rule:** If a Tier 1 document has both a header/summary section and a
detailed table, the status in the table row is authoritative. Updating only the
header and leaving the table row stale creates a direct inconsistency that
automated validators flag as an error.

When a fix lands:
1. Update the table row status from `OPEN` to `FIXED` (or the appropriate status).
2. Add the test name or commit hash in the row or in an adjacent evidence column.
3. Update the header/summary to match.
4. Do not update only the header.

---

## 5. Validated Documents

`scripts/validate_docs_consistency.py` enforces machine-checkable consistency
rules across Tier 1 documents. It runs in CI. The following checks are active:

| Check | Function | Failure Condition |
|---|---|---|
| Risk register evidence | `validate_risk_register_evidence()` | Any FIXED row without test/commit; any OPEN P0/P1 without evidence; header⇄table mismatch |
| Ticket index evidence | `validate_ticket_index_evidence()` | Fixed claim with no file path or test name; partial Fix with no plan file link |
| Roadmap status structure | `validate_roadmap_status()` | Missing H0 row, missing doc-vs-HEAD reference |
| Guarded claims | `validate_guarded_claims()` | Current-truth doc asserts non-zero test failures |
| Coverage omit ledger | `validate_coverage_omit_ledger()` | Ledger out of sync with `pyproject.toml` omit patterns |
| Provider count | `validate_provider_docs_consistency()` | README / architecture / USAGE mismatch with runtime count |
| Acceptance tier | tier block check | `docs/acceptance.md` tier table out of sync with `run_acceptance_tier.py` |
| Dependency audit policy | `validate_dependency_audit_policy()` | Security workflow uses unscoped audit |
| Survey freshness | `validate_date_coherence()` | Date drift across survey, matrix, catalog, use-cases |

To run locally:

```sh
python3 scripts/validate_docs_consistency.py
```

To check only the risk register and ticket index:

```sh
python3 scripts/validate_docs_consistency.py \
  --skip-providers \  # future flag; currently pass --no-check-providers
  --risk-register docs/security/risk-register-and-threat-model-2026-06-02.md \
  --ticket-index docs/plans/ticket-plans/index.md
```

---

## 6. Dated Historical Documents — Retention Policy

Dated evidence documents serve as the audit trail for the project's evolution.
They answer: "what did we know at date X, and what did we decide then?"

**Do not delete dated docs.** If a document is superseded:
1. Add a `> **Superseded by:** [link to newer doc]` blockquote at the top.
2. Move it to the relevant dated archive location (no reorganization needed).
3. Do not edit its body content.

**Do not add new sections to a dated doc** to reflect a later state. If the
state has changed, create a new dated document.

---

## 7. When to Create a New Document vs. Update an Existing One

| Situation | Action |
|---|---|
| Bug was fixed; risk register row should move to FIXED | Update the Tier 1 risk register table row in-place |
| New risk discovered | Add a new row to the Tier 1 risk register |
| Analysis of a new problem was done | Create a new Tier 2 dated doc in `docs/analysis/` |
| A roadmap item is complete | Update `docs/roadmap-status.md` row in-place; add exit evidence |
| A sprint ended and you want to record what happened | Create a new Tier 2 work log in `docs/work-log/` |
| Existing docs are out of date with each other | Fix the Tier 1 docs; create a dated Tier 2 audit if the inconsistency was significant |

---

## 8. Commit Convention for Documentation Changes

When updating a Tier 1 document to reflect a code change:
- Commit message prefix: `docs(status):` for status-only updates
- Commit message prefix: `docs(audit):` for new evidence audit files
- Commit message prefix: `docs(fix):` for correcting doc⇄reality drift
- Always cite the corrected ID and the evidence: `docs(fix): mark DS-12 FIXED — test_empty_path_globs_rejected_ds12`
