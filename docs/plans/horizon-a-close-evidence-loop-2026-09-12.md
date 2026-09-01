# Horizon A — Close Evidence Loop (2026-09-12 → ~2026-10-15)

> **Claim class:** Bounded execution plan for trigger-only work, not a scheduling authority.
> **Authority:** `roadmap-status.md`, `backlog-priority.md`, `current-roadmap-execution-plan-2026-08-26.md` §6.3, `DR-006`, `harness-first-direction`.
> **Status:** Draft, awaiting 2026-09-12 gate. No live call without owner Definition of Ready.
> **Last updated:** 2026-09-01 (re-affirmed: queue empty, 6681 green, no new friction, no dogfood scheduled).

Execution of this horizon requires the 2026-09-12 owner decision. Until then it is a plan only.

## 1. Entry gate

All three tasks are `Hold` until 2026-09-12. After the gate, pick exactly one ADR-0031 disposition per §6.2/6.3 and execute only the tasks whose trigger is met.

## 2. Tasks

### A1 — EFX live proof (only code-bearing item, blocked solely on owner auth)

Use `docs/plans/efx-live-proof-procedure-2026-08-31.md`.

**Trigger:** Owner records six Definition-of-Ready rows (throwaway target, credential scope, exact `github_create_pr`/`browser_navigate` payloads, `max 3 calls`, pre-state, reconciler) in-session.

**Steps:** Run 002→003→001 in order via `AgentRunner` in `prompt` (never `allow`), `resume --approve-scoped`, record `OUTCOME_UNKNOWN`/`retry_safe=false` refusal for 001, inspect provider, reconcile explicitly.

**Exit evidence:** Dated work-log `docs/work-log/efx-live-proof-2026-*.md` (sanitized: target class, run IDs, digests, receipts, budget, reconciliation, operator, residual risks) + `roadmap-status.md` EFX rows `In Progress → Complete` only if each exit contract passed + focused suite `tests/test_efx*` + `tests/acceptance/test_efx_durable_effect_flow.py` + `verify_docs.sh` green.

**Non-goals:** No exactly-once, ledger/outbox, fencing, actor, second runner.

### A2 — Execute ADR-0031 disposition

**Trigger:** Owner decision on 2026-09-12 per execution plan §6.2.

- **Promote:** Only if `C1` shows >0 organic `h4_governance_shadow` events, `C2/C3/C5` green, and owner sign-off. Requires high-risk plan to flip `policy_governance_mode` from advisory to enforce (rename `evaluate_approval_policy_shadow`, add deny branch, RBAC already enforces) + `doctor config` visibility + `h4_mode_changed` audit.
- **Extend:** Only if bound to a scheduled dogfood session that will generate organic events; name missing criteria, new expiry, evidence to collect. Never silent roll-forward.
- **Revert (default):** If no dogfood scheduled by 09-12 or extended window again 0 organic, revert shadow wiring, preserve evidence/history, keep suite `6681` green. Thin-harness invariant requires this. Falsifier: if owner won’t schedule dogfood *and* won’t revert, declare H-series maintenance-mode explicitly per advisor §6.3.

**Exit evidence:** Dated ADR-0031 decision log + either promotion commit with enforce tests or revert commit with rollback proof.

### A3 — DR-006 falsifier review (~2026-09-22, 3 months from 2026-06-22)

**Trigger:** Calendar gate, no code.

**Steps:** Owner walks four falsifiers (friction log stays 0 but feature ships without override; release off-main without `--check`; new UX tickets cite `competitive-positioning-plan` without friction ID; quarterly survey skipped while README makes fresh comparison claims). All currently look clear — record that explicitly. Also schedule quarterly competitive survey (T5, due end-September) as docs-only hypothesis intake.

**Exit evidence:** Dated owner note in `docs/work-log/operator-friction-log.md` or `dr-006-owner-decision` addendum.

## 3. Sequencing

```
2026-09-12 owner decision
  ├─ EFX auth? ──→ A1
  ├─ ADR-0031 disposition ──→ A2
  └─ 09-22 falsifier ──→ A3
```

A1 and A2 are independent except both need owner time; A2's revert is not blocked by A1's outcome.

## 4. Verification after horizon

`verify_docs.sh` PASS, `validate_docs_consistency.py` PASS, sharded `6681/26` still green, no `allow`/`danger-full-access` proof, no generic effect subsystem added.

## 5. Related

- `current-roadmap-execution-plan §6.1.3` — H4 demo `2 synthetic` guarded, not C1
- `held-roadmap-forward-spec-index §8` — dated decision queue
- `analysis/suite-truncation-root-cause-2026-06-10.md`
