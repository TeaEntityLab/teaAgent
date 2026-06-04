# Total Review - Claim-by-Claim Verification

**Date:** 2026-06-04 · **Measured baseline:** `4695d46` · **Subject:** the supplied *Comprehensive Project Analysis* (CPA)
**Verdict legend:**
**VERIFIED** - matches the measured baseline within rounding.
**OVERSTATED** - true but milder than stated.
**REFRAME** - the framing is wrong even if a fact is present.
**STALE/RISK** - was true at a snapshot but the dynamics matter.
**FALSE** - contradicted by the measured baseline.

**Status correction, 2026-06-04:** the ADR rows below were measured before the
ADR cleanup pass. Current truth: no live `Proposed` ADR rows remain in
`docs/adr/README.md`, and ADR 0025 is recorded as implemented for REPL and TUI
chat.

---

## A. Scale & velocity (CPA §1–2)

| CPA claim | Measured at HEAD | Verdict |
|-----------|------------------|---------|
| 625 commits | 626 at baseline; 627 at current documentation pass | VERIFIED (+1/+2 since CPA) |
| 27 days (May 8 -> Jun 4) | first 2026-05-08, last 2026-06-04 | VERIFIED |
| 151K LOC | 155,841 Python LOC at baseline; 155,897 at current documentation pass | VERIFIED, scope-dependent |
| 3,359 tests | 3,377 collected at baseline; 3,379 at current documentation pass | VERIFIED |
| 23 commits/day, 5.6K LOC/day, "unsustainable for a quarter" | 626/27 approx. 23.2 commits/day at baseline | VERIFIED, and the judgment is sound |

## B. Test & coverage (CPA §5)

| CPA claim | Measured | Verdict |
|-----------|----------|---------|
| 441 acceptance tests passing | `acceptance.md` headline = 441; full suite green at recorded baseline | VERIFIED; full-suite evidence was 3355/0/22 |
| 75% coverage gate | `--cov-fail-under=75` (`ci.yml:112`) | VERIFIED |
| "FakeAdapter pattern is great" | confirmed deterministic mock present | VERIFIED |
| 18 modules zero coverage, no deadline | 16 `omit` entries, no re-entry dates | OVERSTATED count; the no-deadline critique is correct and important |
| Test breakdown 2,676 unit + 441 acceptance + 217 integration + 1 E2E + 4 regression + 1 policy | not independently recounted; totals reconcile | VERIFIED, totals consistent |

## C. Architecture & duplication (CPA §3, §6)

| CPA claim | Measured | Verdict |
|-----------|----------|---------|
| AgentRunner 757 lines | `runner/_core.py` = 757 | VERIFIED exact |
| 14+ LLM providers | 14 `ProviderConfig` | VERIFIED |
| Zero mandatory runtime deps, stdlib core | confirmed posture | VERIFIED |
| **Duplicate `ApprovalManager` (HIGH, "behavior may diverge")** | 2 classes, **different roles** (861-line policy engine vs 140-line runner workflow wrapper) | REFRAME to Medium. Name collision, not behavioral fork. Fix = rename, not merge |
| **Circular import policy/approval_manager (HIGH, "will explode")** | real cycle, **handled by lazy import** (`approval_manager.py:299-300`); both import OK in isolation | OVERSTATED to Low. Latent smell, not active bug |
| **MemoryCatalog divergence (HIGH, "which is canonical?")** | legacy is canonical and exported; `memory/catalog.py` is **orphan dead code** (0 importers) | REFRAME to Medium. Answer is known: delete or wire the orphan |
| **`DANGER_FULL_ACCESS` bypass (CRITICAL, "remove or external control")** | bypasses at `approval_manager.py:197-201`, **by design** (opt-in full-access mode) | REFRAME to Medium. Audit plus accidental-enable guard; do not remove by default |

## D. Documentation (CPA §4)

| CPA claim | Measured | Verdict |
|-----------|----------|---------|
| 30 ADRs (20 implemented) | 31 ADR/decision files in the measured scope; the earlier "6 Proposed" reading is superseded by the 2026-06-04 ADR cleanup | VERIFIED for count; SUPERSEDED for current status |
| 6 Proposed ADRs unexecuted | stale snapshot claim for 0010/0012/0014/0015/0017/0018; current ADR index has no live `Proposed` rows | SUPERSEDED |
| 4-standard module docs (28 modules) | 28 module dirs | VERIFIED |
| 250+ markdown / 59 dirs, "discoverability is a problem" | 456 tracked Markdown files at the current documentation pass; 421 under `docs/` | VERIFIED undercount; the discoverability critique is understated |
| "docs are exceptional for a 27-day project" | broadly true | VERIFIED, but see [Critique](total-review-critique-and-interrogation-2026-06-04.md) on docs-as-trust-surface |

## E. The CPA's blind spots (what it did *not* say)

| Gap | Why it matters |
|-----|----------------|
| **Stability is less than 24h old** | CPA presents green as steady-state. The suite was **RED (148 failures) on 2026-06-03**; same-day commits fixed it. The CPA snapshot is true but fragile |
| **`acceptance.md` self-contradicted** | the guarded doc body said "26 failed" while baseline evidence was 0 failed; CPA cited the doc without catching its internal contradiction. Fixed later in the documentation optimization pass |
| **Local env on unsupported Python 3.14.4** | CPA never checks the interpreter; all "passing" numbers would mean little if read off the 3.14 `.venv` |
| **The real systemic risk is doc/reality drift, not over-engineering** | CPA's headline risk ("over-engineering before PMF") is secondary; the recurring "keep it honest" commits reveal the primary failure mode |
| **1 production stub returns fake data** | `issue_intake.py:195` returns a mock `ParsedIssue` instead of raising; CPA's risk table omits silent-wrong-data |

---

## Scorecard

| Bucket | Count |
|--------|-------|
| VERIFIED | 18 |
| OVERSTATED | 3 |
| REFRAME | 3 |
| STALE/RISK (CPA blind spots) | 4 |
| FALSE | 1 at baseline (the secondhand "26 failed" via acceptance.md; later fixed in the documentation optimization pass) |

**Net:** the CPA is a **high-quality, fact-accurate snapshot** with a **partly inflated risk register** and a
**time-blindness** that a same-day re-run exposes. Its facts: trust. Its risk severities: discount by one
notch. Its "ON TRACK": true today, re-check weekly.
