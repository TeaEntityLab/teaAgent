# Daily-Driver Findings — Second Pass (Reconsideration)
# 2026-06-01

**Why this doc exists.** A deliberate re-audit of the daily surfaces to (a) catch
findings the first pass missed, (b) re-examine the severity of existing findings, and
(c) state honestly what is *still* uncovered. Triggered by the question "reconsider all
risks and gaps." Findings here continue the `CG-##` numbering from
`daily-driver-code-grounded-ux-findings-2026-06-01.md`.

---

## New findings (missed by the first pass)

### CG-09 — `/background` is misleading and silently switches your git branch  [P1]

**Evidence.** `chat_repl.py::suspend_to_background`:
- `chat_repl.py:130-132` — `git checkout -b <branch>` creates **and switches to**
  `suspended-<run_id>`, and **never switches back**. The user is left on a new branch
  without a clear statement that their HEAD moved.
- `chat_repl.py:150` — prints *"Background execution requires manual setup"* — i.e. **no
  background execution actually happens**.
- `chat_repl.py:640-648` — but the caller announces *"Interactive session converted to
  background task"* and *"You can now safely exit the REPL."*

So `/background` claims a capability it does not deliver and mutates git state as a side
effect. This is a UX-F4 "confident misreport" plus a workflow-surprise data risk.

**Divergence.** The TUI's `_handle_background` (`tui/__init__.py:717-720`) just prints
*"use teaagent agent run --detach"* and does nothing — so the same verb means two
entirely different things across surfaces (reinforces **CG-05**).

**Why P1 (not P0).** It does not destroy file contents (unlike CG-02), but it silently
relocates the user's branch and misrepresents the outcome. Until fixed, the help text
and printed messages should state plainly: *"creates a branch snapshot; does not run
anything in the background; you remain on the new branch."*

**Fix direction.** Either (a) wire `/background` to the real detach path
(`agent run --detach`) so the claim is true, or (b) demote it to an honest
`/snapshot` that says exactly what it does and restores the original branch. Tie to
**DQ-1** (background commitment vs non-goal).

---

### CG-10 — Background suspension bypasses the audit chain  [P1]

**Evidence.** `suspend_to_background` writes an `audit_trail` dict
(`chat_repl.py:85-90`) **into the local suspension JSON file** (`:92-96`) and creates a
git branch — but never calls the real `AuditLogger`/audit chain (contrast the governed
run path in `tui/__init__.py:776-782`, which uses `store.audit_logger()` and an
`UndoJournal`). The `audit_trail` key is self-described JSON, not a tamper-evident event.

**Why P1.** Audit-everything is teaagent's stated core differentiator (UX-F7, security
whitepaper). A state-changing operation (branch creation, file writes) that is invisible
to the audit chain is a governance hole — exactly the gap enterprises cite (only 21%
have runtime visibility; 33% have no audit trail, per the May-31 survey §4).

**Fix direction.** Route suspension through the audit logger (emit a
`session_suspended` event with branch + file refs) so background transitions are
auditable. Couple with CG-09's fix.

---

## Severity re-examination of first-pass findings

| ID | First-pass | Re-examined | Rationale |
|----|-----------|-------------|-----------|
| CG-01 | P0 | **P0 (confirmed)** | Type mismatch is unambiguous; primary surface broken |
| CG-02 | P0 | **P0 (confirmed)** | Only irreversible/data-loss item; release blocker |
| CG-03 | P1 | P1 (confirmed) | Misleads but does not corrupt; competitive table-stakes |
| CG-04 | P1 | **P1→P2 (consider)** | Operator-visible compaction is theater, but `run_chat_agent` may manage real context internally — *user harm is "false reassurance," not lost work*. Could drop to P2 if internal context is sound. **Needs the P1-2 test to decide.** |
| CG-05 | P1 | **P1→escalate** | Root cause of CG-01/02/03/09; the divergence keeps producing new bugs (CG-09 is fresh proof). Treat as the *first* structural fix, not a late one |
| CG-06 | P1 | P1 (confirmed) | Auto-on for power users; named switching-trigger |
| CG-07 | P2 | P2 (confirmed) | Fails loudly ("not implemented") |
| CG-08 | P2 | P2 (confirmed) | Ambiguity, not loss |

**Net change:** +2 findings (CG-09, CG-10, both P1). CG-05 escalated in *sequencing*
priority (do it early). CG-04 flagged as possibly-overstated pending its test.

---

## Completeness audit — are all risks & gaps now covered?

### Survey themes (UX-F#)

| Theme | Status after second pass |
|-------|--------------------------|
| UX-F1 caps | covered (CG-03 / P1-1) |
| UX-F2 autonomous changes w/o permission | **covered by existing governance** — approval flow gates destructive tools; no finding contradicts it. *Residual:* verified by reading, not by an adversarial test (see residual R-2) |
| UX-F3 context rot/rendering | covered (CG-04, CG-06, CG-07) |
| UX-F4 silent/irreversible | covered (CG-01, CG-02, CG-08, **CG-09, CG-10**) |
| UX-F5 onboarding | covered (CG-01) |
| UX-F6 cost | covered (CG-03) |
| UX-F7 trust under autonomy | covered (governance + **CG-10** is the new gap) |
| UX-F8 IDE lock-in | structural advantage; not a defect (IDE spec covers parity) |

### Ecosystem gaps (F-ECO-###)

All 13 (002–014) now have a spec or an explicit decision/non-goal (see INDEX). F-ECO-003
(background) is **directly implicated by CG-09/CG-10** — the background story is not just
"thin," it is *misleading* in the REPL. This raises F-ECO-003's priority.

---

## Residual risks (honestly stated — what this review still cannot guarantee)

- **R-1 (static analysis).** All `CG-##` findings are from reading, not execution. The
  hardening plan attaches a test to each; until those run, severities are
  evidence-based estimates. CG-04 is the most likely to move.
- **R-2 (no adversarial test of UX-F2).** I confirmed the approval gate by reading, not
  by trying to make the agent act without approval. A negative test
  (`test_destructive_tool_requires_approval_all_modes`) should be added to *prove* it.
- **R-3 (surfaces not exhaustively read).** I read TUI, chat REPL, run_summary, and the
  modules behind the 11 specs. I did **not** fully read: `swarm.py`, `consensus.py`,
  `tournament/`, `gateway/`, `control_plane_*`, `federated_sync.py`. Findings do not
  cover those; they are out of the daily-driver scope but are *not* certified clean.
- **R-4 (spec risks unassessed until now).** The 11 design specs could each introduce
  new risk when built — assessed in `daily-driver-execution-readiness-2026-06-01.md`
  (the `SR-#` register).
- **R-5 (line drift).** All `file:line` refs are against branch
  `codex/plan-exec-2026-05-31` at 2026-06-01; re-anchor before editing.

## Updates to other docs (apply these)

- Add **CG-09, CG-10** to the recommendation log §1 and the traceability matrix.
- Add **PR-7 (branch-switch surprise)** and **PR-8 (unaudited suspension)** to the risk
  register.
- Raise **F-ECO-003** priority in the journey-maps P-OPS section.
</content>
