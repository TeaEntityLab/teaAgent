# ADR 0040: Reconcile the Second Execution Framework with the Primary Runner

## Status

Accepted — 2026-06-20

Resolves A-P1-3 in `docs/retrospective/06-action-register.md` and G-HIGH-2 in
`docs/retrospective/03-architecture-quality.md`. Chooses option (b) of the
action: write an ADR that justifies the dual-framework design and its shared
invariants, rather than folding `SubagentManager.run_subagent` into
`runner/`.

## Context

Two execution frameworks run parallel to each other:

1. **Primary runner** — `teaagent/runner/_core.py` (`AgentRunner`): the
   canonical agent loop with budget enforcement (`runner/_core.py:957,1008`),
   audit emission (`runner/_events.py` EventSpine → audit bridge), and the
   nine-stage approval pipeline.
2. **Second framework** — `teaagent/subagents/_manager.py:205-538`
   (`SubagentManager.run_subagent`) and `teaagent/swarm.py:370-1010`
   (`SwarmManager`): recursive child runners with a custom registry/config/
   approval handler, and a parallel orchestrator with tournament selection
   and heartbeat loops.

ADRs 0019, 0022, 0028, and 0029 cover the existence of swarm/consensus/
subagents, so the `AGENTS.md:7` rule ("Do not add a second framework without
an ADR") is literally satisfied. However, no ADR reconciles the **shared
invariants** across the two execution loops: budget exhaustion, audit
emission, and approval authority must hold identically in both, or the
governance guarantees of the primary runner do not extend to subagent/swarm
runs. This doubles the correctness surface for governance.

## Decision

Retain the dual-framework architecture, but make the shared invariants
**explicit and machine-checked** so the second framework cannot silently
diverge from the primary runner on budget, audit, or approval.

### 1. Shared-invariant contract

Define a `RunnerInvariants` contract (in a new
`teaagent/runner/_invariants.py`) that both execution paths must satisfy:

- **Budget**: every execution path enforces `RunBudget.max_iterations` and
  `max_tool_calls` and emits `BudgetExceededError` at the same thresholds;
  subagent budgets are clamped to the parent's remaining budget
  (`subagents/_manager.py:52-58` already clamps; this ADR makes it a
  contract).
- **Audit**: every execution path emits `run_started`, `tool_call_started`,
  `tool_call_completed`/`_failed`, `run_completed`/`run_failed` through the
  EventSpine → audit bridge (`runner/_events.py:122-174`); the second
  framework must not bypass the bridge.
- **Approval**: every destructive tool call in either framework is
  authorized through `ApprovalManager.assert_allowed` (the nine-stage
  pipeline) or a payload-digest preapproval (ADR-0033); the second
  framework must not introduce a parallel authority path.

### 2. Machine-checked enforcement

Two layers, landed incrementally:

- **Static authority gate (landed):** `scripts/validate_runner_invariants.py`
  (alongside `validate_event_spine_wiring.py`) statically checks that the
  second framework imports/delegates to the shared ApprovalManager and audit
  bridge rather than re-implementing a parallel authority path. This is the
  load-bearing cross-framework guarantee today.
- **Invariant tests (landed):** `tests/runner/test_runner_invariants.py`
  exercises the primary `AgentRunner` path end-to-end (budget enforcement,
  audit lifecycle, read-only approval blocking), unit-tests the subagent
  budget-clamp math, and unit-tests the budget/audit/approval invariant
  comparators with representative evidence bundles.
- **Live differential (follow-up, NOT yet landed):** a parametrized test that
  runs an *identical scenario* through both `AgentRunner` and
  `SubagentManager.run_subagent` and asserts their collected budget/audit/
  approval evidence matches. Until this lands, equivalence on the second
  framework is enforced structurally (by the import gate) rather than
  behaviourally; the comparators exist so this differential can be wired in
  without new assertion logic.

### 3. Documentation

- Document the dual-framework design and its shared invariants in
  `docs/architecture/execution-frameworks.md` (new), referenced from this
  ADR and from ADRs 0019/0022/0028/0029.

### 4. Fold criterion

Folding `SubagentManager.run_subagent` into `runner/` remains a future
option. This ADR sets the fold criterion: the second framework may be
folded into the primary runner only after (a) the shared-invariant contract
has been machine-checked for two release cycles without divergence, and
(b) the swarm tournament scheduler is expressible as a runner-level
orchestration primitive. Until then, the dual-framework design is
justified by the swarm's parallel/tournament semantics that do not fit the
single-loop primary runner.

## Rationale

- Folding the second framework into the primary runner is a large refactor
  that risks regressing the swarm/tournament semantics (ADR-0028) and the
  centralized approval queue (ADR-0022); it is out of scope for the
  retrospective action register and should be paced by the fold criterion
  above.
- The shared-invariant contract makes the existing literal compliance
  *meaningful*: the second framework is only governance-equivalent if its
  budget/audit/approval behavior is proven identical, not just ADR-covered.
- Machine-checked enforcement prevents silent divergence, which is the
  actual risk identified in G-HIGH-2.

## Implementation

- `teaagent/runner/_invariants.py` (new): the `RunnerInvariants` contract
  and helper assertions.
- `tests/runner/test_runner_invariants.py` (new): parametrized tests
  across both execution paths.
- `scripts/validate_runner_invariants.py` (new): static CI gate.
- `docs/architecture/execution-frameworks.md` (new): design doc.
- `.github/workflows/ci.yml` and `.pre-commit-config.yaml`: wire the new
  static gate (NOTE: ci.yml is owned by another batch during Phase 1; this
  wiring lands in Phase 2 after that batch completes).
- `docs/adr/README.md`: index ADR-0040.

## Consequences

- **Positive**: the dual-framework design is now justified by a
  machine-checked shared-invariant contract, not just by ADR existence;
  silent divergence is detected in CI; the fold criterion gives a clear
  future path.
- **Negative**: a new CI gate and contract module to maintain; the second
  framework is not folded (the surface remains doubled until the fold
  criterion is met).
- **Migration**: none — the second framework already imports the
  ApprovalManager and EventSpine; this ADR makes that import a CI-checked
  requirement.

## Alternatives Considered

- **Fold `SubagentManager.run_subagent` into `runner/` now**: rejected —
  large refactor that risks swarm/tournament regressions and is out of
  scope for the action register; the fold criterion paces it.
- **Leave as-is, rely on existing ADRs 0019/0022/0028/0029**: rejected —
  literal compliance without a shared-invariant contract does not address
  G-HIGH-2's actual risk (silent divergence on budget/audit/approval).
- **Mark the second framework deprecated and freeze new features on it**:
  rejected — the swarm is an active feature surface (ADR-0028 tournament).

## References

- `docs/retrospective/03-architecture-quality.md` (G-HIGH-2)
- `docs/retrospective/06-action-register.md` (A-P1-3)
- `docs/adr/0019-phase-4-federated-swarm-consensus.md`
- `docs/adr/0022-centralized-approval-queue-subagents.md`
- `docs/adr/0028-tournament-swarm-architecture.md`
- `docs/adr/0029-consensus-validation-deferred.md`
- `docs/adr/0033-automode-approval-authority.md`
