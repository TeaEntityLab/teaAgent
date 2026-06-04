# Total Review - Future Outlook

**Date:** 2026-06-04 · **Measured baseline:** `4695d46`
This is the forward-looking half. It re-prioritizes the CPA's roadmap against verified ground truth, and
gives every item a **falsifiable exit criterion** — if you can't tell when it's done, it isn't a task.

---

## 1. Trajectory call

**ON TRACK — with one structural caveat the CPA underweighted.**

The engineering is where a disciplined day-27 security-tool should be: green suite, real test pyramid,
stdlib core, captured decisions. The team's "build fast → repair trust → build right" sequence is correct and
*observably happening* (148→0 failures in a day). The caveat is not velocity and not over-engineering — it is
**doc⇄reality drift** (see [Critique §4](total-review-critique-and-interrogation-2026-06-04.md)). The next
four weeks decide whether the docs become trustworthy or remain a recurring credibility tax.

---

## 2. Re-prioritized backlog

Priorities are re-derived from evidence, **not copied from the CPA**. Severity reflects the
[verification](total-review-claim-verification-2026-06-04.md) reframes.

### P0 — do this sprint (Phase-0 exit blockers)

| ID | Task | Exit criterion (falsifiable) | Source |
|----|------|------------------------------|--------|
| FO-1 | **Doc-vs-HEAD CI guard** | A CI job fails when a guarded doc's *prose* claim (e.g. pass/fail counts) contradicts a fresh `pytest` run — proven by deliberately breaking `acceptance.md` and watching CI go red | meta-finding |
| FO-2 | **Fix `acceptance.md` self-contradiction** | Body no longer states the old failed suite as current status; follow-up guard checks the prose, not just the headline | D-1; stale prose fixed later in documentation optimization pass |
| FO-3 | **Pin local dev to Python 3.12** | `.venv` rebuilt on 3.12.x; a documented `make setup` (or `uv` recipe) produces a supported env; CONTRIBUTING notes 3.14 is unsupported | D-2 |
| FO-4 | **Credential encryption** | Secrets at rest use OS keychain/keyring; a test asserts no plaintext credential is written to disk | CPA (agreed) |
| FO-5 | **`issue_intake` stub stops lying** | `_parse_github_issue` raises `NotImplementedError` (or is implemented) instead of returning a mock `ParsedIssue`; test asserts the raise | D-6 |

### P1 — next sprint

| ID | Task | Exit criterion |
|----|------|----------------|
| FO-6 | **Rename runner `ApprovalManager`** | `teaagent/runner/_approval_manager.py` class renamed (e.g. `RunnerApprovalCoordinator`); grep for `class ApprovalManager` returns exactly one hit |
| FO-7 | **Delete/wire orphan `memory/catalog.py`** | Either removed, or imported by ≥1 module with a test; grep for two `class MemoryCatalog` returns one |
| FO-8 | **Audit + guard `DANGER_FULL_ACCESS`** | A hash-chained audit event fires on entering the mode; a test proves it cannot be enabled from config silently (requires explicit flag/confirm) |
| FO-9 | **Re-anchor or supersede the findings ledger** | `…ledger-2026-06-01.md` either updated to HEAD or carries a "Superseded by 2026-06-04 total review" banner |
| FO-10 | **Coverage exclusion deadlines** | Each of the 16 `omit` entries gets a one-line "why excluded + target sprint to re-include" in a tracked doc; ≥1 smoke test added per excluded module |
| FO-11 | **Assign owners to 6 Proposed ADRs** | 0010/0012/0014/0015/0017/0018 each get an owner + decision date, or are closed as "won't do" |

### P2 — when convenient

| ID | Task | Exit criterion |
|----|------|----------------|
| FO-12 | **Break the policy↔approval_manager cycle** | The lazy import at `approval_manager.py:299-300` is removed by extracting shared types to a third module; both import without lazy tricks |
| FO-13 | **Auto-generated `docs/INDEX.md`** | A script regenerates a top-level index for the tracked Markdown corpus; stale links fail CI |
| FO-14 | **Enumerate & ticket the 22 skips** | Each skipped test links to a ticket with a re-enable condition |

---

## 3. Metrics to watch (next 4 weeks)

| Metric | Today | 4-week target | Why |
|--------|-------|---------------|-----|
| Full-suite failures (3.12) | **0** | **0 sustained** (no RED window > 1 build) | durability is the open question |
| Guarded docs contradicting HEAD | **≥1** (`acceptance.md`) | **0**, enforced by FO-1 | the meta-finding's kill-criterion |
| Coverage `omit` entries | 16 | 16 → 12 → 8 (with deadlines) | shrink the unmeasured surface |
| Same-named class collisions | 2 (`ApprovalManager`, `MemoryCatalog`) | 0 | FO-6, FO-7 |
| Proposed ADRs without owner | 6 | 0 | deferred decisions are decisions |
| Local-env Python | 3.14.4 (unsupported) | 3.12.x | test what you ship |
| Commits/day | ~23 | stabilize 10–15 | sustainability |
| Acceptance tests | 441 | 500+ | breadth, not just green |

---

## 4. Phase-0 exit definition (proposed, falsifiable)

Phase 0 ("trust repair") is **done** when **all** hold simultaneously for **7 consecutive days**:

1. Full suite green on Python 3.12 in CI — zero RED builds.
2. Zero guarded docs contradict HEAD (FO-1 enforced).
3. Zero same-named class collisions (FO-6, FO-7).
4. Every coverage exclusion has a written reason + target date (FO-10).
5. No production stub returns fabricated data (FO-5).
6. Local dev env matches the supported interpreter (FO-3).

If any of these is false, Phase 0 is not exited — regardless of how the roadmap doc reads. This is the
discipline the project's own "honest" commit messages are reaching for; make it a gate, not a vibe.

---

## 5. The one-sentence outlook

**The project is building something genuinely differentiated — a zero-dependency, audit-first, ADR-driven
agent — and it has just demonstrated it can repair its own trust debt in a day; the next four weeks turn on
whether it makes documentation honesty a *CI-enforced gate* rather than a *recurring heroic commit*, because
that, not over-engineering, is the failure mode that will otherwise quietly erode every other achievement.**
