# Daily-Driver Risk Register
# 2026-06-01

**Purpose.** Two risk surfaces in one register: (A) **product risks** — what the
current code does to users *today*, derived from
`daily-driver-code-grounded-ux-findings-2026-06-01.md`; and (B) **execution risks** —
what could go wrong while applying
`docs/plans/daily-driver-hardening-plan-2026-06-01.md`. This is the
`reflective-risk` gate for that plan.

**Scoring.** Likelihood × Impact, each Low/Med/High. Severity = the higher of the two
unless a single dimension is High-and-irreversible (then severity is High).

---

## A. Product risks present in the current build

| ID | Risk | Likelihood | Impact | Severity | Trigger / evidence | Mitigation (plan item) |
|----|------|-----------|--------|----------|--------------------|------------------------|
| PR-1 | `/undo` in `teaagent chat` reverts unrelated manual edits via `git checkout -- .` → **silent data loss** | Med | High (irreversible) | **High** | `chat_repl.py:418,789-799`; default checkpoint disabled (`:537`) makes the destructive path common | P0-2 |
| PR-2 | Chat REPL reports success as failure and hides the answer → users abandon in first minute | High | High | **High** | `chat_repl.py:820` (`result != 0`); answer never printed | P0-1 |
| PR-3 | Cost/budget displays are fabricated → users make spend decisions on false data; trust collapses when reality diverges | High | Med | **High** | REPL `+= 10` (`:563,825`); TUI counter never incremented (`tui:184` read-only) | P1-1 |
| PR-4 | `/compact` appears to manage context but doesn't → users believe context rot is mitigated when it isn't | Med | Med | Med | `chat_repl.py:564` only path appending observations; loop never does | P1-2 |
| PR-5 | TUI auto-clears screen on large terminals → loss of scrollback, approval prompts, prior answers | Med | Med | Med | `tui:205` `\033[2J\033[H` each loop; auto-enabled ≥120×30 (`:189`) | P1-4 |
| PR-6 | Surface drift: a fix applied to one chat path silently leaves the other wrong | High | Med | Med | Two implementations, divergent behavior (CG-05 table) | P1-3 |
| PR-7 | `/background` silently switches the user's git branch and never returns | Med | Med | Med | `chat_repl.py:130-132` `git checkout -b`, no restore (CG-09) | TICKET-3b |
| PR-8 | Background suspension bypasses the audit chain → governance hole | Med | Med-High | Med | `chat_repl.py:85-96` writes JSON `audit_trail`, no `AuditLogger` (CG-10) | TICKET-3b |

**Note:** A *spec-level* risk register (SR-1…SR-11 — risks introduced by building the
design specs) lives in `docs/plans/daily-driver-execution-readiness-2026-06-01.md`.

### Highest-priority product risk

**PR-1 (data loss)** is the only irreversible item and therefore the release blocker.
Until P0-2 ships, `docs/USAGE.md` and the REPL `/undo` help should carry an explicit
warning: *"`/undo` currently reverts all uncommitted changes in the worktree, not just
this session's edits."* — honesty now, fix next.

---

## B. Execution risks of the hardening plan

| ID | Risk | Likelihood | Impact | Severity | Mitigation |
|----|------|-----------|--------|----------|------------|
| ER-1 | P1-3 refactor (shared controller) regresses one or both daily surfaces | Med | High | **High** | Land P0-1/P0-2 *before* refactor; gate P1-3 behind the parity test (P1-3 acceptance); keep PRs small and surface-by-surface |
| ER-2 | P0-2 over-corrects and makes legitimate undo a no-op | Med | Med | Med | Route to `UndoJournal` (already proven on agent path); test both "reverts agent edits" and "leaves manual edits" |
| ER-3 | Cost numbers (P1-1) are themselves inaccurate (adapter under-reports) and re-erode trust | Med | Med | Med | Label as server-reported; show tokens alongside dollars; add a test with a known stub cost; document the source per Hermes #504 |
| ER-4 | P1-4 TUI rewrite is larger than scoped (full-screen app is a real project) | Med | Med | Med | Allow the cheap path (option b: drop auto-activation, make `state` opt-in) as an acceptable interim; full layout is a follow-up |
| ER-5 | Fixes pass tests but break a real interactive session (TTY-only behavior) | Med | Med | Med | Each phase requires a manual smoke (`teaagent chat`, `teaagent tui`) in addition to CI; use `/run` skill or `verify` skill before merge |
| ER-6 | Line numbers in findings drift before edits land | High | Low | Low | Re-anchor against the working tree at edit time; findings cite symbols + line numbers both |

---

## Rollback

- All plan changes are code edits on a feature branch — revert by dropping the
  branch/commits. No data migrations, no schema changes, no external state.
- The one operation that touches user data is `/undo` itself; P0-2 *reduces* its blast
  radius, so the change direction is strictly safer. No rollback hazard introduced.

## Human-review gate

- **PR-1 / P0-2** (data-loss path) and **P1-3** (touches both surfaces) require human
  review before merge. The remaining items are low-blast-radius and can follow normal
  review.
- This register is advisory analysis only; no code was changed producing it.

## Re-evaluation triggers

- Re-run the competitive delta (`competitive-feedback-refresh-*.md`) before any
  release claim — the cost-accuracy bar (Delta D-1) is moving monthly.
- Re-anchor all `file:line` references after Phase 0 lands, since the chat REPL will
  have changed.
</content>
