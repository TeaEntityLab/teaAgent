# M4 Approval Slice B Blocked — Interceptor Misses jit_state/handler

> **Status:** Blocked by a verified correctness gap, 2026-06-13. Approval
> Slice A is committed (`2da5d6c`) and safe (interceptor + unit parity, not
> wired). Slice B (enforce cutover) must NOT land until the gap below is closed.

## The gap

The inline approval check in `AgentRunner._execute_tool_decision`
(`teaagent/runner/_core.py`, the `self.approval_policy.assert_allowed(...)` call)
passes two runtime inputs that the salvaged `ApprovalGateInterceptor`
(`teaagent/runner/_approval_manager.py`) does **not**:

```python
# inline (authoritative today):
self.approval_policy.assert_allowed(
    ..., jit_state=self.approval_manager.jit_state, handler=tool.handler, ...
)
# interceptor (would replace it in Slice B):
self._approval_policy.assert_allowed(
    ...,  # no jit_state, no handler
)
```

`ApprovalPolicy.assert_allowed` (`teaagent/policy.py`) uses `jit_state` to merge
the session's JIT `approved_call_ids` / `session_approved_tools` into the
decision (verified lines ~23-27 of the method). Without it, a call that the
session has JIT-approved would be **denied** by the interceptor while the inline
path **allows** it — a behavior regression in enforce mode. `handler` is
similarly forwarded and may affect handler-gated decisions.

## Why the unit parity test didn't catch it

`test_approval_gate_interceptor_parity` constructs **fresh** `ApprovalPolicy`
objects per scenario with no JIT/session state, so interceptor and inline agree
trivially. The divergence only appears with live `jit_state` — exactly the
state the interceptor cannot see. The parallel tool's collapsed M4 batch had the
same incomplete interceptor; its acceptance pass did not exercise a
JIT-approved-then-enforced path, so the latent regression went unobserved.

## Fix design (for Slice B, before enforce)

1. Give the interceptor access to JIT state — either hold a reference to the
   `RunnerApprovalCoordinator`/`jit_state`, or carry `jit_state` + `handler`
   in the `TOOL_CALL_REQUESTED` payload (payload route keeps the interceptor
   pure but means putting a callable `handler` in an event payload, which is
   ugly and pollutes the audit stream — prefer the reference route).
2. Extend the **parity test** to cover a JIT-approved call and a
   session-approved tool, asserting interceptor == inline **with** live
   jit_state. This is the assertion that was missing.
3. Only then: register enforce + remove the inline `assert_allowed`
   (Slice B), with the JIT parity test green.

## Current state

- Committed and safe: `5b5f007` (PlanGateError), `2da5d6c` (approval Slice A:
  interceptor + unit parity, **not wired** — zero behavior change).
- NOT done: approval Slice B (this blocker), budget Slice A, budget Slice B.
- The parallel tool's full collapsed M4 remains in `git stash@{0}`
  ("parallel-tool-M4-collapsed-batch-salvage-2026-06-13") for salvage —
  note it shares this jit_state/handler gap.
- Budget gate has its own trap (see §15 family): the budget interceptor can
  emit `budget_warning` audit events, so a shadow budget interceptor must NOT
  be given `audit=` while inline budget warnings remain, or warnings
  double-write.

---

## Update — reference approach attempted, deeper coupling found (2026-06-13)

Per the owner's "use the reference approach" decision, I extended the
interceptor to recover the runtime inputs (jit_state via a provider callable,
handler via a registry reference). That closes gaps 1-2. But wiring Slice B
surfaced a **third** runtime-coupling gap:

3. **`self.approval_policy` is swapped at runtime by auto-mode.** In
   `_execute_tool_decision`, after the `TOOL_CALL_REQUESTED` emit,
   `get_auto_approve_policy()` may reassign `self.approval_policy`
   (`_core.py` ~line 664-665). The inline `assert_allowed` then runs against
   the *new* policy. An interceptor that captured `approval_policy` at
   construction holds the *stale* reference → divergence under auto-mode. Fix
   would require a policy **provider** too (and re-ordering the emit after the
   swap).

## Architectural finding and recommendation (owner decision needed)

The plan gate moved to an interceptor cleanly because it is nearly stateless
(`evaluate_write_gate` over context). The **approval gate is deeply
runtime-coupled**: its decision depends on (1) live JIT/session state,
(2) the tool handler, and (3) a permission policy that auto-mode can swap
mid-call — none of which live in the event payload. Making the interceptor
faithful means turning it into a thin shim that reaches back into runner state
for *all three* via providers. That is doable but couples the "pure interceptor
on an event" model tightly to runner internals, and each provider is a
regression surface (gaps 1-3 were each invisible to the unit parity test).

**Two honest options for the owner:**

- **(A) Heavy shim:** give the interceptor policy/jit_state/handler providers,
  re-order the emit after the auto-mode swap, and extend the parity test to
  cover JIT-approved, handler-gated, and auto-mode-swapped cases. Completes the
  spine vision (approval is an interceptor) at the cost of coupling.
- **(B) Leave approval inline (recommended):** keep the approval gate as a
  runner concern (it is legitimately stateful), and have the spine carry an
  approval *observability* event (e.g. emit the decision as a consumer-only
  event for evidence/receipts) rather than moving enforcement into an
  interceptor. The spine/interceptor model fits stateless gates (plan); forcing
  a stateful gate into it is the source of every gap here.

Budget gate (still pending) is closer to plan (cost thresholds) than to
approval, so it is likely interceptor-suitable — but should be assessed after
this decision.

## Current committed state (unchanged, clean)

`bcd9369` is HEAD-ish for this thread: PlanGateError (`5b5f007`) + approval
Slice A (`2da5d6c`, interceptor + unit parity, NOT wired) + this report. No
enforce cutover landed. Working tree clean.

---

## RESOLVED — Owner chose (B), 2026-06-13

The owner chose **option (B): approval enforcement stays inline.** The approval
gate is legitimately runtime-stateful (live JIT/session state, tool handler,
auto-mode-swappable policy) and is NOT moved to an EventSpine interceptor.

Actions taken:
- Reverted approval Slice A (`2da5d6c`) — the `ApprovalGateInterceptor` and its
  unit/parity tests — via revert commit, since under (B) it is unused code and
  unused code is drift. Approval enforcement is back to its proven inline path,
  unchanged.
- **Approval observability needs no new code:** the approval audit events
  (`tool_call_approved`, `tool_call_denied`, `tool_call_pending_approval`,
  `approval_*`) were already typed in M2-T002 and are surfaced by the M2-T001
  reader from the audit JSONL. So the spine carries approval *observability*
  (for evidence/receipts via the M6 fold) without moving enforcement.
- `PlanGateError` (`5b5f007`) is retained: harmless under (B) and a small
  improvement (plan blocks no longer show the misleading "approve this" hint).
  Its original approval-coexistence justification no longer applies.

**Net M4 redefinition:** M4 = budget gate only. The plan gate (M3) is the one
governance gate that moved to an interceptor; approval stays inline by design.
