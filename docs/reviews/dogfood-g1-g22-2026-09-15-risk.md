# Risk Report — Dogfood Gap Fixes G1–G22 (2026-09-15)

> Satisfies review-system.md §4.2 for changes to approval / policy / audit /
> sandbox / runner gates. Owner adjudicated every item before implementation;
> decisions recorded in `docs/work-log/dogfood-findings-2026-09-15.md`
> §"Owner decisions (2026-09-15)".

## Scope

Approval/policy (`teaagent/approval/manager.py`, `selectors.py`,
`ergonomics/_approval_grants.py`, `runner/_approval_manager.py`,
`_governed_execution.py`), audit/run-store (`run_store.py`, `run.py`,
`resume.py`), sandbox (`sandbox/_git_branch.py`), background lifecycle
(`ergonomics/background_run.py`), RBAC (`governance/rbac.py`,
`subagents/_manager.py`), control-plane (`control_plane_api.py`), CLI
handlers, and dead-code deletion (`tui/cockpit_*.py`).

## Risk assessment per change

| Change | Risk | Mitigation |
|---|---|---|
| G1 deny grants block in all modes | **Behavior change**: previously a matched deny fell through to prompt/execute; now it hard-blocks. Could deny calls that used to run. | Owner chose "block in all modes" — the documented intent. `DenialReasonCode.POLICY_DENIED` is explicit; `check`/`explain` already reported `deny`. |
| G6 strict preset wildcard scope | Strict preset now applies denies it previously skipped. | Owner chose fix; `preset strict` was a documented no-op bug. |
| G9 shadow on all modes | More `h4_governance_shadow` events (allow/workspace-write/read-only now emit). | Deduped by `call_id`; shadow is observability-only, no enforcement change. |
| G5/G21 unbounded pending-approval query | `limit=None` scans all runs — could be slow on large stores. | Bounded by run count; correctness (no missed pending) outweighs. `list_runs` widened to `int \| None`. |
| G15 `approval reject` + resume | Denying a queued call then resuming could re-execute or strand the run. | Records `tool_call_denied` (clears pending) then resumes; verified the denied call is not re-executed. `deny` reverted to grant-only. |
| G16 24h auto-deny expiry | A paused run older than TTL is auto-denied — could deny a call the owner meant to approve. | Configurable via `TEAAGENT_PENDING_APPROVAL_TTL_SECONDS`; matches subagent-queue timeout pattern; owner chose auto-deny. |
| G2/G3 sandbox rollback guard + branch restore | `rollback()` now refuses when HEAD isn't on the sandbox branch — could refuse a legitimate undo. | Prevents the data-loss path (reset --hard on main); refusal is the safe failure. |
| G22 audit promotion ordering | Reordering promotion after sandbox resolution changes event timing. | Events land in the real run `.jsonl` instead of orphaned temp — strictly more complete audit. |
| G4 orphan marker | `exit_code` no longer defaults to 0 on lost exit — downstream readers may see `None`. | `orphaned` flag is additive; clean exits still backfill 0. |
| G7/G8 default role + operator_id | Seeding a default operator role changes empty-store deny-all to allow. | Owner chose minimal `start_workflow` only; shadow-mode still records, enforce path now reachable. |
| G17 delete TUI cockpit | Removes ~1100 LOC dead code + tests. | Owner chose delete; nothing instantiated the screens (verified dead). |
| G18 dead-code gate wired | New pre-commit hook; vulture findings now block. | Pre-existing findings fixed/whitelisted; gate passes clean. |

## Reversibility

All changes are in-repo code; rollback is `git revert`. No external state,
no data migration, no irreversible operation. The riskiest change (G1 deny
enforcement) makes a documented control real — the prior behavior was the
bug.

## Verification

- Focused pytest: 122 passed across touched areas.
- Per-gap smoke scripts: deny blocks in allow+prompt; strict preset applies;
  shadow emits in allow mode; reject denies+resumes; pending surfaces agree;
  orphan marker on SIGKILL; undo refuses off-branch; audit events land in run
  log.
- `check_dead_code.py` clean; ruff/mypy clean on changed files.

## Human Review

Owner adjudicated all items (2026-09-15). D1 deferred; ADR-0031 extended to
2026-09-29 conditioned on G1–G5 landing and re-dogfood. EFX live proof stays
blocked on owner credentials.
