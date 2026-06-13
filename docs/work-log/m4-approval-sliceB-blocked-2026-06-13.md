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
