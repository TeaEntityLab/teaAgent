# External Advisor Roadmap Hypothesis — 2026-08-31

> **Claim class:** Dated evidence record of an external-advisor consultation.
> Hypothesis only — never a scheduling authority. DR-006 and
> `docs/roadmap-status.md` remain authoritative; nothing here schedules,
> promotes, or reverts anything.
> **Provenance:** internalized 2026-09-17 from the local-only run artifact
> `.omx/artifacts/claude-you-are-an-external-advisor-for-teaagent-a-harness-first-own-2026-08-31T06-14-02-585Z.md`
> (provider `claude`, created 2026-08-31T06:14:02Z, exit code 0). That path is
> excluded from git (`.git/info/exclude`), so the three committed docs that
> cited it (`backlog-priority.md` advisor note, `roadmap-status.md` H4 row,
> `plans/current-roadmap-execution-plan-2026-08-26.md` §6.3) now cite this
> file instead. §2 is the advisor's raw output, verbatim. §3 is the
> agent-prepared disposition as of 2026-09-17 — evidence only, no owner verdict.
> **Last reviewed:** 2026-09-17
> **Review trigger:** ADR-0031 close (2026-09-29), DR-006 calendar review
> trigger (2026-09-22), or the Horizon C fork (ADR-0043 disposition 2026-12-09).

---

## 1. Prompt snapshot (what the advisor was told, 2026-08-31)

Current truth as stated to the advisor (main at `c8a3e7d` → `7ca7aaa`, 6681
tests green via sharded `-n auto`, 6707 collected):

- H0 Complete, H1 Complete, H2 On Hold (M2 done), H3 On Hold (M3 done), H4 On
  Hold — shadow wiring exists (ADR-0031 packet: C2/3/5 pass, C1 0 shadow events
  unexercised, C4 human sign-off pending, `promotion_ready=false`, expiry
  2026-09-12, demo `scripts/exercise_h4_shadow_demo.py` exercisable, 2
  candidates guarded), H5 Blocked (offline fixture), H6 On Hold (local proof, no
  CLI).
- Milestones M0–M3 Complete, M4 On Hold except dogfood carve-out, M5 Blocked,
  M6 On Hold.
- Governance-gap: EFX-001/002/003 all In Progress with runtime guards +
  providerless acceptance (15 passed via `test_efx*`); live GitHub/browser
  proof pending owner auth.
- DR-006 and harness-first direction authoritative; thin-harness invariant.
- Operator friction log 5/5 closed (F2/F3/F6/F7/F8), zero new friction, WDH-002
  Hold, M4 dogfood Hold.
- Next gate 2026-09-12: ADR-0031 promote/extend/revert + EFX live-proof closure.

Question posed: "what should be the next roadmaps after 2026-09-12? Propose 2-3
horizons/milestones with ordered priorities, what to promote vs hold vs revert,
and what concrete exit evidence would justify each. Keep it harness-first, not
external adoption, and respect DR-006 gates."

## 2. Advisor output (verbatim)

