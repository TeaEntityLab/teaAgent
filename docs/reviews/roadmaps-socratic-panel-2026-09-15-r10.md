# Roadmaps Socratic Panel Round 10 — Synthesis Addendum (2026-09-15)

Rounds 1–9: R1 synthesis + R2–R9 addenda (R9: R9-1..R9-3 adopted, R9-4
rejected). Round 10 packet: `review-packet-roadmaps-r10-2026-09-15.md`
(deleted after synthesis). HEAD at round 10: `e5fcebd1` → this commit.

## Panel Consensus
- Decision: **AGREE WITH CHANGES — two doc-truth corrections adopted.**
  UnsweptCells found one real arithmetic defect; SelfInflicted found the
  same plus a close-date pair both lenses misread as contradiction.
  Coordinator adjudicated: G1 fix ADOPTED; close-date "fix" REJECTED (both
  dates true of different things); checklist/R8/R9 surfaces clean;
  gateway/control-plane tests correctly ungated (held surfaces).
- Use-case recommendation: **adopt** (corrections below).

## Required Wording Changes (landed in this commit)
1. G1 row parenthetical: "(1205 synthetic, 322 unknown, 65 dogfood)" →
   "(1205 synthetic, 322 unknown — of which 65 are `origin: dogfood`)".
   Source: `scripts/prepare_g1_evidence.py:187-199` — only three buckets
   exist (owner/synthetic-task-or-fixture/else-unknown); `origin: dogfood`
   falls in `unknown`. 1205+322=1527; the 65 are a subset, not a summand.
2. R8/R9 synthesis + checklist flag note: already correct in R9 (both
   scripts accept `--threshold-ms`); no change.

## Shared Findings (round 10 deltas only)
- Post-round-9 commits are bundle-only; no runs/evidence/friction/owner
  changes.
- Close-date pair is NOT a contradiction: roadmap-status:26 + m4-dogfood:13
  record the *session-date-derived* close (2026-09-15, set when the session
  was booked); ADR-0031 file + README + backlog:20 + risk report record the
  *owner-extended* close (2026-09-29, conditioned on G1–G5). Different
  decisions at different times; the 09-29 extension supersedes for action
  purposes but does not falsify the 09-15 record. Lens-proposed rewrite
  rejected: rewriting session-date history would falsify the log.
- 09-29 provenance: NOT owner-signed in-session. Earliest committed source
  is the risk report Human Review section (agent-prepared, `05bc473c`
  docs commit); findings:129 says "new close date" without naming it.
  The 09-29 date is owner-*attributed* (batch adjudication record), not
  owner-*signed*. Flagged as residual risk, not corrected (correction
  itself would need owner direction).

## Disagreements / Residual Risks
- **09-29 date authority gap**: no owner-signed line names 2026-09-29;
  strongest evidence is the risk-report Human Review section of an
  agent-committed docs commit. If the owner never set 09-29, every
  downstream table (backlog, H4 gate, ADR file, checklist) inherits the
  error. Re-litigation trigger: owner confirms or corrects the date.
- Round 1 Devil's C4 + Strategic C3/R2-5 deferrals stand.

## Evidence Actually Checked
- Coordinator: H4/G1 re-runs, falsifier loop, verify green, G1 bucket
  source reads, close-date provenance trace (`git log -S 2026-09-29`),
  risk-report + findings + backlog + ADR reads.
- UnsweptCells: never-line-read tables (M0–M6, GOV, DSK, SCL, CPP,
  critical path, B1/B3, risk body, ADR-0043) — all current except G1.
- SelfInflicted: R8/R9 edit surfaces, ledger IDs, flag sets, commit
  traces — clean except G1 + close-date pair.

## Candidate Adoption Ledger (round 10)
| ID | Candidate | Status | Evidence | Next action / trigger |
|----|-----------|--------|----------|----------------------|
| R10-1 | G1 subset phrasing | Adopted | `prepare_g1_evidence.py:187-199` three-bucket logic; 1205+322=1527 | Landed this commit |
| R10-2 | Close-date rewrite to 09-29 | Rejected | Both dates true (session-set vs owner-extended); rewriting history falsifies log | None; residual risk noted above |
| R10-3 | Gateway/control-plane parser tests | Rejected | Held surfaces; tests wait for trigger | Trigger-gated |
