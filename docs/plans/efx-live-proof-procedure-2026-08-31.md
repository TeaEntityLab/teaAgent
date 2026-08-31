# EFX-001–003 Live-Provider Proof Procedure — 2026-08-31

> **Claim class:** Preparation scaffold for owner-authorized live proof only.
> **Status:** Draft, not an execution. No live call may run without the
> owner recording the six Definition of Ready items from
> `current-roadmap-execution-plan-2026-08-26.md §5` in-session.
> **Authority:** `harness-first-direction`, `DR-006`, `roadmap-status.md`,
> `backlog-priority.md`, `ADR-0042`, and the execution plan §5–5.4.

## 1. Why this exists (12 days to 2026-09-12)

ADR-0031 and EFX share the same clock. Criterion 1 remains `0 observed`
because shadow mode is unexercised in production audit logs. The new
`scripts/exercise_h4_shadow_demo.py` proves the 30-day window analysis
*is exercisable* — run it against a scratch audit log to see 2 denial
candidates. For EFX, providerless acceptance is green
(`tests/acceptance/test_efx_durable_effect_flow.py` 4 passed, sharded full
suite `6680 passed` at `b017c81`), but live GitHub/browser proof is still
required to move `In Progress → Complete`. This procedure is the
checklist the owner can authorize in one session to close EFX-002→003→001
in order.

## 2. Definition of Ready (owner records all six before any live call)

Copy this table into the session; leave Phase 1 blocked if any row is blank:

| # | Item | Owner value (example) |
|---|------|-----------------------|
| 1 | Throwaway target | `TeaEntityLab/teaagent-efx-throwaway-20260831` (private fork, deletable) + `about:blank` browser data URL |
| 2 | Credential & scope | `GITHUB_TOKEN` with `repo` on throwaway only, or `GH_TOKEN` with `public_repo`; least privilege, short-lived PAT |
| 3 | Allowed tools & payloads & budget | `github_create_pr` with exact `{"title":"EFX-002 probe 2026-08-31","head":"efx-002-20260831","base":"main"}` + `browser_navigate` with `{"url":"data:text/html,<h1>efx</h1>"}`; `max 3 calls` |
| 4 | Expected external effect & pre-state | No PR # exists before; browser has no prior navigation to that data URL |
| 5 | Reconciler & reversal | Owner will inspect GitHub PR list + browser history; `gh pr close --delete-branch` or manual delete if `OUTCOME_UNKNOWN` |
| 6 | Interruption auth (EFX-001 only) | Owner authorizes child termination after provider mutation but before runner persists completion (copy pattern from `tests/test_efx001_interrupted_dispatch.py`) |

Also record:
- `TEAAGENT_H4_*` stays `shadow` (no mode flip in this lane).
- Permission mode stays `prompt` (or `read-only`/`workspace-write`); never `allow`/`danger-full-access`.
- MCP `readOnlyHint`/`destructiveHint` are not authoritative.

## 3. Execution order (do not reorder)

```
Owner auth → EFX-002 → EFX-003 → EFX-001 → sanitized work-log → status flip
```

### 3.1 EFX-002 — classification & escalation (fail-closed)

1. `teaagent agent run --permission-mode prompt "create a PR with title EFX-002 probe 2026-08-31"` against throwaway.
2. Before approval: assert run returns `pending_approval`, `tool_call_pending_approval` in audit, and GitHub shows no new PR.
3. Confirm pending record names locally classified `external_effect` tool even if remote metadata says read-only.
4. `teaagent agent resume <provider> <run_id> --approve-scoped github_create_pr:<payload_sha256>` and continue via governed path.
5. Capture: run ID, tool, payload digest, approval/audit event IDs, before/after PR URL, handler-not-called-before-approval proof.

### 3.2 EFX-003 — exact one-time binding

1. Reuse the same pending call; do not mint wildcard.
2. Prove one successful external effect.
3. Replay same payload with same grant → must deny, no second PR.
4. Replay changed arguments with same grant → must deny.
5. Capture: one success + two denials, consumed-grant event, provider state shows no duplicate.

### 3.3 EFX-001 — interrupted dispatch & reconciliation

Only after 002+003 pass, against a *reversible* throwaway effect (e.g., `browser_navigate` to data URL or second throwaway PR).

1. Record remote pre-state + exact non-idempotent payload.
2. Dispatch via `AgentRunner`; temporary handler terminates child after provider mutation is observable but before `run_completed` persists (copy `tests/test_efx001_interrupted_dispatch.py` spawned-run/process-exit pattern; do not add production fault-injection API).
3. `teaagent agent resume` must surface `OUTCOME_UNKNOWN`, `retry_safe=false`, and refuse blind redispatch of same digest.
4. Inspect provider independently; record whether effect happened.
5. Reconcile explicitly; do not label unknown as settled.

## 4. Closure and status transition (one commit, per §5.4)

Create a sanitized dated work-log under `docs/work-log/efx-live-proof-2026-08-31.md` (no tokens, no raw audit logs) containing: target class, run IDs, event IDs, redacted digests, remote receipts/URLs, call budget, reconciliation outcome, operator, residual risks. Then in one status-reconciliation change:

- `roadmap-status.md` EFX-001..003 `In Progress → Complete` only if each exit contract passed;
- `backlog-priority.md` same;
- `daily-driver-current-status.md` warning reflects exact live-proof scope;
- `acceptance.md` updated only with reproducible test evidence, not manual counts;
- Run `tests/test_efx*`, `tests/acceptance/test_efx_durable_effect_flow.py`, `tests/acceptance/test_docs_acceptance_count_accuracy.py`, `scripts/validate_docs_consistency.py`, `./scripts/verify_docs.sh`.

## 5. How to run the dry-run today (no credentials, no external mutation)

```bash
# H4 shadow demo (scratch, proves criterion-1 exercisable)
python3 scripts/exercise_h4_shadow_demo.py --output /tmp/h4_demo.jsonl
python3 scripts/prepare_h4_evidence.py --audit-log /tmp/h4_demo.jsonl --since 2026-08-13 --until 2026-09-11

# EFX providerless (already green, no live provider)
python3 -m pytest tests/test_efx002_effect_classification.py tests/test_efx003_one_time_approval.py tests/test_efx001_interrupted_dispatch.py -q
python3 -m pytest tests/acceptance/test_efx_durable_effect_flow.py -q
```

## 6. Non-goals (explicitly not in this lane)

No exactly-once claim, generic effect ledger/outbox, distributed fencing/leases, actor supervision, second runner, cloud/SaaS, or public adoption work. See `held-roadmap-forward-spec-index §3.2`.

## 7. Residual risks for owner sign-off

- Live proof still needs owner credential handling; ambient `GITHUB_TOKEN` warning remains per `daily-driver-current-status.md`.
- Provider settlement is per-provider; broad claim from one target is not implied.
- `h4_governance_shadow` receipts are the only ADR-0031 C1 source; 0 observed is honest unexercised, not a pass.
