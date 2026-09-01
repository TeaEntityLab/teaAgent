# Horizon B — Generate Evidence via Dogfood (2026-09-12 → ~2026-11-15)

> **Claim class:** Bounded execution plan for trigger-only work, not a scheduling authority.
> **Authority:** `roadmap-status.md`, `backlog-priority.md`, `current-roadmap-execution-plan-2026-08-26.md` §6.3, `DR-006`, `harness-first-direction`, advisor `2026-08-31` hypothesis.
> **Status:** Draft, awaiting 2026-09-12 gate. No code without dated dogfood schedule.
> **Last updated:** 2026-09-01 (parallel to Horizon A; runs only if dogfood scheduled, else Horizon C prune).

This horizon is the *only* DR-006 lane that can generate organic evidence for everything downstream (H4 C1 shadow events, new friction entries, BG-001/cockpit). It is the fuel for Horizons A and C. If no dogfood is scheduled by 09-12, this horizon is intentionally empty and Horizon C's prune default applies.

## 1. Entry gate

`Hold` until owner records a dated dogfood session in `docs/work-log/operator-friction-log.md` or a dated note (owner-override per DR-006) naming the M4 carve-out scope. Cloud/gateway/multi-tenant remain held per DR-006 T4 — this horizon is background lifecycle + cockpit only.

## 2. Tasks

### B1 — Dated dogfood session (owner-override, co-maintainer dogfood)

**Trigger:** Owner schedules session; no agent may fabricate.

**Steps:**

- Owner runs ≥1 day of real coding through the harness (TUI `tui --setup --root .`, `agent run` with subagents, background `attach`, cockpit inspection).
- Agents do not simulate testimony; every event must be owner-observed.
- Use `scripts/exercise_h4_shadow_demo.py` only as a local spike — organic `h4_governance_shadow` events from real policy/RBAC denials are the real evidence.

**Exit evidence:** Dated work-log `docs/work-log/m4-dogfood-2026-*.md` with session date, commands run, failures seen, organic `h4_governance_shadow` count, new friction entries or explicit dated "no friction" owner testimony (agents must not simulate).

### B2 — Collect organic H4 evidence

**Trigger:** After B1 runs have generated audit logs.

**Steps:**

- Re-run `scripts/prepare_h4_evidence.py --since 2026-08-13 --until <session-date>` and `scripts/build_h4_decision_packet.py` against real audit logs (not demo `/tmp/h4_demo.jsonl`).
- Record per-surface weekly coverage and empty weeks.

**Exit evidence:** Updated `.teaagent/reviews/adr-0031/` packet with organic event count; owner adjudication table with `owner_verdict`/`owner_note` per denial candidate (agents leave null).

### B3 — Evaluate BG-001 and cockpit subcriteria (M4 carve-out)

**Trigger:** B1 work-log exists.

**Steps:**

- Validate background lifecycle per `specs/background-lifecycle-acceptance-spec-2026-07-11.md` §8 (3 acceptance criteria) and cockpit per `specs/operator-cockpit-acceptance-spec-2026-07-11.md`.
- Do not claim full M4 (cloud/gateway held); only the DR-006 carve-out is eligible.

**Exit evidence:** Per-spec verdict in work-log + focused suite `tests/test_h4_*`, `tests/test_background*`, `tests/test_cockpit*` green.

## 3. Sequencing

```
09-12: dogfood scheduled?
  ├─ yes ──→ B1 (run) → B2 (evidence) → B3 (BG-001/cockpit)
  └─ no  ──→ Horizon C prune default
```

## 4. Verification after horizon

`verify_docs.sh` PASS, `validate_docs_consistency.py` PASS, sharded `6681/26` still green (or updated if dogfood code lands), no generic effect subsystem.

## 5. Related

- Execution plan §6.3 Horizon B, §7 M4 lane
- `specs/held-roadmap-forward-spec-index-2026-07-11.md` §8 dated decision queue
- Current plan Horizon A `horizon-a-close-evidence-loop-2026-09-12.md`
