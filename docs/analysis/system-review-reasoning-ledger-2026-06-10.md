# System Review Reasoning Ledger
# 2026-06-10

> **Claim class:** Dated evidence package — public reasoning record.
> **Anchor:** TeaAgent at commit `8fcd781` (HEAD on 2026-06-10).
> **Role:** records what questions this review asked, in what order, what
> evidence answered them, what was inferred versus verified, and what remains
> unknown. This is the audit trail for the 2026-06-10 package; it summarizes
> reasoning publicly and does not expose private chain-of-thought.

---

## Method Statement

1. **Start from the prior package, not from zero.** The 2026-06-06 package
   (anchored `ad5e2d7`) defined findings and a WS backlog. This review treats
   each prior finding as a hypothesis to re-test at HEAD, then looks for new
   failure modes the prior frame could not see.
2. **Prefer cheap falsifiers.** For every "X is implemented" claim, the first
   check was the import graph (who calls it?), not the implementation quality.
   This single method produced the package's central finding.
3. **Re-verify status claims at runtime.** Per the standing doc-drift lesson,
   no test/suite status was quoted from documents; the suite was re-run.
4. **Separate self-facts from market-facts.** Self-state was verified at HEAD;
   competitor facts were consolidated from dated sources and explicitly marked
   not re-verified.

---

## Question Log

| # | Question asked | Evidence gathered | Answer class | Outcome |
| --- | --- | --- | --- | --- |
| Q1 | How much did the system change since the 06-06 anchor? | `git log/diff ad5e2d7..HEAD`: 81 commits, ~75k insertions, 694 files; source files 366→444 | Evidence | Delta large enough to justify a full refresh rather than an addendum |
| Q2 | What do the H4/H5/H6 commits claim, and what did they actually add? | Commit messages of `f2c835a`, `4e0a9e9`, `111c61c`, `fe2a881`; `git show --stat`; spec `docs/specs/h4-h5-h6-implementation-spec.md` | Evidence | ~12k-line component drop: RBAC, policy engine/routing, consensus validation, eval suite, release gate, update package, cockpit screens, 291 tests |
| Q3 | Are the new H4/H5 modules wired into any production path? | Import grep across `teaagent/`, `_lazy_exports.py`, `cli/`, `scripts/`, `.github/workflows/` | Evidence | **No** — both clusters import only within themselves; only the cockpit data source reaches a user surface. Central finding ENG-R1 |
| Q4 | Does the canonical roadmap agree with the commit log? | `docs/roadmap-status.md` (last updated 06-07) vs commit messages | Evidence | No: H4–H6 "Pending" vs commits claiming implementation; H2/H3 "Pending" vs M2/M3 "Complete" in the same file. Finding ENG-R2 |
| Q5 | Which 06-06 WS1/WS2/WS3 items actually closed? | Code reads: `subagents/_isolation.py`, `subagents/_manager.py`, `coordination/approval_backend.py`, `run_receipt.py` wiring, findings ledger, commit log (`5d1c25f`, `fa108d2`, `0f30750`, `ac6b318`, `5ea042f`, `7c83e01`, `35c7cb0`) | Evidence | Receipts, selectors, isolation default, batch timeout, durable-queue interface, audit P0s: closed. WS2-004 depth bypass: unverified. WS2-003 cost-cents inheritance: partially verified |
| Q6 | Did the remote multi-agent non-goals become safe to relax? | Re-scored all 9 non-goal rows against HEAD; Ed25519 grep; approval backend read | Evidence + inference | 4 of 9 closed/largely closed; all remote-gating rows (identity, federation, remote orchestration) still open → non-goals remain binding |
| Q7 | What does tenant isolation actually guarantee? | `git show 4e0a9e9`; reasoning about process/principal boundaries | Evidence + inference | Data partitioning for a trusted operator: yes. Security isolation between distrusting tenants: no (single process, string tenant_id) |
| Q8 | Did the conversation experience improve for a general user? | Re-scored 06-06 UX findings; cockpit module review; vocabulary scan | Evidence + inference | Trust-visibility findings closed; cognitive-load findings open; governance vocabulary expanded in daily path (UX-R1 register-mismatch finding) |
| Q9 | What does the whole competitor corpus say when read against today's self-state? | 14 dated competitor docs consolidated; axis table rebuilt with verified NOW column | Evidence (self) + dated evidence (market) | Lane confirmed 5th time; eval-gate axis identified as the only benchmark-setting opportunity; further surveys near-zero marginal value |
| Q10 | Is the test suite actually green at HEAD? | Background full-suite run on Python 3.12 | Evidence | **First run produced no pytest summary — output ended at ~49% with pipeline exit 0 (exit code masked by `tail`).** Re-run issued with pipe-status capture. Result recorded in the package INDEX when complete; until then, suite status at HEAD is **unknown**, and the roadmap's "4758 tests pass" may not hold |
| Q11 | Is the review process itself still needed at this cadence? | Compare 05-31→06-10 packages; observe that the same finding shape (unwired/undocumented capability) recurs at growing scale | Inference | Manual dated reviews catch the drift but do not prevent it; the work directions therefore prioritize *gates* (wiring validator, status-claim check) over more review prose |

---

## Inference Discipline

| Statement in this package | Class |
| --- | --- |
| H4/H5 clusters unwired at HEAD | Direct evidence (import graph) |
| "291 tests verify islands" | Evidence (tests import the islands) + bounded inference (they cannot verify integration that does not exist) |
| Tenant isolation is not inter-tenant security | Inference from architecture (single process), not a penetration test |
| Register-mismatch UX finding | Inference from surface inventory; no user study exists — falsifiable by the proposed ten-minute stranger test |
| Eval-gate axis as benchmark-setting opportunity | Inference from absence in the dated corpus; **competitor absence not re-verified on 06-10** |
| Suite status | Unknown until re-run completes; deliberately not claimed |

---

## What This Review Could Not See (Open Unknowns)

1. **Runtime behavior under real workloads.** Everything here is static
   analysis, git forensics, and test-suite evidence; no live multi-hour agent
   session was observed.
2. **Why the first suite run died (if it died).** Exit-code masking means we
   cannot distinguish crash from truncation until the re-run completes; the
   repo's prior segfault/thread-exhaustion incident (`cf3c028`) makes a crash
   plausible but unproven.
3. **WS2-004 depth/concurrency bypass status** — flagged for targeted
   verification, not checked in this pass.
4. **External user perception.** Five internal reviews now agree with each
   other; that is consistency, not validation. No external user evidence
   exists in this repo.

---

## Self-Critique of This Review (Steelman of the Other Side)

- *Steelman of the component-first approach:* landing H4/H5/H6 as tested
  islands before wiring is arguably correct sequencing — wiring untested
  governance into a live approval path would be worse. The critique stands
  not because components-first is wrong but because the unwired state is
  unlabeled and the canonical status doc contradicts the commits. The fix is
  labeling and gating, not reverting the strategy.
- *Steelman of governance vocabulary in UX:* TeaAgent's target adopter may
  genuinely be the trust-sensitive operator, for whom receipts-everywhere is
  the product. The UX-R1 finding is therefore conditional on the persona
  priority in the daily-driver roadmap rationale still being correct — a
  product decision, flagged as such in the work directions, not an
  engineering defect.
- *Falsifiability:* each major finding names the check that would overturn it
  (wiring imports appearing, roadmap row updates with test citations, a
  stranger test passing, a green suite summary line).
