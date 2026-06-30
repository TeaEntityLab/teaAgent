# Reflective-Risk Report: Authorization Extraction (A-P1-3)

ADR 0041 Phase 1, gate G1 (authorization dimension). Date: 2026-06-30.
High-risk path touched: `teaagent/runner/_core.py`.
Companion to `docs/reviews/a-p1-3-governed-execution-risk.md` (budget dimension).

## Goal

Move `AgentRunner._authorize_tool_call` — the per-tool-call approval pipeline
(file-policy gate, event-spine permission gate, auto-mode scoping,
preapproved-payload-digest checks, `ApprovalPolicy.assert_allowed`, and the
approval-request/blocked handling) — into the shared
`teaagent/runner/_governed_execution.py` layer as `authorize_tool_call(runner, …)`.
This completes the G1 shared governed-execution layer (budget already landed in
the companion report); both budget and authorization now live in one named
module. Behavior-preserving; no policy semantics changed.

## Stakeholders

Harness maintainers; every agent run (primary + subagent — subagents execute
through `AgentRunner`); the approval/governance gates of ADR-0009 / ADR-0040;
security reviewers (this is the approval boundary).

## Assets at Risk

- **Approval correctness** — the gate that decides whether a (possibly
  destructive) tool call may run. The single most security-critical path.
- Audit event stream (`tool_call_approved` with `authority_type`
  `auto_mode` / `preapproved_payload_digest`; blocked-request records).
- `ApprovalPolicy` scoping state (`runner.approval_policy` is reassigned to the
  auto-mode scoped policy mid-method).
- Pending-approval terminal path (emits run summary, raises `ToolPermissionError`).

## Threat Model

A subtle change during extraction could (a) approve a call that should be
denied (privilege escalation / unapproved destructive op), (b) drop or reorder
audit records (weakens the approval audit trail), (c) fail to persist the
auto-mode `approval_policy` reassignment so later calls use the wrong policy, or
(d) change the exception type/`reason_code` so the run loop mis-handles a denial.

## Assumption Audit

- ASSUMPTION: the method only ever mutates `self.approval_policy` (line 610 of
  the pre-extraction file) and otherwise reads collaborators. VERIFIED by reading
  the full body (553–701): the single write is `self.approval_policy =
  scoped_policy`; everything else is method calls on collaborators.
- ASSUMPTION: passing the `AgentRunner` instance as `runner` and rewriting every
  `self.X` to `runner.X` is semantically identical, including the reassignment
  (`runner.approval_policy = scoped_policy` mutates the same instance attribute)
  and the `runner._emit_summary(...)` callback. VERIFIED — Python attribute
  binding on the passed instance is the same object the caller holds.
- ASSUMPTION: no import cycle is introduced. VERIFIED — `_core` is imported only
  under `if TYPE_CHECKING:` in `_governed_execution`; `RunEventType` comes from
  the stdlib-only leaf `_events`; `scripts/check_circular_imports.py` reports a
  clean graph (it excludes TYPE_CHECKING blocks).

## Evidence Check

- The extracted function is a verbatim copy of the method body with `self`
  rewritten to `runner` (a mechanical move); signatures preserved. `_core.py`'s
  `_authorize_tool_call` is now a thin delegation with the same signature, so the
  single call site (the run loop) is untouched.
- Orphaned `DenialReasonCode` import removed from `_core.py` (now used only as a
  type annotation inside the moved function, imported there under TYPE_CHECKING).
- ruff (check + format) clean; mypy clean on both files (the TYPE_CHECKING
  `AgentRunner` import gives the type checker the full runner surface, including
  `_check_payload_digest_approval` and `_emit_summary`).

## Authority / Tool Boundary

- In scope: `teaagent/runner/_core.py` (method body -> delegation; one import
  removed), `teaagent/runner/_governed_execution.py` (new function + imports +
  docstring), `scripts/validate_runner_invariants.py` (G1 symbol set), tests, ADR.
- Out of scope: no change to `ApprovalPolicy`, `RunnerApprovalCoordinator`,
  `AutoModeManager`, `FilePolicy`, the event spine, or audit semantics — those are
  called exactly as before.

## Failure Modes

- Import cycle: mitigated as above (TYPE_CHECKING + leaf import; gate green).
- `approval_policy` desync: not applicable — the function mutates the runner
  instance attribute directly, identical to the inline write.
- Private-member access across modules (`runner._emit_summary`,
  `runner._check_payload_digest_approval`): intentional and type-checked; ruff's
  selected rule set (`E,F,W,I,B,SIM,T201`) does not include `SLF`, so this is not
  a lint regression.

## Worst-case Scenario

The approval gate silently approves a destructive call that should require human
approval. Bounded by: the full approval/governance/runner suites plus the G3
live differential test (which drives a denied tool through both surfaces and
asserts `assert_approval_invariant`); a regression fails CI before merge.

## Safe Dry-run Plan

Behavior-preserving pure move, verified offline by the runner, approval,
governance, auto-mode, and subagent suites plus the live differential test — no
production run, no external I/O, no credentials.

## Rollback Plan

`git revert` the commit. The change is one new function + one method-body
delegation + one removed import + a gate symbol; reverting restores the inline
method exactly. No data migration, no persisted-state change.

## Bounded Execution

Single commit; only the files listed above; no network; no destructive ops;
verified by the local suites and the runner-invariant gate before commit.

## Audit Log Plan

Audit emission is byte-identical: every `audit.record(...)` and approval-manager
record call moved verbatim into the shared function. No audit event added or
removed.

## Human Review Required

Yes — high-risk path (`teaagent/runner/_core.py`) and the approval boundary.
This report is the reflective-risk artifact; the `check-high-risk-paths`
pre-commit hook gates the commit on its presence.

## Human Approval Gate

Owner authorized completing G1 ("Everything you can") after the budget dimension
landed. This finishes the G1 shared-layer extraction.

## Acceptance Criteria

- `_governed_execution.authorize_tool_call` owns the approval pipeline;
  `AgentRunner._authorize_tool_call` delegates to it.
- All existing approval / governance / runner / auto-mode / subagent tests pass
  unchanged.
- `validate_runner_invariants.py` passes and now requires `_core.py` to call
  `authorize_tool_call` (alongside the budget `enforce_*` functions).
- ruff + mypy clean; the G3 differential test stays green.

## Go / No-go Decision

**GO** — bounded, behavior-preserving mechanical move (`self` -> `runner`), fully
verified, trivially reversible, with a static gate locking the delegation. With
this slice, G1's shared governed-execution layer covers both the budget and
authorization dimensions.
