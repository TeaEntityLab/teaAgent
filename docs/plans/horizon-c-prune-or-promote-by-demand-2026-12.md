# Horizon C — Prune or Promote by Demand (~2026-12-01, Q4 gate)

> **Claim class:** Bounded execution plan for trigger-only work, not a scheduling authority.
> **Authority:** `roadmap-status.md`, `backlog-priority.md`, `current-roadmap-execution-plan-2026-08-26.md` §6.3, `DR-006`, advisor `2026-08-31` hypothesis.
> **Status:** Draft, awaiting Horizon B output. No code without cited friction/governance-gap/owner-override.
> **Last updated:** 2026-09-01.

This horizon forks on Horizon B's output. It is the only Q4 gate; it does not pre-build product work.

## 1. Entry gate

`Hold` until Horizon B's dogfood session has produced a dated work-log (or explicit no-dogfood decision). Quarterly competitive survey (T5, due end-September) has landed as docs-only hypothesis intake, not code.

## 2. Tasks

### Fork decision — dated work-log evidence

- **No demand** (no friction entries, no organic `h4_governance_shadow`, no update friction, no funded live-provider gate): prune path.
- **Demand emerges:** promote path, routed per-queue row in `specs/held-roadmap-forward-spec-index-2026-07-11.md` §8. Agents do not invent demand.

### C1 — Prune path (harness with zero friction is done, not stalled)

**Trigger:** No-demand fork above.

**Steps:**

- Revert H4 shadow if still standing: remove `h4_integration.shadow` wiring, preserve `.teaagent/reviews/adr-0031/` evidence/history, keep `tests/test_h4_*` rollback proof, verify `6681` green.
- Keep `update/*` absent (no desktop packaging), `M5`/`M6` held, cloud/gateway/multi-tenant held.
- No new generic effect subsystem.

**Exit evidence:** Revert commit(s) with `verify_docs.sh` PASS + `validate_docs_consistency.py` PASS + sharded `6681/26` green. Declare H-series maintenance-mode explicitly per advisor falsifier (if owner won't schedule dogfood and won't revert, bookkeeping is the signal).

### C2 — Promote-by-demand path (per-queue row, each with its own packet)

**Trigger:** First cited need for a held lane, per §8 queue.

| Lane | Trigger | Packet to copy |
|------|---------|---------------|
| EFX-FUTURE | First provider-settlement need (per-provider identity/status/contract + fault evidence) | `ADR-0042` boundary + dated owner promise Spec |
| `teaagent update` | First owner update friction | `update-cli-wiring-and-packaging-spec-2026-07-11.md` |
| M5 non-advisory eval | First funded live-provider gate | `nonadvisory-eval-gate-promotion-spec-2026-07-11.md` |
| WDH-002 | Consenting non-maintainer + privacy preflight | `wdh-002-external-pilot-protocol-2026-07-11.md` |

Each lane requires its companion spec's promotion graph and executable-contract map; no lane may be satisfied by adding a second scheduler/queue/supervisor/agent framework.

**Exit evidence:** Per-lane commit with its §4 executable contract tests, `verify_docs.sh` PASS, `roadmap-status.md` row promoted in same commit as behavior change (cross-spec invariant §5.1/5.4).

## 3. Verification after horizon

Either path: `verify_docs.sh` PASS, docs bundle `ok:true`, inventory last, OKF current, no `legacy-competitive` item built without friction or owner-override (DR-006 falsifier).

## 4. Related

- Execution plan §6.3 Horizon C, §7 Phase 3 trigger-only lanes
- `specs/held-roadmap-forward-spec-index-2026-07-11.md` §§4–8
- Current plan Horizons A/B (`horizon-a-close-evidence-loop-2026-09-12.md`, `horizon-b-generate-evidence-via-dogfood-2026-09-12.md`)
