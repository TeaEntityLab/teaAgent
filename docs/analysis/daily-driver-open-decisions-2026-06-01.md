# Daily-Driver Review — Open Decisions Register
# 2026-06-01

Every point in the 2026-06-01 review that is genuinely the **maintainer's call** — not
something I should decide by default. Each has options, a recommendation, and what it
blocks. Resolve these before the corresponding work starts.

| ID | Decision | Options | Recommendation | Blocks |
|----|----------|---------|----------------|--------|
| **DQ-1** | Are P-OPS background/cloud journeys a near-term commitment or a documented non-goal? | (a) commit + build lifecycle (b) declare non-goal w/ attach recipes (F-ECO-004) | (a) if enterprise is the target; else (b) and say so loudly | journey-maps P-OPS rows; F-ECO-003/004 |
| **DQ-2** | Should P-ML parallel-experiment comparison emit a file artifact (reproducible) or stay TUI-only? | (a) write comparison evidence file (b) TUI-only | (a) — reproducibility is the ML persona's core need | evidence-bundle scope |
| **DQ-3** | P1-4 TUI: full prompt_toolkit fixed-region app, or just drop the auto-clear? | (a) real layout (medium effort) (b) drop auto-clear + opt-in `state` (small) | (b) now to stop the regression; (a) as a follow-up | CG-06 fix size; cockpit render |
| **DQ-4** | Should `prompt` mode + background be (a) auto-pre-granted, (b) refused with a message, or (c) silently allowed (current)? | a / b / c | (b) refuse with a clear message until pre-grant/JIT is set | PMR background row; PR-1 interaction |
| **DQ-5** | Cost source for display: server-reported only, local tiktoken estimate, or both labeled? | server / local / both | both, **labeled** (per Hermes #504 debate) | P1-1; cockpit budget; evidence economics |
| **DQ-6** | Consolidate undo onto `UndoJournal` and rename git-stash to `checkpoint restore` — acceptable breaking change to the `undo` verb? | (a) yes, rename (b) keep both, add docs | (a) — overlapping `undo` verbs are a recovery hazard (CG-08) | P2-1 |
| **DQ-7** | Is this volume of docs the desired working mode, or should findings go straight to GitHub issues / the existing `docs/backlog-priority.md`? | (a) keep doc package (b) issues (c) fold into backlog-priority | maintainer preference — see note below | future review cadence |

## Note on DQ-7 (and on "write as many docs as possible")

I produced a **consolidation package** (index, recommendation log, this register,
assumptions/non-goals, traceability, backlog) rather than many near-duplicate files,
because past a point more files *reduce* signal — the May-31 corpus already covers the
broad survey, and duplicating it dilutes the code-grounded findings that are the real
new value. If the intent is issue-tracker tickets or entries in
`docs/backlog-priority.md` instead of standalone docs, say so and I'll convert; that may
be the better home for actionable items.

## How to record decisions

When you resolve one, append a line here: `DQ-#: chose <option> on <date> — <one-line
why>`, and update the dependent doc. This file is the durable record of *why* the
product went one way.

---
*(Decisions log — append below)*
</content>
