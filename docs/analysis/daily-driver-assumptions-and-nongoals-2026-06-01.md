# Daily-Driver Review — Assumptions & Non-Goals
# 2026-06-01

Explicit log of every premise the review relied on, and every exclusion it recommends.
Stating these makes the review falsifiable: if an assumption is wrong, the conclusions
it supports should be re-examined.

## Assumptions (premises the review depends on)

| ID | Assumption | If false… | Confidence |
|----|------------|-----------|:----------:|
| **AS-1** | "cx skill" in the request meant the `cx-cli` code-analysis tool used in this repo, not a Claude skill | Re-route to that tool; findings unaffected (they came from direct reads) | H |
| **AS-2** | `run_chat_agent` returning `RunResult` is the contract the REPL should honor (not an int) | CG-01 fix changes; but the initial-task path at `chat_repl.py:560` already assumes `RunResult`, so AS-2 is corroborated in-tree | H |
| **AS-3** | `_session_cost_cents` not being incremented is a bug, not an intentional always-zero placeholder | CG-03 severity drops to cosmetic; the UI still misleads | H |
| **AS-4** | The May-31 corpus is accurate and current enough to build on (not re-survey) | Would need a full re-survey; the June-1 delta partially hedges this | M |
| **AS-5** | Line numbers reflect branch `codex/plan-exec-2026-05-31` working tree at 2026-06-01 | Re-anchor before editing; symbols also cited as backup | H |
| **AS-6** | Static reading is sufficient to assert CG-01/CG-02/CG-03 without executing | The plan attaches a regression test to each, converting assertion → executable proof | M-H |

## Recommended non-goals (what this review says to *exclude*)

| ID | Non-goal | Rationale | Source |
|----|----------|-----------|--------|
| **NG-1** | Do **not** regenerate the May-31 broad UX survey | Already strong; duplication dilutes signal | J-1 |
| **NG-2** | Do **not** write an IDE/desktop packaging plan in this pass | Concerns "partial" code not yet read; would be speculation | J-10 |
| **NG-3** | teaagent should **not** become a second LangGraph/CrewAI workflow framework | Product contract; keep tool-governance + audit central, domain logic outside | GAP F-ECO-014 |
| **NG-4** | The evidence bundle is **not** a replacement for the audit log/trace/replay | It is the closing summary layer, not a new store | EVB |
| **NG-5** | The cockpit contract is **not** a real-time streaming dashboard rewrite | Scope is parity + completeness of one snapshot | CKP |
| **NG-6** | Do **not** keep generating near-duplicate documents for volume alone | Past a point, more files reduce signal; prefer consolidation | DQ-7 |

## Constraints honored

- **No code changed** — analysis and docs only.
- **No external publishing** — all artifacts are local files under `docs/`.
- **Sourced research** — every external claim in the competitive refresh links a URL.
- **Falsifiability** — each finding cites `file:line`; each fix specifies a test.

## How to use this file

Before acting on any conclusion, check the assumption(s) it rests on here. If you
invalidate an assumption (e.g. AS-3 turns out intentional), annotate it and re-grade
the dependent finding in the recommendation log.
</content>
