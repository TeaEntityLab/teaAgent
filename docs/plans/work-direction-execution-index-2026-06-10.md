# Work Direction Execution Index — TeaAgent
# 2026-06-10

> **Claim class:** Current truth for post-review execution order.
> **Derived from:** [Work Direction Decomposition](work-direction-decomposition-2026-06-10.md)
> and the [June 10 System Critical Review Package](../analysis/system-critical-review-2026-06-10-INDEX.md).
> **Supersedes for execution routing:** the June 6 workstream spine is substantially
> closed; use [System Improvement Work Directions (2026-06-06)](system-improvement-work-directions-2026-06-06.md)
> only for unresolved WS0/WS4/WS5/WS6 items not restated in the June 10 backlog.
>
> **Review trigger:** P0 item closure, suite tier changes, or roadmap truth fixes.
> **Last reviewed:** 2026-06-10
> **Scheduled anchor:** `85109e4` (review package commit)

---

## Executive Rule

**Truth before features.** No new H4/H5/H6 capability work until Sprint 1
closes. The import graph, roadmap, and commit log must tell one story before
any eval-gate or remote-approval differentiation work begins.

---

## Sprint Calendar

| Sprint | Window | Theme | Exit gate |
| --- | --- | --- | --- |
| **S1 — Truth pass** | 2026-06-10 → 2026-06-17 | Label, validate, tier | WDA-001 + WDB-001 + WDB-003 + WDG-002 merged; roadmap rows honest |
| **S2 — Shadow wiring** | 2026-06-17 → 2026-07-01 | H4/H5 shadow integration | WDA-002 + WDA-003 merged; zero acceptance regression |
| **S3 — Gate enforcement** | 2026-07-01 → 2026-07-15 | CI release profile + eval corpus | WDA-004 + WDD-001 merged |
| **S4 — Front door** | parallel from S2 | General-user simplification | WDC-001 baseline + WDC-002 happy path |
| **S5 — Remote + consolidate** | after S3 | Remote approval + tree hygiene | WDE-001/002, WDF-001 opportunistic |
| **S6 — External validation** | after S4 | Positioning proof | WDH-002/003 |

Sprint windows are planning targets, not release commitments. Slip S2 if S1
validators are not green.

---

## Critical Path (Sprint 1)

```
WDA-001 (label unwired islands)
  └─► WDB-001 (import-graph wiring validator)
        └─► WDB-003 (roadmap contradiction fix)
              └─► WDG-002 (smoke / acceptance / nightly tiers)
                    └─► WDG-001 (diagnose SIGXCPU truncation — parallel)
```

**Parallel lane (independent files):** WDC-001 stranger-test baseline may start
any time after S1 WDA-001 lands (needs honest module labels for concept audit).

---

## Ticket Plans — Sprint 1 (P0)

| ID | Priority | Size | Plan | Summary |
| --- | --- | --- | --- | --- |
| WDA-001 | P0 | S | [WDA-001-plan](ticket-plans/WDA-001-plan.md) | **Closed** — 13 watch-list modules labeled; roadmap H4–H6 honest |
| WDB-001 | P0 | M | [WDB-001-plan](ticket-plans/WDB-001-plan.md) | **Closed** — `scripts/validate_wiring.py` + CI/docs gate |
| WDB-003 | P0 | S | [WDB-003-plan](ticket-plans/WDB-003-plan.md) | **Closed** — roadmap reconciled; horizon/milestone validator |
| WDG-001 | P0 | M | [WDG-001-plan](ticket-plans/WDG-001-plan.md) | **Closed** — [root-cause note](../analysis/suite-truncation-root-cause-2026-06-10.md) |
| WDG-002 | P0 | M | [WDG-002-plan](ticket-plans/WDG-002-plan.md) | **Closed** — `run_test_tier.py`, markers, CI smoke split |

---

## Backlog Queue (scheduled, not yet ticketed)

| Sprint | IDs | Notes |
| --- | --- | --- |
| S2 | WDA-002, WDA-003, WDA-006 | **Closed** — shadow policy + RBAC enforce; ADR 0029 |
| S3 | WDA-004, WDD-001, WDD-002 | **Closed** — release eval gate + conversational corpus; [eval gate design](../analysis/eval-gate-design-2026-06-10.md) |
| S3b | WDA-005 | Single-platform update proof (queued) |
| S4 | WDC-002, WDC-003, WDC-004 | Three-concept onboarding; terminology freeze |
| S5 | WDE-001, WDE-002, WDE-003, WDF-001, WDF-002 | Remote backend; root-module freeze |
| S6 | WDH-001, WDH-002, WDH-003 | Stop surveys; external users; "when not to use" page |
| Ongoing | WDB-002, WDB-004, WDG-003 | Claim-commit hook; suite freshness rule; machine-readable summary |

Ticket plans for S2+ items are created when the prior sprint exit gate passes.

---

## Definition of Done — Sprint 1

- [x] Every unwired `teaagent/*` module carries `experimental — unwired` in docstring and roadmap.
- [x] `scripts/validate_wiring.py` fails CI on unlabeled unreachable watch-list modules.
- [x] `docs/roadmap-status.md` H2–H6 rows match import-graph reality and milestone table.
- [x] `scripts/run_test_tier.py` smoke/acceptance/nightly profiles documented in `docs/acceptance.md`.
- [x] WDG-001 root-cause note exists ([suite truncation analysis](../analysis/suite-truncation-root-cause-2026-06-10.md)).

---

## Related Documents

| Document | Role |
| --- | --- |
| [Work Direction Decomposition](work-direction-decomposition-2026-06-10.md) | Full WD-A … WD-H backlog with acceptance gates |
| [Engineering Critique Refresh](../analysis/engineering-critique-refresh-2026-06-10.md) | ENG-R1/R2 evidence |
| [Roadmap Status](../roadmap-status.md) | Canonical status surface (WDB-003 target) |
| [Ticket Execution Plans (daily-driver)](ticket-plans/index.md) | Historical daily-driver closure index |
