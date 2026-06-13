# M4 Budget Gate Stays Inline — Interceptor-Suitability Assessment

> **Status:** RESOLVED — owner chose **B-analog: budget enforcement stays
> inline**, 2026-06-13. No budget interceptor shipped. This mirrors the approval
> resolution (decision B) and closes M4 with **no gate moved beyond the plan
> gate (M3)**.

## Why this assessment ran first

Per the work plan §7 (M4 row) and §13.3, the budget gate's first required step
is an interceptor-suitability assessment, not an immediate parity-first slice.
The approval gate taught the lesson the hard way: a unit parity test hid three
runtime-coupling gaps, and enforce-cutover would have regressed JIT-approved
calls (`m4-approval-sliceB-blocked-2026-06-13.md`). So budget was assessed
against the observable code before any interceptor was written.

## Finding: the "budget gate" is three distinct mechanisms, not one

| Mechanism | Inline impl (`teaagent/runner/_core.py`) | State / coupling | Interceptor-suitable? |
|---|---|---|---|
| **Global cost cap** | `_assert_cost_budget` (~line 213) | Pure function of `(cost_cents, budget.max_estimated_cost_cents)`; raises `BudgetExceededError` | **Yes** — the plan-gate analog |
| **Phase budget** | `_check_phase_budget` (~line 246) | Reads live `self.phase_tracker` (current phase, phase iterations/tool-calls/cost); emits `phase_budget_warning`; raises | No — runtime-stateful (like approval) |
| **Warning ladder** | `_check_budget_warnings` (~line 296) → `BudgetMonitor.check_at_threshold` | `self._budget_warning_levels_emitted` **and** `BudgetMonitor._emitted_levels` / `_prompted` dedup sets; **interactive `on_prompt` side-effect** (`budget_monitor.py:167-176`); emits `budget_warning` / `budget_prompt` / `budget_read_only_suggested`; may raise `RunCancelledError` | No — strictly worse than approval |

So only ~⅓ of the gate (the global cost cap) is genuinely stateless.

## Two hard blockers (evidence-backed)

### 1. The warning ladder hits the exact `assert_allowed` shadow-coexistence trap

`BudgetMonitor.check_at_threshold` (`teaagent/budget_monitor.py:108-129`) is
**side-effecting**: it mutates `self._emitted_levels` (line 121) and invokes
`on_prompt` (line 169, an interactive handler returning a bool that advances
`_prompted`). This is the same shape as `ApprovalPolicy.assert_allowed`, whose
side effects made a shadow interceptor unable to coexist with the inline path.
A shadow budget interceptor calling `check_at_threshold` alongside the inline
call would either:

- **double-fire** `on_prompt` / double-emit `budget_warning`, or
- if the dedup set is shared, **silently swallow** the inline call (whichever
  runs first marks the level emitted) — a covert cutover, not a shadow.

The previously documented `budget_warning` double-emit trap is one instance of
this larger side-effect problem.

### 2. Even the clean piece does not map 1:1 to events

The global cost cap is enforced at **two evolving-cost points per iteration**:

- `_core.py:948` — before `decide()`, with the prior iteration's `cost_cents`
  (fail-fast before spending more);
- `_core.py:966` — after `_read_usage()` refreshes `cost_cents` with the cost of
  the model call just made (catch this iteration's overspend).

`ITERATION_STARTED` fires once at `_core.py:936-938`, **before both**, and its
payload is only `{'iteration': iterations}` — it does not even carry
`cost_cents` (a loop-local). An `ITERATION_STARTED` interceptor could only
approximate the line-948 semantics; covering the line-966 post-usage check would
require emitting a **new** post-usage event into the audit stream — scope creep
for marginal value.

## Decision and rationale

**Owner chose B-analog: budget enforcement stays inline.** The decision-B logic
("runtime-stateful gates stay inline; do not force them into the
interceptor-on-event model") applies *more* strongly to budget than it did to
approval: budget has a side-effecting interactive handler, two mutable dedup
sets, a live phase-tracker dependency, *and* a multi-point evolving-cost
enforcement pattern with no clean event mapping.

The alternatives were weighed and rejected:

- **Narrow cost-cap-only slice:** moves ~⅓ of the gate, still needs a new
  post-usage event for the line-966 check, and leaves the stateful majority
  inline — high overhead, low value.
- **Full heavy shim:** providers for phase-tracker / dedup sets / `on_prompt` +
  new events — the exact coupling we rejected for approval, at greater cost.

## Consequences

- **No budget interceptor ships.** Budget warning/prompt/exhausted/phase
  behavior is **unchanged** — the proven inline paths stay authoritative.
- **Budget observability already reaches the M6 fold via M2:** the audit events
  `budget_warning`, `budget_prompt`, `budget_read_only_suggested`,
  `phase_budget_warning` are typed in `RunEventType` and surfaced by the
  M2-T001 reader from the audit JSONL. The spine carries observability without
  owning enforcement — identical shape to the approval resolution.
- **The parallel tool's salvage stash (`stash@{0}`) is now fully superseded** —
  both interceptors it held (`ApprovalGateInterceptor`, `BudgetGateInterceptor`)
  are decided-unneeded. Dropped (recoverable via git reflog for ~90 days if
  ever needed).

## Net M4 outcome

**M4 closes with no gate moved beyond M3.** The plan gate (M3) is the sole
governance gate that became an EventSpine interceptor. Approval and budget are
both legitimately runtime-stateful and stay inline by evidenced architectural
finding. The strangler migration's remaining value is on the read side:
M5 (HookRegistry on spine), M6 (evidence + receipt fold over the typed stream),
M7 (ContextBus + webhook consumers).
