# Control-Loop Ownership Map - 2026-06-11

## Purpose

This map records how TeaAgent's runner responsibilities are currently split
across control loops, which module owns each decision, and which boundaries are
stable enough to extract first.

The goal is not to redesign the runner in one move. The goal is to keep the
thin-harness boundary legible while extracting only the smallest verified seams.

## Current Runner Boundary

Current execution path:

`ModelDecisionEngine -> AgentRunner -> ToolRegistry -> ApprovalPolicy -> workspace tools -> AuditLogger / RunStore`

`AgentRunner` remains the orchestration surface for:

- run state initialization
- iteration progression
- budget accounting
- decision dispatch
- tool execution
- error-to-result translation
- summary emission

Everything else below should be treated as a control-loop owned boundary, not a
runner-local policy decision unless explicitly noted.

## Ownership Map

| Control loop | Current owner | Input | Output | Failure semantics | Stable boundary? | Keep in `AgentRunner`? |
| --- | --- | --- | --- | --- | --- | --- |
| Approval gate | `teaagent/runner/_approval_manager.py` + `teaagent/policy.py` | tool name, arguments, annotations, JIT state, checkpoint state, run context | approval request, approval audit events, allow/deny/pause decision | denied or missing approval becomes `pending_approval` or `ToolPermissionError` depending on handler path | yes | orchestration only |
| Budget gate | `teaagent/budget.py`, `teaagent/budget_monitor.py`, `teaagent/runner/_core.py` | cost, token usage, iteration count, tool-call count, phase budget | warning, prompt, read-only suggestion, or hard stop | exceeds iteration/tool/cost cap -> `BudgetExceededError` / run failure | partially | yes, but only as a thin enforcement wrapper |
| Plan/spec gate | `teaagent/runner/_plan_validator.py`, `teaagent/governance/plan_gate.py` | tool name, context, plan contract, tool args, permission mode | drift message or allow decision | missing or out-of-scope plan -> `ToolPermissionError` | yes | only dispatch the evaluation |
| Tool governance gate | `teaagent/tools.py`, `teaagent/file_policy.py`, `teaagent/governance/tool_lint.py` | tool schema, annotations, file path, write intent | schema validation, file-policy allow/deny, lint allow/deny | invalid decision or policy violation -> blocked tool call | yes | orchestration only |
| Audit / evidence recorder | `teaagent/audit.py`, `teaagent/run_evidence.py`, `teaagent/run_receipt.py` | run events, tool events, approvals, model route data, undo signals | audit log, evidence bundle, human receipt | missing evidence should surface as incomplete receipt, not silently pass | yes | emit events only |
| Context compaction gate | `teaagent/context.py`, `teaagent/runner/_core.py` | observation count, token estimate, compactor config | compacted context, pinned memory, compaction audit event | compaction failure should not mutate run state silently | moderate | yes, but keep the policy out of the runner body |
| Plugin loading boundary | `teaagent/plugin_system.py` | workspace root | loaded tools / plugin warnings | load failure is non-fatal unless policy says otherwise | yes | initialize once, then stop touching it |
| Final result validation | `teaagent/proof_of_use.py`, `teaagent/evidence_summary.py`, `teaagent/run_evidence.py` | final answer, audit trail, run events | final run result, proof-of-use metadata, evidence summary | missing proof or incomplete evidence should be reported in metadata / receipt | moderate | yes, but only as a terminal adapter |

## Input / Output Semantics

### Approval Gate

- Input: tool identity, arguments, annotations, approval policy, and any JIT or preset approval state.
- Output: an allow/deny result plus audit evidence.
- Failure: denial should remain actionable and auditable, with the reason surfaced to the caller.

### Budget Gate

- Input: measured or reported usage plus configured caps.
- Output: warnings, prompts, or a hard stop.
- Failure: cost/iteration/tool-call overflow must terminate the run cleanly and record the reason.

### Plan / Spec Gate

- Input: tool request, run context, and bound plan contract.
- Output: either `None` or a drift/error message.
- Failure: a blocked write must explain the scope mismatch and name the plan artifact or the missing binding.

### Audit / Evidence Recorder

- Input: every material run event.
- Output: JSONL audit, run summary, receipts, and evidence bundle material.
- Failure: incomplete evidence should be detectable later, not hidden by a prettified receipt.

## Stable Extraction Candidates

The first narrow extraction should be the plan/spec gate wrapper.

Why this one first:

- it is already a pure decision boundary
- it has a clear allow/block contract
- it is exercised by focused tests
- it can be extracted without changing run lifecycle ordering

Recommended shape:

- add one `PlanValidator` wrapper that evaluates write gating in a single call
- keep policy semantics unchanged
- keep `AgentRunner` responsible for dispatch order only

Second-tier candidates, in order:

1. Receipt completeness builder.
2. Budget decision adapter.
3. Approval decision recorder.

## Keep In Runner For Now

These should remain in `AgentRunner` until the boundary pressure is clearer:

- run loop control
- iteration counting
- cancellation checks
- final result shaping
- summary emission
- phase-tracker bookkeeping

Those behaviors are close to the execution loop and do not yet benefit from a
separate boundary without risking a broad refactor.

## Verification Notes

The plan/spec gate wrapper is the first extraction candidate because the current
tests already prove the underlying semantics. The new wrapper should be
behaviour-preserving and covered by a focused unit test that exercises:

- allow path
- plan drift block
- read-only lint block if applicable

If that wrapper becomes noisy, stop there and keep the rest of the runner intact.
