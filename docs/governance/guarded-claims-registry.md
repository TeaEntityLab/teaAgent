# Guarded Claims Registry

This registry generalizes the documentation guards beyond coverage-omit and
dependency-audit scope. It lists volatile prose facts that tend to go stale and
the rule `scripts/validate_docs_consistency.py` enforces so that a stale claim
fails CI instead of silently misleading readers.

The motivating failure mode: a current-truth document keeps an old full-suite
result such as `... 26 failed` long after the suite went green. Dated evidence
documents may keep their historical numbers; current-truth front doors may not.

## Guarded Claim: full-suite failure prose

- **Claim class**: full test-suite pass/fail summary prose (for example
  `N passed, M failed`).
- **Rule**: in the guarded current-truth documents listed below, a line that
  reads like a test-suite summary (mentions `passed`, `pytest`, or `suite`) must
  not assert a non-zero failure count (`N failed` / `N failures` with `N > 0`).
  A green claim (`0 failed`) is allowed.
- **Exemption**: a line that also contains `historical`, `superseded`, or
  `example` is treated as intentionally dated and is skipped. Move durable
  historical numbers into dated evidence docs (for example under
  `docs/analysis/` or `docs/reviews/`) rather than current-truth front doors.
- **Validator function**: `validate_guarded_claims` in
  `scripts/validate_docs_consistency.py`.

### Guarded current-truth documents

| Document | Why it is guarded |
|---|---|
| `README.md` | Project front door; first thing new users read. |
| `docs/acceptance.md` | Current acceptance truth; pass counts are quoted widely. |
| `docs/daily-driver-current-status.md` | The "what can I trust today" front door. |
| `docs/roadmap-status.md` | Current roadmap and claim-hygiene status. |

## Guarded Claim: cross-reference integrity

- **Claim class**: internal markdown cross-references in current-truth docs.
- **Rule**: every relative link to a `.md` file in the guarded documents must
  resolve to an existing file in the repository. Broken links fail validation.
- **Guarded documents**: `README.md`, `docs/INDEX.md`, `docs/USAGE.md`,
  `docs/cli.md`, `docs/acceptance.md`, `docs/roadmap-status.md`,
  `docs/daily-driver-current-status.md`, `docs/release-checklist.md`,
  `docs/backlog-priority.md`, `docs/maturity-matrix.md`, `docs/terminology.md`,
  `docs/architecture.md`.
- **Validator function**: `validate_doc_cross_references` in
  `scripts/validate_docs_consistency.py`.

## Guarded Claim: plan staleness

- **Claim class**: plan documents lacking date markers or supersession notes.
- **Rule**: every plan in `docs/plans/` must have a `Last updated` /
  `Last reviewed` / `Date:` marker or a `Supersession note` within 90 days.
  Files in `ticket-plans/` are exempt (task execution ledgers, not plans).
- **Validator script**: `python3 scripts/detect_stale_plans.py`
- **CI integration**: informational only (not yet blocking); plans older than
  90 days without updates are reported.

## Guarded Claim: provider count drift

- **Claim class**: provider count in README, architecture.md, and USAGE.md.
- **Rule**: the provider count in all three documents must match
  `len(PROVIDER_CONFIGS)` at runtime.
- **Validator function**: `validate_provider_docs_consistency` in
  `scripts/validate_docs_consistency.py`.

## Guarded Claim: acceptance count accuracy

- **Claim class**: acceptance test count in docs/acceptance.md and
  docs/maturity-matrix.md.
- **Rule**: `docs/acceptance.md` passed count must match `pytest --collect-only`
  count for `tests/acceptance/`. The maturity-matrix "Honest External Posture"
  file/test counts must match the acceptance.md guard target and the
  `tests/acceptance/test_*.py` file count.
- **Validator function**: `validate_docs_consistency` compares
  `_extract_acceptance_status_count` with `_collect_acceptance_test_count`;
  `tests/test_docs_consistency.py::test_maturity_matrix_acceptance_counts_match_acceptance_doc`
  pins the maturity-matrix numbers.

## Guarded Claim: review date coherence

- **Claim class**: competitor survey review dates across documentation.
- **Rule**: survey, use-case-matrix, plugin-skill-catalog, and use-cases docs
  must all reference the same review date. Date drift across documents fails
  validation.
- **Validator function**: `validate_date_coherence` in
  `scripts/validate_docs_consistency.py`.

## Re-Entry Rules

- Adding a guarded document requires a same-commit row in the relevant table
  above and a matching entry in the corresponding validator.
- Adding a new guarded claim class requires a new section here and a matching
  validator function with a unit test in `tests/test_docs_consistency.py`.
- Historical, dated numbers belong in evidence documents, not in the guarded
  current-truth front doors above.
- Plan staleness checks are informational (non-blocking in CI) until the
  corpus stabilizes; current-truth cross-reference checks are blocking.
