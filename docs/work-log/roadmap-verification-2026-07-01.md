# Roadmap Verification — 2026-07-01

> **Claim class:** Dated verification record. Confirms roadmap item status against
> code at HEAD; the canonical status surface remains
> [roadmap-status.md](../roadmap-status.md).
> **Method:** Each load-bearing claim was checked with repository tools (grep,
> targeted reads, running scripts/tests), not trusted from prior docs.
> **Review trigger:** A roadmap item changes status, or a new open item appears.

## Summary

Every **code-bearing** roadmap unit is complete. The decomposed backlog
(WD-A … WD-H) is closed except **WDH-002** (recorded outside-user sessions —
needs real non-maintainer humans, not an agent task). The harness-first
`TASK-001 … TASK-008` set is done except **TASK-001** (constitution-repositioning
text, Human-Review-gated, not independently re-verified here). The remaining
"Partially fixed" horizons (H2–H6) and pending milestones (M4–M6) are held by
governance or blocked on external evidence — see the held/external table.

This pass corrected three docs that lagged the code (see Reconciliations).

## Evidence legend

- **[verified]** — confirmed this pass with my own tools at HEAD.
- **[per index]/[per doc]** — trusted from the cited status doc; not independently re-run.

## Horizons and milestones

| Item | Status surface | Verified reality | Why not "more" |
|------|----------------|------------------|----------------|
| H0/H1, M0–M3 | Complete | [per doc] roadmap-status + M0 checks | — |
| H2 multi-surface | Partially fixed | M2 wired [per doc] | IDE/dashboard/cloud parity is external/future (harness-first descope) |
| H3 ecosystem trust | Partially fixed | M3 + WDC-002 3-concept onboarding closed [per index] | "Trust onboarding simplification" needs real daily-use signal |
| H4 durable ops | Partially fixed — shadow | Policy/RBAC **shadow-only** [per doc] | RBAC enforce flip **Held** until owner demand (ADR-0031, expiry 2026-09-12); consensus deferred (ADR-0029) |
| H5 eval loop | Partially fixed | Release eval gate in CI [per doc] | Non-advisory model/provider gate needs live provider runs + owner decision |
| H6 packaging | Partially fixed — unwired | **[verified]** single-platform update proof reproducible via `scripts/prove_update_platform.py` (emits `artifact_sha256`/`delta_sha256`/`rollback_ok`; ran green this pass — the JSON output is a regenerated machine-local artifact, not committed); **[verified]** `update/*` has no CLI wiring (`teaagent/cli` grep empty) | Desktop packaging / session-attach is future; CLI wiring intentionally deferred |
| M4 background/cloud | Pending (held) | — | cloud/SaaS/multi-tenant GTM **Held** (T4); only background-lifecycle + operator-cockpit allowed under DR-006 carve-out |
| M5 eval/repo-map | Partially fixed | repo-map corpus gated [per doc] | Model/provider regression evidence needs live runs |
| M6 desktop packaging | Pending | — | Future; no owner-platform proof beyond the H6 update proof |

## Decomposed backlog (WD-A … WD-H)

All **Closed** [per execution index `work-direction-execution-index-2026-06-10.md`]
except **WDH-002** (S6 partial — pilot harness + 3 simulated sessions done;
non-maintainer recruitment open; not an agent-completable task).
The wiring validator (`scripts/validate_wiring.py`) **passes at HEAD [verified]**
(no unlabeled unreachable islands).

## Harness-first tasks (TASK-001 … TASK-008)

| Task | Status | Evidence |
|------|--------|----------|
| TASK-001 constitution repositioning | Promote (Human-Review) | Not independently re-verified this pass; positioning text is owner-review-gated |
| TASK-002 docs tiering | **Done** | **[verified]** tier column in `docs/generated/docs-inventory.md` + aging dashboard; `check-docs-inventory` pre-commit |
| TASK-003 test typing pass | **Done** | **[verified]** all 586 test files typed (contract/behavior/adversarial/lifecycle) via `scripts/audit_test_quality.py` |
| TASK-004 flagship off deprecated approval | **Done** | **[verified]** flagship files use `--approve-scoped` (`test_first_hour_e2e_flow.py:205`, `test_five_minute_proof_flow.py:222,332`, `five-minute-proof-demo.sh:240`); 18 tests pass |
| TASK-005 doctor config provenance | Done | [per doc] harness-first §7 (2026-06-14) |
| TASK-006 RunEvent taxonomy + M0 | **Done** | **[verified]** ADR-0032 + `teaagent/runner/_events.py` spine + audit dual-write |
| TASK-007 friction log bootstrap | Met | [per doc] 5/5 owner evidence 2026-06-22 |
| TASK-008 pre-run scoped-approval CLI | **Done (via G-P2-2)** | **[verified]** `--approve-scoped TOOL:SHA256` (`preapproved_payload_digests`); `--approve-call-id` removed, inert at `teaagent/policy.py:46` |

## Held / external (must not be "done" by an agent)

| Item | Reason | Gate |
|------|--------|------|
| M4 cloud/SaaS/multi-tenant GTM | Governance hold | T4 owner decision (`backlog-priority.md`) |
| RBAC shadow → enforce (H4) | Governance hold | Owner demand + ADR-0031 (expiry 2026-09-12) |
| Consensus validation gate | Deferred | ADR-0029 (expiry 2026-12-10) |
| H5 non-advisory model/provider gate | Needs live provider runs + owner | M5 exit criteria |
| WDH-002 non-maintainer user sessions | Needs real external humans | Recruitment (not agent-completable) |
| SCL-P0 tickets | Hold until owner validates in friction log | `backlog-priority.md` |
| TASK-001 constitution text | Human Review (positioning) | Owner review |

## Reconciliations made this pass

1. `work-log/task-004-blocked-2026-06-13.md` — added a **RESOLVED** banner: TASK-004
   is done and TASK-008 unnecessary (G-P2-2 removed call-id preapproval; scoped-digest
   CLI shipped). Historical analysis retained.
2. `roadmap-status.md` H6 exit-evidence — replaced the stale "no owner-platform proof
   yet" with the verified single-platform update proof; kept status "Partially fixed —
   unwired" (CLI wiring genuinely absent).
3. `backlog-priority.md` — TASK-002/003/004/006 provenance rows moved `Promote` → `Done`
   with evidence.

## Bottom line

There is no genuinely-open, non-held, non-external **code** item left on the roadmap.
Advancing H4-enforce, M4 cloud, M5 live-model gating, or WDH-002 would violate the
project's own governance holds or require real humans/providers. The honest remaining
work was truthing-up the docs that trailed the code, done here.