```text
Grounded in `roadmap-status.md`, DR-006, and the dated decision queue at HEAD. Recommendation first, then the horizons.

**Bottom line:** Don't promote anything at 2026-09-12 except EFX closure. The ADR-0031 packet cannot justify promotion (C1 = 0 organic shadow events; the demo script's 2 candidates are synthetic and must not launder into C1). The real problem your snapshot reveals: the roadmap's fuel is exhausted — friction log 5/5 closed, zero new entries, no dogfood scheduled. Every DR-006 lane except `governance-gap` is starved. The next roadmap's job is to restart evidence generation, not to build.

## 2026-09-12 dispositions

- **Promote:** nothing on 09-12 itself. EFX-001–003 promote to Complete only when live proof lands (see A1).
- **Extend (conditionally):** ADR-0031 H4 shadow — one extension only, and only if bound to a scheduled dogfood session that generates organic events. A passive extension re-runs another 0-event window and decides nothing.
- **Revert (default):** H4 shadow wiring if no dogfood is scheduled by 09-12, or if the extended window again shows 0 organic events. Unexercised wiring violates the thin-harness invariant; you have rollback proof requirements in the packet already.
- **Hold unchanged:** H2, H5 (Blocked), H6, M4-beyond-carve-out, M5, M6, WDH-002, EFX-FUTURE.

## Horizon A — Close the evidence loop (09-12 → ~10-15)

1. **EFX live proof** (only authorized, unblocked code item; blocked solely on owner auth). Owner provisions throwaway repo + scoped credential + budget cap; run `docs/plans/efx-live-proof-procedure-2026-08-31.md`. **Exit:** dated live receipts on a real GitHub target showing (a) interrupted dispatch → OUTCOME_UNKNOWN + refused blind redispatch, (b) fail-closed classification of an unknown effectful tool, (c) digest-bound approval rejecting a mutated/replayed call; audit chain intact; evidence bundle committed; EFX rows → Complete.
2. **Execute ADR-0031 disposition** per above. **Exit:** dated owner sign-off + either >0 organic shadow events or revert commit with green suite (~6681) and rollback proof.
3. **DR-006 falsifier review** — the 3-month window from 06-22 closes ~09-22. **Exit:** dated owner note walking the four falsifiers (all currently look clear; record that explicitly).

## Horizon B — Generate evidence via dogfood (parallel, ~09-12 → ~11-15)

The M4 co-maintainer carve-out (background lifecycle + cockpit) is the *only* lane that can produce what everything downstream is waiting on: organic shadow events (ADR-0031 C1), new friction entries (DR-006 friction lane), and BG-001/cockpit evidence (M4 gate). Owner noted 07-22 it's held with no scheduled session — schedule one or accept Horizon C's prune default.
**Exit:** ≥1 dated dogfood work-log session; organic policy/shadow event count recorded; new friction entries *or* explicit dated "no friction" owner testimony (agents must not simulate); BG-001 subcriteria evaluated. Cloud/gateway/multi-tenant stay held.

## Horizon C — Prune or promote by demand (~Q4 gate, ~12-01)

Fork on Horizon B's output, decided through the existing dated queue — no new lanes:
- **No demand** (no friction, no organic events): revert H4 shadow if still standing, keep `update/*` absent, M5/M6 held. A harness with zero friction and closed backlog is *done*, not stalled — shrink it. **Exit:** reverts with rollback proof, suite green, `validate_docs_consistency.py` + evidence bundle clean.
- **Demand emerges:** route each item through its queue row (EFX-FUTURE only on first provider-settlement need; `teaagent update` only on first update friction; M5 only on first funded gate) with the required packets. **Exit:** per-row packet as already specified in §8 of the held-roadmap index.
- Either way: quarterly competitive survey (T5, due ~end of September) as docs-only hypothesis intake.

**Assumptions stated:** owner remains sole evidence source; 09-12 date holds; no external adoption goal. **Falsifier for this whole proposal:** if the owner won't schedule dogfood *and* won't revert, the roadmap has become status bookkeeping — that's the signal to declare H-series maintenance-mode explicitly rather than extend gates indefinitely.
```

## 3. Disposition as of 2026-09-17 (agent-prepared; evidence, not verdicts)

| Advisor item | What happened | Evidence |
| --- | --- | --- |
| Promote nothing on 2026-09-12 | Nothing promoted; the 09-12 review recorded `unexercised` (0 observed / 0 reachable) | `roadmap-status.md` Review 2026-09-12 |
| Extend ADR-0031 only if bound to a scheduled dogfood session | Owner extended on 2026-09-14 bound to a session booked for 2026-09-15; window closed 2026-09-15 at **9 observed / 22 reachable / 1 denial candidate, verdict `needs_review`**; decision deadline 2026-09-29, readiness checklist 0/8 signed | `roadmap-status.md` Updates 2026-09-14/15, H4 row; `work-log/adr-0031-2026-09-29-readiness-checklist.md` |
| Revert (default) if no session or another 0-event window | Not triggered — a session was booked and the window produced events. Caveat: the 9 receipts are `origin: dogfood` (agent-driven session), and `prepare_g1_evidence.py` still reports **0 `origin: owner` runs**; whether agent-driven receipts satisfy the advisor's "organic" is the owner's D1/criterion-1 call | `scripts/prepare_g1_evidence.py` (`unexercised`), `dogfood-findings-2026-09-15.md` §H4 evidence |
| Hold unchanged: H2, H5, H6, M4-beyond-carve-out, M5, M6, WDH-002, EFX-FUTURE | All still Hold/Blocked | `roadmap-status.md` Horizons and Milestones tables |
| A1 — EFX live proof | Still pending owner-authorized credentials/target; EFX-001–003 remain In Progress; exit evidence narrowed 2026-09-13 to one real provider mutation observed to behave as classified | `roadmap-status.md` EFX table + 2026-09-13 clarification |
| A2 — ADR-0031 disposition | Open; owner sign-off (criterion 4) + D1 classification due 2026-09-29 | `work-log/adr-0031-2026-09-29-readiness-checklist.md` (0/8) |
| A3 — DR-006 falsifier review (~2026-09-22) | Falsifier 1 mechanical via `scripts/check_dr006_gate_trailer.py` and clean since 2026-09-09; F2–F4 unexercised; the dated owner note walking all four is not yet written. 2026-09-22 is a calendar trigger, not an authority expiry | `roadmap-status.md` Correction 2026-09-15; Review 2026-09-17 |
| B — Dogfood session | Agent-driven co-maintainer session ran 2026-09-15 under the M4 carve-out: 38 findings (G1–G38) adjudicated by the owner on 2026-09-15/16 and implemented; BG-001 orphan path found unimplemented (G-series); **B1 owner-observed coding evidence still pending**; no new owner-written friction entries (agent verification evidence added 2026-09-14 on three open hypotheses) | `work-log/m4-dogfood-2026-09-15.md`, `work-log/dogfood-findings-2026-09-15.md`, `work-log/operator-friction-log.md` |
| C — Prune-or-promote fork (~2026-12-01) | Not reached; nearest matching gate is the ADR-0043 quarantine disposition on 2026-12-09 | `adr/0043-legacy-competitive-surface-quarantine.md` |
| T5 quarterly survey (~end of September) | Two docs-only survey intakes landed 2026-09-13 (agentflow v8.2.0 delta → AGF-001–004; vendor direction survey → VND-001–003) | `roadmap-status.md` intake sections |
| Proposal falsifier ("won't schedule dogfood and won't revert") | Not triggered — the owner scheduled the session | `roadmap-status.md` Update 2026-09-14 |

## References

- [Roadmap Status](../roadmap-status.md) (canonical current truth)
- [DR-006 Owner Decision](../strategy/dr-006-owner-decision-2026-06-22.md)
- [Current Roadmap Execution Plan](../plans/current-roadmap-execution-plan-2026-08-26.md) §6.3
- [Backlog Priority](../backlog-priority.md) advisor note
