# Fact-Check Log — Review Findings (2026-06-20)

Verification of the review claims raised after the `fix/docs-tests-small-defects`
cleanup. Each claim was re-checked against the working tree at HEAD `d786f70`
(in sync with `origin/main`, behind 0 / ahead 0) before being recorded here.
Status uses the Claims Ledger convention: `verified` = evidence examined
directly; `refuted` = evidence contradicts the claim.

## Claims Ledger

| ID | Claim | Verification command | Status |
|----|-------|----------------------|--------|
| F1 | The `e065536` cleanup is on `main` | `git merge-base --is-ancestor e065536 HEAD` → ancestor=yes | **verified** |
| F2 | TUI dead background/event state is gone | `git grep -n "_index_ready\|_background_indexer_started\|_ensure_background_indexer\|_cache_refresher_worker" -- teaagent/tui/_completion.py` → no matches | **verified** |
| F3 | Dependency-contract test de-duplicated (tomllib in dedicated test; acceptance dup removed) | `git grep -c tomllib -- tests/test_test_dependency_contract.py` → 2; acceptance `test_full_collection_dependencies_are_declared_in_dev_extra` absent | **verified** |
| F4 | Review finding #2's "Operator Friction Log" rename was **not** adopted in governance docs | `git grep -l "Operator Friction Log" -- docs/governance/` → only `evidence-to-principle-policy.md`, not the operating-model or taxonomy | **verified (not implemented)** |
| F5 | The *live defect* behind finding #2 (governance docs disagreeing on next-work source) is already resolved | `doc-taxonomy-and-ownership.md:64` and `documentation-operating-model-2026-06-04.md:83` **both** point next-work → `docs/roadmap-status.md`, ticket index demoted to "historical closures" | **verified (conflict resolved)** |
| F6 | `validate_docs_consistency.py` still has no anchor-link checking (file-link rot gated, anchor rot not) | `git grep -in anchor -- scripts/validate_docs_consistency.py` → no matches | **verified (gap open)** |
| F7 | Owner has an uncommitted retrospective package staged | `git diff --cached --name-status` → 10× `A docs/retrospective/*` + 2× `M docs/generated/*`, all `A`/`M` vs HEAD (new, not yet committed) | **verified (owner work — hands off)** |

## Corrected claims (from earlier loose statements)

- Earlier framing said "all 3 review findings landed." Accurate count: **2 of 3
  required fixes (F2, F3) + 1 bonus anchor-slug fix** shipped in `e065536`.
  Finding #2's rename (F4) did **not** ship.
- Finding #2 does **not** need reopening as a bug: F5 shows the source-of-truth
  conflict it flagged is already gone. What remains is an optional design choice
  (adopt "Operator Friction Log" wording or not), not a defect.
- F7 was briefly mis-described as "tracked at HEAD." Authoritative signal is
  `git diff --cached` showing `A` — the files are **newly staged, not committed**.

## Process lesson (recorded, not repo-verifiable)

During the anchor work, a slug scanner using `re.sub(r'\s+', '-', ...)` collapsed
consecutive spaces, whereas GitHub preserves them as consecutive hyphens
(`.replace(' ', '-')`). The bug nearly produced 21 false "broken anchor" fixes.
Caught before acting. Relevant to F6: an anchor gate, if added, must replicate
GitHub's exact slug algorithm or it will generate false positives.

## Open items (not started — require owner direction)

1. **Anchor gate (F6):** fold GitHub-correct anchor-link checking into
   `validate_docs_consistency.py` so anchor rot is gated like file-link rot.
2. **Finding #2 rename (F4):** decide whether to standardize on "Operator
   Friction Log" wording across governance docs, or close as won't-do (the
   defect is already resolved per F5).

## Constraints honored while recording this

- This file is **new and untracked**; it was not staged, so it does not disturb
  the owner's in-flight `docs/retrospective/` staged package (F7).
- No `git add -A`; no commit/push performed.
