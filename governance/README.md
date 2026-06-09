# Governance — Governed Agentic Engineering for teaagent

> **One line:** Spec is the steering wheel, tests are the brakes, trace is the dashcam,
> runtime guardrails are the lane barriers, human review is the traffic light at high-risk junctions.

This directory holds the **Governed Agentic Engineering** framework adopted by teaagent, the
**adoption plan** for wiring it into the repo, and the **live governance artifacts** (specs, test
matrices, agent rules, feedback log). Governance strength scales with risk — see the §4 cost model in
the framework doc. Low-risk changes pass through with almost none of this; only L3 (auth / payment /
permission / migration / delete / deploy) pays the full cost.

## Map of this directory

| Path | What it is | When you touch it |
|---|---|---|
| [framework/GOVERNED-AGENTIC-ENGINEERING.md](framework/GOVERNED-AGENTIC-ENGINEERING.md) | The full methodology (2026 fact-corrected). Core values, strategies, tactics, cost model, evidence. | Reference. Read once, cite often. |
| [plans/ADOPTION-ROADMAP.md](plans/ADOPTION-ROADMAP.md) | Layer A — risk-scaled roadmap to adopt the framework into teaagent. | When planning the rollout. |
| [plans/SURF-010-EXECUTABLE-PLAN.md](plans/SURF-010-EXECUTABLE-PLAN.md) | Layer B — file-level executable plan applying the framework to the committed resume-parity change. | The concrete first application. |
| [AGENT_RULES.md](AGENT_RULES.md) | Environment-hardening rules (Allowed / Forbidden / Requires Human Review). | Every agent task. |
| [DONE_CHECKLIST.md](DONE_CHECKLIST.md) | Definition-of-done gate before a change is called complete. | Before claiming "done". |
| [LOCAL_FEEDBACK.md](LOCAL_FEEDBACK.md) | Failure-learning log. No fix is real without Evidence + Anti-regression Rule. | After every failure / correction. |
| [templates/SPEC.template.md](templates/SPEC.template.md) | Copy-to-start spec skeleton (T1). | New L2/L3 change. |
| [templates/TEST_MATRIX.template.md](templates/TEST_MATRIX.template.md) | Copy-to-start test-matrix skeleton (T2). | New L2/L3 change. |
| [specs/](specs/) | Live specs. `SURF-010-resume-parity.md` (resume trust inputs) + `approval-store-permission-binding.md` (CV-8 boundary of the grant engine). | Per change / per L3 module. |
| [test-matrices/](test-matrices/) | Live test matrices + gap analyses. First: `SURF-010.md`. | Per change. |

## The nine-stage workflow (quick reference)

```
Intent Capture → Spec Draft → Spec Quality Gate → Permission Binding
  → Test Matrix → Controlled Generation → Verification
  → Trace / Diff Review → Local Feedback (Spec Repair)
```

## How to start a new change (the short version)

1. Decide the risk level (L1 / L2 / L3) using the cost model. L1 → just do it with existing tests.
2. L2 / L3 → copy `templates/SPEC.template.md` into `specs/<ticket>.md`, fill the five columns.
3. Pass the **Spec Quality Gate** checklist (bottom of the spec template).
4. L3 only → fill Permission Binding (Allowed / Forbidden / Requires Human Review).
5. Copy `templates/TEST_MATRIX.template.md`, ensure P0 (security / data / money / permission) is covered.
6. Implement under `AGENT_RULES.md` constraints.
7. Verify against `DONE_CHECKLIST.md`. Log any failure in `LOCAL_FEEDBACK.md`.

_Status: framework adopted 2026-06-09. First live application: SURF-010 (HEAD `c37e181`)._
