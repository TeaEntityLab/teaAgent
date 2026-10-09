# DR-006 Owner Decision — Epistemology & Release Gates

> **Claim class:** Direction decision snippet (owner-ratified).
> **Date:** 2026-06-22.
> **Derived from:** multi-role debate (Friction Purist, Evidence Archaeologist,
> Harness Scheduler, Release Pragmatist, Platform Devil's Advocate) +
> [Direction Review Agenda](direction-review-agenda-2026-06-22.md).
> **Supersedes:** unresolved T1/T5 in direction-review-agenda §2 (status only).
> **Pairs with:** DR-001 (owner friction evidence — still owner-blocking).

---

## Converged decision (debate synthesis)

TeaAgent harness-first is **scheduling discipline for code**, not positioning-only.
**Docs claim hygiene** and **co-maintainer dogfooding** remain gated separately.

### T1 — Epistemology: **Option B+ (dual track, enforced)**

Not pure Option A (would stall M4 dogfood and conflate docs with code).
Not Option C (contradicts 2026-06-13 ratification).

**Code / platform scheduling** requires one of:

| Gate | When |
| --- | --- |
| `friction-driven` | Cited owner evidence entry in [operator-friction-log.md](../work-log/operator-friction-log.md) |
| `governance-gap` | Structural correctness (audit, approval, budget) with traceable test/ADR proof |
| `owner-override` | Dated one-paragraph rationale in friction log or this file; tag `legacy-competitive` items explicitly |

**Rules:**

- Competitor surveys → **hypothesis intake only** until owner validates (harness-first §5.1).
- `legacy-competitive` items (CP-4 escalation, CP-6, SCL-P0, full M4 cloud/SaaS) stay **on hold** without friction evidence or `owner-override`.
- **Carve-out:** M4 **background lifecycle + operator cockpit** may proceed under `owner-override: co-maintainer dogfood` (harness-first §1) — not enterprise multi-tenant GTM.
- **TASK-007 / DR-001:** Scaffold done (7a); ≥5 owner evidence entries (7b) **met 2026-06-22** (F2/F3/F6/F7/F8 in operator-friction-log). Agents must not simulate further evidence.

### T5 — Release gates: **Option C (split gate)**

Not full downgrade (loses acceptance-count drift protection).
Not status quo (per-release competitive ritual conflicts with harness-first §2).

| Layer | Gate |
| --- | --- |
| **CI on `main`** | Keep blocking `refresh_competitive_docs.py --check` (generated artifact + consistency bundle) |
| **Manual pre-tag** | Trust CI-green commit; re-run `--check` only for off-main hotfixes |
| **Constitution truth** | `validate_docs_consistency.py` + acceptance collect-only match remain release blockers |
| **Competitive survey steps 1–3** | **Quarterly** or before public positioning claims — not per-release |

---

## DR-001 resolution (paired)

| Phase | Status | Owner |
| --- | --- | --- |
| **7a Scaffold** | Done | Agents |
| **7b Evidence (≥5)** | **Done (2026-06-22)** | Owner — F2/F3/F6/F7/F8 confirmed |

Agents completed permitted work. DR-001 acceptance = owner testimony only.

---

## Falsifiers (3 months)

| Signal | Decision failed |
| --- | --- |
| `feat:` commit touching `teaagent/` has no commit message trailer (`Gate:` or `Constraint:`) whose value cites one of `friction-driven`, `governance-gap`, `owner-override` — mechanical check in `scripts/check_dr006_gate_trailer.py` | T1 lip service |
| Release tagged off-main with stale generated docs and no local `--check` | T5 split gate broken |
| New UX tickets cite `competitive-positioning-plan` without friction ID | T1 not enforced |
| Quarterly survey skipped while README makes fresh comparison claims | T5 docs track broken |
**Amendment (2026-09-09):** Falsifier 1 is now enforced mechanically by `scripts/check_dr006_gate_trailer.py`. `Gate:` is the canonical trailer; `Constraint:` trailers containing an accepted gate token are accepted during the transition because they were already in use (e.g. `87d1c61`).

**Review record (2026-10-09, owner-ratified in session):** the three-month
falsifier review due ~2026-09-22 was performed on 2026-10-09. F1 (gate
trailer): mechanical check `python3 scripts/check_dr006_gate_trailer.py --base 3ff0fa24`
exits 0 on this tree (no output; the script prints only on violation) — every
`feat:` commit touching `teaagent/` since 2026-09-09 cites a gate; no violation.
The `--base 3ff0fa24` range starts after 2026-09-09, so the full window was also
checked with `--base 8b613392` (last commit before 2026-09-09), which exits 0.
F2 (off-main release with stale generated docs): not exercised — no release
tag exists after `v0.1.0-p4-remediation`; the only later tag is
`tui-chat-not-merged-yet` (annotated, 2026-05-30, on `395f173`), a work marker
by name rather than a release. F3 (UX tickets citing the competitive plan
without a friction ID): not exercised — no new UX ticket was opened. F4 (survey
skipped while README makes fresh comparison claims): no fresh comparison claim
was added; the T5 quarterly survey itself is recorded below. Decision: T1
Option B+ and T5 Option C stand unchanged.

**T5 quarterly survey record (2026-10-09):** the Q3 (end-September) docs-only
competitor UX survey was not run on time. The owner directed on 2026-10-09
that it be run; the attempt in the recording environment could not reach any
vendor documentation host (outbound access limited to the proxy allowlist),
so no survey file was produced. Recorded as **attempted, blocked, deferred**:
the next attempt must be made from an environment with vendor-docs access,
remains docs-only hypothesis intake per harness-first §5.1, and is due no
later than 2026-12-31. No positioning claim may be refreshed until it runs.

---

## Owner ratification

- [x] I ratify T1 Option B+ and T5 Option C as recorded above.
- [x] I will seed ≥5 owner evidence entries by **2026-07-22** (or record why deferred). **Met 2026-06-22** (F2/F3/F6/F7/F8).

**Ratified by:** owner-operator  
**Date:** 2026-06-22

## Related

- [Operator Friction Log](../work-log/operator-friction-log.md)
- [Release Checklist](../release-checklist.md) (T5 implementation)
- [Backlog Provenance](../backlog-priority.md#backlog-provenance-dr-004-2026-06-22)
