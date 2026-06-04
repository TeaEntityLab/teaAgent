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

## Re-Entry Rules

- Adding a guarded document requires a same-commit row in the table above and a
  matching entry in `GUARDED_FULL_SUITE_DOCS` in
  `scripts/validate_docs_consistency.py`.
- Adding a new guarded claim class requires a new section here and a matching
  validator function with a unit test in `tests/test_docs_consistency.py`.
- Historical, dated numbers belong in evidence documents, not in the guarded
  current-truth front doors above.
