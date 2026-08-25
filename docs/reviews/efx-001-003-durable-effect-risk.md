# EFX-001–003 Durable-Effect Governance Risk Review

**Date:** 2026-08-25
**Action:** G-P0-2 follow-through (implementation)
**High-risk paths:** `teaagent/approval/`, `teaagent/runner/_core.py`

## Goal

Close three owner-promoted DR-006 governance gaps on existing seams:

- EFX-002: classify built-in external mutations and fail closed in
  prompt / read-only / workspace-write.
- EFX-003: bind and consume one-time JIT approvals to canonical payload.
- EFX-001: persist an unmatched mutating start as `OUTCOME_UNKNOWN` and
  refuse blind redispatch.

## Stakeholders

Owner-operator, harness maintainers, security reviewers, any run that
can invoke GitHub, browser, MCP, or other mutating tools.

## Assets at Risk

- Approval allow/deny decisions and JIT one-time grants.
- External systems reachable from built-in GitHub/browser/MCP tools.
- Checkpoint/resume integrity (duplicate mutations vs stuck runs).
- Operator trust that prompt mode is not a silent bypass.

## Threat Model

1. A tool labeled non-destructive mutates a remote system under PromptBackend
   auto-approval.
2. Remote MCP `readOnlyHint` falsely relaxes local policy.
3. A one-time approval is reused for a different payload or a second dispatch.
4. A crash after `tool_call_started` and during handler execution is treated
   as failure or success, authorizing a duplicate non-idempotent mutation.
5. Resume auto-approval re-grants an unmatched mutating start.

## Assumption Audit

- Prompt / read-only / workspace-write are expected to gate external mutation.
  Supported by AGENTS.md tool governance; annotation design is additive.
- Process-death of a local handler is a valid proxy for the unmatched-start
  window. It does not prove live provider frequency.
- Scoped local fixes can close the proved gaps. A fresh call_id for the same
  intent is addressed by payload-digest identity, not call_id uniqueness alone.

## Evidence Check

Coordinator probes from
`docs/analysis/durable-effect-roadmap-socratic-review-2026-08-25.md`:
P1 unmatched start + duplicate retry; P2 reusable `approve_once` and shared
omitted IDs; P3 PromptBackend/AgentRunner path for `github_create_pr`.
No live GitHub/browser/provider mutation was executed.

## Authority / Tool Boundary

User authorized implementation in this conversation. Documentation is not
authorization for deploy, push, or live external effects. Workers must not
call live GitHub, browser, or paid providers.

## Effect Recovery Decision

Unmatched non-idempotent dispatch is `OUTCOME_UNKNOWN` with `retry_safe: false`.
Idempotent tools may retry the same digest. Exactly-once external effects remain
a non-goal. ADR-0042 reversal boundary is unchanged.

## Failure Modes

- Over-classification: true read-only MCP tools now require JIT in prompt mode
  (fail closed; allow/danger-full-access still exist).
- Under-classification: a built-in mutator missed in the inventory.
- Legacy `approve_once(call_id)` without digest still one-time but not
  payload-bound until the prompt path supplies arguments.
- Checkpoint schema consumers that copy only known keys: `pending_effect`
  added to `_CHECKPOINT_KEYS`.

## Worst-case Scenario

A remaining misclassified mutator or unconsumed grant ships and performs an
unauthorized or duplicate external mutation (PR, review, browser click).

## Safe Dry-run Plan

Providerless unit/integration tests only. Mock GitHub HTTP. No `GITHUB_TOKEN`
network. Process-death test uses a local temp-file mutation and `os._exit`.

## Rollback Plan

`git revert` of the implementation commit. Annotation and JIT changes are
behavior-tightening; rollback restores previous auto-approval and reusable
grants. Checkpoint `pending_effect` is additive and ignored by older readers.

## Bounded Execution

Local repository only. Isolated worker worktrees. No production, no push,
no live effects.

## Audit Log Plan

Keep existing `tool_call_started` / completion / failure events. Unmatched
resume surfaces `OUTCOME_UNKNOWN` in observations. Do not claim settlement
from start-only audit.

## Human Review Required

Yes — approval and dispatch semantics. Implementation was owner-requested;
deploy/push is not authorized.

## Human Approval Gate

Owner requested implement. Live GitHub/browser/provider use remains
unauthorized.

## Acceptance Criteria

Named tests for EFX-001/002/003 pass. Prompt/read-only/workspace-write fail
closed for inventoried external mutators. One-time grants bind digest and
consume. Unmatched non-idempotent starts are UNKNOWN and not redispatched.

## Go / No-go Decision

**GO** for bounded local implementation and tests.
**NO-GO** for production deploy, live effects, or generic durable-execution
infrastructure.
