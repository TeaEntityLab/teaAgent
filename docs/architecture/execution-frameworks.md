# Execution Frameworks — Dual-Framework Design

> ADR 0040: Reconcile the Second Execution Framework with the Primary Runner
> Accepted 2026-06-20

TeaAgent runs two execution frameworks in parallel, justified by different
semantics: the single-loop primary runner and the parallel tournament/swarm
second framework. This document describes both paths, their shared invariants,
and the machine-checked contract that prevents silent divergence.

## Primary runner — AgentRunner

- **Module**: `teaagent/runner/_core.py`
- **Semantics**: single-loop agent cycle — decide, dispatch, enforce, audit.
- **Budget**: `RunBudget.max_iterations` and `max_tool_calls` enforced inline
  in the `run()` loop at lines 957 and 1008.
- **Audit**: all lifecycle events (`run_started`, `tool_call_started`,
  `tool_call_completed`/`_failed`, `run_completed`/`_failed`) flow through
  the `EventSpine` → audit bridge (`runner/_events.py:122-401`).
- **Approval**: destructive calls pass through `ApprovalPolicy.assert_allowed`
  (the nine-stage pipeline) or payload-digest preapproval (ADR-0033).

## Second framework — SubagentManager / SwarmManager

- **Modules**: `teaagent/subagents/_manager.py:205-538`, `teaagent/swarm.py:370-1010`
- **Semantics**: recursive child runners (`SubagentManager.run_subagent`) and
  parallel tournament orchestrator (`SwarmManager`) with worktree isolation
  and heartbeat loops.
- **Budget**: subagent budgets are **clamped** to the parent's remaining
  budget by `_resolve_budget_limits` (`_manager.py:52-58`).
- **Audit**: delegates to `run_chat_agent` which uses the same `EventSpine` →
  audit bridge as the primary runner.
- **Approval**: `SubagentManager._build_approval_handler` routes through the
  centralized approval queue (ADR-0022); destruction authority stays within
  `ApprovalManager.assert_allowed`.

## Shared invariants (machine-checked)

ADR 0040 defines three invariants that both frameworks must satisfy identically:

### 1. Budget

Every execution path enforces `RunBudget.max_iterations` and `max_tool_calls`
and emits `BudgetExceededError` at the same thresholds. Subagent budgets are
clamped to the parent's remaining budget.

- **Contract**: `teaagent/runner/_invariants.py` → `assert_budget_invariant`
- **Test**: `tests/runner/test_runner_invariants.py` → `TestBudgetInvariant`
- **CI gate**: `scripts/validate_runner_invariants.py` checks import paths

### 2. Audit

Every execution path emits `run_started`, `tool_call_started`,
`tool_call_completed`/`_failed`, `run_completed`/`run_failed` through the
`EventSpine` → audit bridge. The second framework must not bypass the bridge.

- **Contract**: `teaagent/runner/_invariants.py` → `assert_audit_invariant`
- **Test**: `tests/runner/test_runner_invariants.py` → `TestAuditInvariant`
- **CI gate**: import-path check ensures both frameworks use `teaagent.runner._events`

### 3. Approval

Every destructive tool call in either framework is authorized through
`ApprovalManager.assert_allowed` or a payload-digest preapproval (ADR-0033).
The second framework must not introduce a parallel authority path.

- **Contract**: `teaagent/runner/_invariants.py` → `assert_approval_invariant`
- **Test**: `tests/runner/test_runner_invariants.py` → `TestApprovalInvariant`
- **CI gate**: import-path check ensures both frameworks use `teaagent.approval_manager`

## Architecture diagram

```
User Task
    │
    ├── Primary Runner (AgentRunner)
    │   ├── budget: RunBudget.max_iterations / max_tool_calls
    │   ├── audit:  EventSpine → AuditLogger.record
    │   └── approve: ApprovalManager.assert_allowed
    │
    └── Second Framework (SubagentManager / SwarmManager)
        ├── budget:  clamped → parent's remaining budget
        │            (_resolve_budget_limits, _manager.py:52-58)
        ├── audit:   same EventSpine → AuditLogger.record
        │            (delegates to run_chat_agent → AgentRunner)
        └── approve: centralized approval queue OR
                     delegated to parent's ApprovalManager
                     (no parallel authority path)

Shared invariants (checked at CI and test time):
  ┌──────────────────────────────────────────────────┐
  │  RunnerInvariants contract                        │
  │  ├── assert_budget_invariant                      │
  │  ├── assert_audit_invariant                       │
  │  └── assert_approval_invariant                    │
  │                                                   │
  │  tests/runner/test_runner_invariants.py           │
  │  scripts/validate_runner_invariants.py            │
  └──────────────────────────────────────────────────┘
```

## Fold criterion

Folding `SubagentManager.run_subagent` into `runner/` remains a future option
(ADR 0040 §4). The fold criterion requires:

1. The shared-invariant contract has been machine-checked for **two release
   cycles** without divergence, and
2. The swarm tournament scheduler (ADR-0028) is expressible as a runner-level
   orchestration primitive.

Until then, the dual-framework design stands.

## References

- [ADR 0040](../adr/0040-second-framework-invariants.md) — full decision record
- [ADR 0019](../adr/0019-phase-4-federated-swarm-consensus.md) — swarm consensus
- [ADR 0022](../adr/0022-centralized-approval-queue-subagents.md) — centralized approval queue
- [ADR 0028](../adr/0028-tournament-swarm-architecture.md) — tournament architecture
- [ADR 0029](../adr/0029-consensus-validation-deferred.md) — consensus validation
- [ADR 0032](../adr/0032-run-event-taxonomy.md) — event spine and taxonomy
- [`teaagent/runner/_invariants.py`](../../teaagent/runner/_invariants.py) — shared-invariant contract
- [`tests/runner/test_runner_invariants.py`](../../tests/runner/test_runner_invariants.py) — parametrized tests
- [`scripts/validate_runner_invariants.py`](../../scripts/validate_runner_invariants.py) — static CI gate
