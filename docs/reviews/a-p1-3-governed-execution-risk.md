# Reflective-Risk Report: Governed-Execution Budget Extraction (A-P1-3)

ADR 0041 Phase 1, gate G1 (budget dimension). Date: 2026-06-30.
High-risk path touched: `teaagent/runner/_core.py`.

## Goal

Extract the primary runner's per-iteration **budget enforcement** (cost ceiling,
phase budget, graduated cost warnings) from `teaagent/runner/_core.py` into a
shared `teaagent/runner/_governed_execution.py` layer that `AgentRunner`
delegates to, so the budget invariants are defined once and inherited by
subagents (which execute through `AgentRunner` via `run_chat_agent`).
Behavior-preserving; no approval/authorization or policy change.

## Stakeholders

Harness maintainers; every agent run (primary + subagent) relies on correct
budget enforcement; the governance gates of ADR-0009 / ADR-0040.

## Assets at Risk

- Budget-enforcement correctness (overspend protection).
- Audit event stream shape (`phase_budget_warning`, `budget_warning`,
  `budget_prompt`, `budget_read_only_suggested`).
- Run-loop control flow (`BudgetExceededError` / `RunCancelledError` propagation).

## Threat Model

A subtle behavior change during extraction could (a) fail to raise on an
over-budget run (overspend), (b) change audit event order/fields (breaks audit
consumers / schema), or (c) alter the exception type so the run loop mishandles
it.

## Assumption Audit

- ASSUMPTION: `self.budget`, `self.phase_tracker`, `self.audit`,
  `self._budget_monitor`, and `self._budget_warning_levels_emitted` are never
  reassigned after `__init__`. VERIFIED by reading `_core.py` — set once; the
  warning set is mutated in place (`.add`), not reassigned. A context built once
  holding the same references therefore stays in sync.
- ASSUMPTION: the three methods read no other mutable `self` state. VERIFIED by
  reading the bodies — only the five collaborators above.

## Evidence Check

- The extracted functions are a verbatim copy of the original method bodies,
  parameterized over a `GovernedExecutionContext` of the same collaborators (the
  diff is a pure move).
- Method signatures are unchanged; all run-loop call sites are untouched.

## Authority / Tool Boundary

- In scope: `teaagent/runner/_core.py` (3 budget method bodies + one `__init__`
  context construction), new `teaagent/runner/_governed_execution.py`,
  `scripts/validate_runner_invariants.py`, tests, ADR.
- Out of scope (explicitly deferred): `_authorize_tool_call` / approval-policy
  extraction; sandbox; audit chain; policy semantics.

## Failure Modes

- Import cycle (`runner` <-> new module): mitigated — the module imports only
  leaf modules (`errors`/`budget`/`budget_monitor`/`phase_tracker`/`audit`);
  import smoke passes.
- Context desync if a collaborator is reassigned in future: guarded by the
  no-reassignment invariant (documented in the module) and the full test suite.

## Worst-case Scenario

A budget check silently stops raising, so a run overspends its cost cap. Bounded
by the full budget/runner suites and the live differential test, which assert
enforcement still triggers; a regression fails CI before merge.

## Safe Dry-run Plan

Behavior-preserving pure move, verified offline by running the existing budget,
runner, governance, and subagent suites (93 passed) plus the live differential
test and new unit tests — no production run, no external I/O.

## Rollback Plan

`git revert` the commit. The change is additive (one new module) plus three
method-body delegations and a static gate; reverting restores the inline methods
exactly. No data migration, no persisted-state change.

## Bounded Execution

Single commit; only the files listed above; no network; no destructive ops;
verified by local test suites and the runner-invariant gate before commit.

## Audit Log Plan

Audit emission is byte-identical: every `audit.record(...)` call moved verbatim
into the shared functions. No audit event added or removed.

## Human Review Required

Yes — high-risk path (`teaagent/runner/_core.py`). This report is the
reflective-risk artifact; the `check-high-risk-paths` pre-commit hook gates the
commit on its presence.

## Human Approval Gate

Owner authorized the G1 extraction in-session. Budget dimension only; the
higher-blast-radius `_authorize_tool_call` extraction remains deferred to a
separate report and review.

## Acceptance Criteria

- `_governed_execution.py` owns budget enforcement; `AgentRunner` delegates to it.
- All existing budget / runner / governance / subagent tests pass unchanged.
- `validate_runner_invariants.py` passes and now gates `_core.py` -> shared layer.
- ruff + mypy clean; the G3 differential test stays green.

## Go / No-go Decision

**GO** for the budget dimension — bounded, behavior-preserving, fully verified,
trivially reversible. **NO-GO** for bundling `_authorize_tool_call` into this
change: it reassigns `ApprovalPolicy` and calls run-summary emission, a larger
blast radius that warrants its own reflective-risk report and review.
