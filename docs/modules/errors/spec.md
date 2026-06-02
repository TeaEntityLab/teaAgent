# errors — Behavior Specification

## Purpose

`errors` defines the canonical harness exception taxonomy and denial reason codes used by runtime control flow, CLI rendering, and audit classification.

## Error Categories

`ErrorCategory` classifies failures into `transient`, `model_logic`, `permission`, and `system` classes for consistent reporting and run-failure labeling.

## Exception Hierarchy

- `AgentHarnessError` (base): message + optional remediation `hint`; `__str__` appends hint when present.
- `BudgetExceededError` (`MODEL_LOGIC`): iteration/tool-call/cost envelope exhausted.
- `ToolValidationError` (`MODEL_LOGIC`): malformed model decision payload.
- `ToolPermissionError` (`PERMISSION`): policy/approval/plan-gate denial with optional `reason_code`.
- `ToolExecutionError` (`SYSTEM`): local tool runtime failure.
- `RunCancelledError` (`SYSTEM`): cancellation token triggered.

## Behavior Contract

1. Harness-raised domain errors should inherit `AgentHarnessError`.
2. Subclasses must set stable `category` values for downstream categorization.
3. Remediation guidance should be carried in `hint` instead of implicit message-only wording.
4. Permission denials should attach `DenialReasonCode` when a specific gate is known.
5. String formatting is deterministic: message first, hint second line when present.

## Invariants

- `AgentHarnessError.__str__` never drops the primary message.
- Exception construction performs no I/O or state mutation.
- `DenialReasonCode` values remain lowercase stable tokens for audit/search indexing.
