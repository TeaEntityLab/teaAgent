# Risk Report — PR 98: terminal deny presets, batch cancel token, cockpit and heartbeat fields

> **Claim class:** Risk note for one PR. Not current truth.
> **Last reviewed:** 2026-10-27

**Date:** 2026-10-27
**Scope:** G-P1-4, G-P1-5, U-P1-7, U-P1-8 (`docs/retrospective/06-action-register.md`)
**High-risk path touched:** `teaagent/runner/_core.py` (per `scripts/high_risk_paths.yaml`). The approval change in `teaagent/runner/_governed_execution.py` is not on that list but changes approval behavior, so it is assessed here too.

## What changes

1. **Deny presets are terminal in `prompt` mode (G-P1-4).** `authorize_tool_call` caught every `ToolPermissionError` and, for a destructive tool in `prompt` mode, offered it to the interactive approval handler. A matched deny preset (`POLICY_DENIED`, `teaagent/approval/manager.py:987`) therefore ran when a person approved. It now goes to `record_blocked` and re-raises before the handler. Every other reason code keeps its current path.
2. **Subagent batches cancel their children at the deadline (G-P1-5).** Each batch creates a `threading.Event`, passes it to its children as `cancel_token`, and sets it at the deadline and on every exit. A set parent token is copied to the batch token while the batch waits. `AgentRunner` already checked the token at the top of each iteration; it now also checks it right before dispatching a tool decision (3 lines in `_core.py`).
3. **Cockpit run context (U-P1-7).** `ControlCockpitState` gains branch, undo availability, last run id and active rules; the TUI renders them.
4. **Heartbeat progress (U-P1-8).** Heartbeat ticks can carry tool, in-flight flag, elapsed seconds, cost and last checkpoint from an allow-listed provider.

## Risk assessment

- **Blast radius.**
  - (1) Only calls that match an explicit deny grant change outcome, and only in `prompt` mode with a destructive tool and an approval handler. Allow, workspace-write, read-only and handler-less prompt runs already blocked.
  - (2) Only `register_subagent_tools` batches pass the new token; swarm, tournament and team callers still inherit the parent token unchanged.
  - (3) and (4) Additive read-only observability.
- **Failure modes.**
  - (1) A user who relied on approving a denied call at the prompt is now blocked. That behavior contradicted `docs/cli.md:923`, `docs/permission-and-approval-playbook.md:63-64` and the owner decision in `docs/reviews/dogfood-g1-g22-2026-09-15-risk.md:22`. The escape hatch is `teaagent approval revoke <grant_id>`, pinned by a falsifier test.
  - (2) A child stops at its next check, so a tool call already dispatched may still finish; the guarantee is "no new tool call after the deadline", not "no side effect after the deadline". A cancelled child records the existing `run_failed` (`system`, "run cancelled by cancel token"). The batch wait loop now wakes every 50 ms to poll the parent token.
  - (3) Each source is wrapped: a failure logs, records an error string and shows `unknown`, never a silent pass (A-P0-2).
  - (4) A raising provider sets `progress_unavailable` and the tick still records; the provider cannot overwrite `tick` or `interval_seconds`.
- **Thin harness.** `runner/_core.py` grows from 1,062 to 1,065 lines; god-module exemptions stay at 18. No new framework, event type or dependency: the cancel path reuses `cancel_token` and `RunCancelledError`.
- **Not changed.** `JIT_NO_APPROVAL`, `MULTISIG_NO_QUORUM` and the protected-path codes (`WORKSPACE_WRITE_MODE`, `SYMLINK_BLOCKED`, `SKILL_WRITE_BLOCKED`) still reach the approval prompt for destructive tools in `prompt` mode. No owner decision on record covers them; flagged in the PR for the owner.

## Dry run and rollback

- **Dry run.** Full suite on the PR head with the locked toolchain: 6830 passed, 34 skipped, 0 failed. All `lint` and `governance-gate` CI steps were run locally and exit 0. Each behavior change has a test that failed on the base: the approving handler ran the denied tool, and 4 tool calls landed after the batch deadline.
- **Rollback.** Each change is one commit and reverts independently: `801223dd` (deny), `98fa5e59` (cancel token), `57d84d70` (cockpit), `232df373` (heartbeat). Reverting `801223dd` restores prompt-mode override; reverting `98fa5e59` restores the previous behavior where abandoned children keep running. No data migration and no stored-state format change.

## Tests

- `tests/test_deny_preset_runtime_enforcement.py`:
  - the approving handler is never called and the tool never runs;
  - `tool_call_blocked` records `policy_denied`;
  - `approval why-denied` describes it;
  - revoking the grant lets the same handler run the tool.
- `tests/test_subagent_batch_cancel_token.py`:
  - at most one already-dispatched tool call after the batch returns;
  - a parent cancel mid-batch stops the children.
- `tests/test_control_cockpit.py` and `tests/acceptance/test_cockpit_snapshot_flow.py`: the four fields, plus the no-git, no-run and failure cases.
- `tests/test_heartbeat_progress_fields.py`: payload fields, backward compatibility without a provider, and one real run.

## Decision

Proceed. Change (1) aligns code with an owner decision already on record rather than making a new one. Change (2) makes the batch's "timed out" result true by reusing an existing primitive. Changes (3) and (4) are inside the DR-006 M4 cockpit and background-lifecycle carve-out. Human review: the PR is not merged without the owner's review; the protected-path question stays with the owner.
