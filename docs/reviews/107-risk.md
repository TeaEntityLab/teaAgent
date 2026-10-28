# Risk Report — PR 107: deny preset terminal over session and once grants

> **Claim class:** Risk note for one change. Not current truth.
> **Last reviewed:** 2026-10-28

**Date:** 2026-10-28
**Scope:** G-P1-10 (`docs/retrospective/06-action-register.md`), extends G-P1-4 and the owner decision of 2026-10-27 ("a matched deny preset is terminal; session approvals and once grants must not override it")
**High-risk path touched:** `teaagent/approval/manager.py` (matches `teaagent/approval/` in `scripts/high_risk_paths.yaml`). `teaagent/policy.py` and `teaagent/runner/_governed_execution.py` are assessed here too: they change no code, but they reach the changed ordering on every governed call.

## What changes

1. **Deny preset checked before session and once allows (G-P1-10).** In `ApprovalManager.assert_allowed` (`teaagent/approval/manager.py:974-1000`) the `check_preset` call and its `POLICY_DENIED` raise now run before `jit_state.is_tool_session_approved` and `jit_state.consume_once`. Before the change, both grants returned early and a matched deny preset was never reached: deny + `approve_session` and deny + `approve_once` (exact payload) both executed the tool.
2. **Once grant not consumed on denial.** Because `consume_once` now runs only after the deny check, a denied attempt leaves a once grant in place.
3. **No change to `ApprovalPolicy` or the governed runner.** `ApprovalPolicy.assert_allowed` (`teaagent/policy.py:106`) copies the session and once state into the manager and delegates, so the single reorder covers it. `_governed_execution.py:325-335` already re-raises `POLICY_DENIED` without offering it for approval, so it needed no change.
4. **Non-deny decisions are unchanged.** The `allow` preset, the backend decision, `check_scoped`, the payload-digest preapproval and the JIT prompt keep their order and their results. The only new call on the hot path is a read-only `ApprovalPresetStore.check` made before the session check; it has no writes and no audit side effects.

## Risk assessment

- **Blast radius.**
  - Only calls that match an explicit deny preset change outcome. They change from allowed to `POLICY_DENIED` in every permission mode where the grant applies.
  - A session approval or once grant can no longer override a deny preset. No other call changes outcome.
  - `JITApprovalManager.is_approved` (`teaagent/approval/manager.py`) returned True for a session-approved tool even under a deny preset. It has no callers in `teaagent/` (the `is_approved` hits under `teaagent/consensus/` are a different class). It is a query, not an allow path; it is made deny-aware in the `is_approved` section below.
- **Failure modes.**
  - A user who relied on a session approval to override a deny preset is now blocked. The escape hatch is `teaagent approval revoke <deny_grant_id>`; the falsifier test pins it.
  - A once grant is now left in place when a call is denied, so it stays available for a later call with the same payload. That is the intended "not consumed on denial" behaviour, but the grant's lifetime is now longer than before for denied attempts. It is still bound to the exact call id and payload digest.
  - Preset checks now run on every destructive call, including calls that were previously allowed by a session grant. Cost is one read of the preset store per call, the same read the non-session path already performed.
- **Thin harness.** `teaagent/approval/manager.py` changes by 13 insertions and 8 deletions, moving one existing block up. No new framework, event type, grant scope or dependency. Exemption count for `scripts/check_god_modules.py` stays at 18.
- **Not changed.**
  - Permission-mode denials (`READ_ONLY_MODE`, `WORKSPACE_WRITE_MODE`, `PLAN_CONTRACT_DENIED`, `FULL_ACCESS_NOT_ACKNOWLEDGED`) still run before every grant, as before.
  - Workspace-path and protected-skill-path checks still run before the grant checks, as before.
  - `is_approved` is now deny-aware; see the `is_approved` section below.

## `is_approved` (owner decision 2026-10-28)

`JITApprovalManager.is_approved` (`teaagent/approval/manager.py`, the method the owner called `ApprovalManager.is_approved`) is now deny-aware. It takes an optional `arguments` and checks a matched deny preset before any session or once logic, so it returns False for a session-approved or once-granted call that a deny preset blocks. It never consumes a once grant. With `arguments=None` the payload is unknown, so path- and command-scoped denies cannot be evaluated; the check fails closed and treats any deny grant recorded for the tool as a match. `ApprovalManager` passes its approval store and permission mode into the manager, so the peek agrees with `assert_allowed`. `assert_allowed` itself is unchanged. Tests: `tests/test_deny_preset_terminal_over_grants.py`, four `is_approved` cases (deny + session False, deny + once False with the grant unconsumed, no-deny control True, path-scoped deny).

## Dry run and rollback

- **Dry run (before the fix).** `tests/test_deny_preset_terminal_over_grants.py` run against `origin/main`: 6 of 8 tests failed. Deny + session and deny + once returned without raising, and the recording handler ran the tool. The probe scripts reproduced the same results: deny + approve_session ALLOWED, deny + approve_once ALLOWED, policy path with a session approval ALLOWED.
- **Dry run (after the fix).** All 8 tests pass. Both probes report `POLICY_DENIED` for every deny case. The approval/deny/policy/governed/permission subset and the other gates in the commit message's `Tested:` trailer were run on the fixed tree.
- **Rollback.** One commit (`fix(approval): make a deny preset terminal over session and once grants`) reverts cleanly. Reverting restores the earlier order: session and once grants override a deny preset again. No data migration, no stored-state format change, no change to grant files on disk.

## Tests

- `tests/test_deny_preset_terminal_over_grants.py` (adversarial, 8 tests):
  - deny + `approve_session` raises `POLICY_DENIED` at the manager;
  - deny + `approve_once` with the exact payload raises `POLICY_DENIED`, and the once grant is still present afterwards;
  - the `ApprovalPolicy` path with a session approval in `jit_state` raises `POLICY_DENIED`;
  - the runner path (`AgentRunner.run`) with a session grant or a once grant under a deny preset never calls the handler and records `policy_denied`;
  - control: with no deny preset, session and once grants still allow, and the once grant is consumed on use;
  - falsifier: revoking the deny grant restores the session allow on the real runner path.
- Existing `tests/test_deny_preset_runtime_enforcement.py` (G-P1-4) continues to pass.

## Decision

Proceed to human review. The change aligns code with the owner decision of 2026-10-27 and does not change any non-deny decision. **Human review gate: OPEN.** The owner should confirm that (a) a session or once grant must never override a deny preset, and (b) the fail-closed tool-level deny check in `is_approved` (used when no arguments are passed) is acceptable.
