# Total Review - Critique And Interrogation

**Date:** 2026-06-04 · **Measured baseline:** `4695d46`
This document does the *adversarial* work: assumption audit, steelman, falsifiability, and the meta-finding.
It interrogates **both** the supplied Comprehensive Project Analysis (CPA) **and my own prior review**, which
recorded the suite as RED and is now superseded.

---

## 1. Assumption audit

### Assumptions the CPA made (and whether they hold)
| Assumption | Holds? | Note |
|------------|--------|------|
| "441 passing ⇒ project is healthy" | **partially** | True for *test health today*; says nothing about durability or coverage of the 16 omitted modules |
| "more docs (30 ADRs, FMEA, threat model) ⇒ maturity" | **partially** | Docs can encode maturity *or* substitute for it; the CPA itself flags this in §8 |
| "two same-named classes ⇒ behavioral duplication" | **no** | They have different roles (verified); see [Real Situation §4](total-review-real-situation-2026-06-04.md) |
| "circular import ⇒ latent crash" | **no** | Lazy import already neutralizes it |
| reported numbers were read on a supported interpreter | **unstated** | The local `.venv` is 3.14.4; numbers are only meaningful on 3.12 |

### Assumptions *my prior review* made (self-critique)
| Assumption | Holds? | Correction |
|------------|--------|------------|
| "FIXED in docs ≠ FIXED in code, so trust nothing green" | **was right, now over-applied** | The team *did* close 148 failures; refusing to re-measure would have produced a false RED report today |
| "148 failures = stable regression" | **no** | It was a transient mid-refactor state; re-running at HEAD is mandatory, not optional |
| "the ledger is the authority" | **no** | The ledger (2026-06-01) is *itself* stale; **the code at HEAD is the only authority** |

**Lesson that binds both reviews:** *every status claim decays in hours in this repo.* The correct protocol is
**re-run, then write** — which is what produced this package.

---

## 2. Steelman of the project's current choices

Before criticizing, the strongest case *for* what the team is doing:

- **"Build fast → repair trust → build right" is the correct order.** Phase-0 trust repair *after* a fast
  build is more honest than pretending the fast build was clean. The 148→0 repair in a day, with commit
  messages that *name* the dishonesty, is exactly the behavior you want.
- **Over-documentation is cheaper to prune than under-documentation is to reconstruct.** 31 ADRs you can index;
  decisions lost to chat history you cannot recover. The corpus is an asset with a maintenance tax, not a
  liability.
- **The "duplicates" are mostly disciplined seams, not rot.** A 140-line runner-local approval *coordinator*
  separate from the 861-line policy *engine* is arguably good layering; the only mistake is the shared name.
- **`DANGER_FULL_ACCESS` is a feature, not a hole.** Power users need an escape hatch; pretending they don't
  drives them to worse workarounds.

If the steelman is right, the project is roughly where a disciplined security-minded tool *should* be at day 27.

---

## 3. Falsifiability — claims stated so they can be proven wrong

A review that can't be falsified is marketing. Each headline judgment below has a kill-criterion.

| Judgment | Falsified if… |
|----------|---------------|
| "Suite is green at HEAD" | `pytest -q` on 3.12 shows any FAILED/ERROR (re-run: it shows 0) |
| "Green is < 24h durable, not proven" | the suite stays green across the next 7 days at current churn without a RED window |
| "Circular import is benign" | any supported import order raises `ImportError` (tested: none does) |
| "`memory/catalog.py` is dead" | any module/test imports `teaagent.memory.catalog` (grep: zero) |
| "doc⇄reality drift is the #1 risk" | a 30-day audit finds zero guarded docs contradicting HEAD (today: `acceptance.md` already does) |
| "CPA risk register is inflated by ~1 notch" | independent review rates the 3 reframed risks at the CPA's original HIGH/CRITICAL on evidence |

---

## 4. The meta-finding (the thing both reviews circle but neither named)

> **The dominant systemic risk in this repo is not over-engineering, not velocity, and not any single
> bug. It is the structural tendency for documentation to over-claim relative to code, and the cost of
> that drift scales with a large Markdown corpus.**

Evidence that this is systemic, not incidental:
1. **The repo contains its own confession.** Today's commits: *"Keep the test suite honest," "keep the story
   honest," "Make the … surface honest enough to trust," "Unify suspend and review wording so the
   daily-driver story stays honest."* You do not write four "honest" commits in a day unless dishonesty was
   the default.
2. **A guarded doc was wrong at the measured baseline.** `acceptance.md` is protected by
   `test_docs_acceptance_count_accuracy.py`, yet its narrative body stated "26 failed" while full-suite
   evidence showed 0 failed. The guard checked the *headline number*, not the *prose claim* — so the test
   passed while nearby prose drifted. The stale paragraph was fixed in the documentation optimization pass,
   but the guard gap remains.
3. **Prior reviews keep rediscovering the same drift.** `markdown-status-review-2026-06-02` (MSR-002) already
   diagnosed status-vocabulary drift; `task-tracking-review-2026-05-31` found a "Shipped" feature whose
   directory didn't exist. The pattern repeats because nothing structurally prevents it.

**Why the large Markdown corpus makes this worse, not better:** every doc is a *claim surface*. The validator
(`validate_docs_consistency.py`) checks a handful of facts (counts, dates, required sections) but, per MSR-004,
**does not enforce the lifecycle** — so most of the Markdown corpus can drift freely. More docs means more
unverified claims ⇒ more trust eroded each time one is caught wrong.

**The interrogation question for the team:** *Which Markdown files would survive a script that
fails CI when a doc's claims contradict HEAD?* If the honest answer is "we don't know," that is the finding.

---

## 5. Where I disagree with the CPA's recommendations

| CPA recommendation | My amendment |
|--------------------|--------------|
| "Merge duplicate ApprovalManager" | **Rename, don't merge** — they're different roles (§4a of Real Situation) |
| "Break the circular import (P0)" | **Demote to P2** — it's already neutralized by lazy import; cosmetic |
| "Decide which MemoryCatalog is canonical (P0)" | **Already decided** — delete/wire the orphan `memory/catalog.py` |
| "Add credential encryption (P0)" | **Agree, keep P0** — this is a genuine gap the CPA got right |
| (absent) | **Add: a doc-vs-HEAD CI guard** — the highest-leverage missing control |
| (absent) | **Add: pin local dev to 3.12** — stop testing on unsupported 3.14 |
| (absent) | **Add: make `issue_intake` stub raise** instead of returning fake data |

---

## 6. Residual uncertainty (what this review does *not* establish)

- **Coverage *number* not measured here** — I verified the *gate* (75%) and the *omit list* (16 entries), not
  the achieved percentage. The 16 omitted modules (TUI, tournament, validation, WASM, webhook sink, …) are
  by definition unmeasured.
- **22 skipped tests not enumerated** — `acceptance.md` attributes skips to "deep architectural issues"
  (undo-diff budget, llm_conformance config, A2A timing, TUI features). Each skip is a small hidden debt.
- **Durability of the green** — established for one run at one hour. Only a week of green proves it.
- **Security depth** — the approval/audit *machinery* is substantial and tested; whether it resists a
  determined adversary (the "defeat scenarios" docs) is out of scope for this review.
