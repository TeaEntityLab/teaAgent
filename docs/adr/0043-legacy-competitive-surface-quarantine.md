# ADR 0043: Legacy-Competitive Surface Quarantine (Non-Goal Retention)

## Status

Accepted — quarantine declared 2026-09-09 (owner-adopted, ledger R-09)

**Expiry review:** 2026-12-09 (re-score each surface: promote under a recorded
`owner-override`, or delete with import-graph evidence per the ADR-0029 precedent)

## Context

The owner-ratified [harness-first direction](../strategy/harness-first-direction-2026-06-13.md)
§2 declares two binding non-goals:

- "Remote/federated multi-agent execution beyond the existing non-goals doc."
- "A general-purpose workflow/event engine. The event spine covers the **run
  lifecycle only**; it is not a plugin message bus, not a distributed queue."

The 2026-09-09 Socratic roadmap/intent panel found that code implementing exactly
those shapes is still present, still imported from production paths, still exposed
as CLI subcommands, and still gated by CI's `governance-gate` job.

Crucially, **every one of these modules predates the decisions that descoped them**
(verified with `git log --diff-filter=A`):

| Module | Added | Relative to harness-first (2026-06-13) / DR-006 (2026-06-22) |
| --- | --- | --- |
| `teaagent/federated_sync.py` | 2026-05-27 | before both |
| `teaagent/workflow_engine.py` (ADR-0030 compat shim) | 2026-05-28 | before both |
| `teaagent/context_bus.py` | 2026-05-28 | before both |
| `teaagent/signature_relay.py` | 2026-05-29 | before both |
| `teaagent/domain/workflow_engine.py` | 2026-06-20 | after harness-first, before DR-006 |

So this is **not** a governance violation — no one shipped a non-goal after it was
declared. It is an unresolved **retention** question: the direction doc descoped the
*claims* but never dispositioned the *code*, and no ADR recorded the retention. That
gap is what let a "thin, local-first" harness keep a WAN multi-signature relay and a
simulated workflow engine on the main CI path for three months without contradiction
being visible anywhere.

Reachability, as reviewed: none of these surfaces is reachable from the daily
owner-operator path (`ask` / `approve` / `undo`). They are reachable only via opt-in
CLI subcommands (`teaagent sync`, `teaagent consensus`, `teaagent control-plane serve`)
or non-default configuration (`MultiSigQuorumConfig.enabled=False`,
`SwarmManager(enable_consensus=False)`). `teaagent/domain/workflow_engine.py` has no
production caller at all and its `_execute_step` is explicitly simulated.

## Decision

**Quarantine, do not delete — yet.** Each surface below is declared
`legacy-competitive` and **On Hold** under
[DR-006](../strategy/dr-006-owner-decision-2026-06-22.md). Concretely:

1. **No new feature work** on a quarantined surface without a dated
   `owner-override` rationale recorded in DR-006 or the operator friction log.
2. **No present-tense capability claims.** README, `docs/product-contract.md`, and
   roadmap docs must not describe federation, consensus, signature relay, or a
   workflow engine as delivered capability.
3. **Retention is explicit, not accidental.** This ADR is the record that the
   contradiction with harness-first §2 is *known and accepted for now*, with a dated
   expiry rather than an open end.
4. **Deletion requires the ADR-0029 procedure**: preserve intent + symbol inventory +
   git recovery anchor first, then remove runtime files and the tests that pin them.

Why not delete immediately (rejecting the panel's stronger recommendation): three of
these surfaces are lazily imported from production code and wired to live CLI
subcommands. Deleting CLI-reachable code on a review's authority, without an owner
decision on the multisig and operator-cockpit carve-out, would itself be an
ungoverned external effect — the exact failure class EFX-001..003 exists to prevent.

### Quarantined surfaces

| Surface | LOC (approx) | Daily-path reachable | DR-006 class | Disposition at expiry |
| --- | --- | --- | --- | --- |
| `teaagent/federated_sync.py` (P2P graph sync, file-based multi-sig) | 763 + 398 test | No — `teaagent sync`, or `MultiSigQuorumConfig.enabled=True` | `legacy-competitive` | Promote under `owner-override` if multisig is wanted, else delete |
| `teaagent/signature_relay.py` (WAN HTTP signature relay) | 492 + 212 test | No — `teaagent sync signature-relay` | `legacy-competitive` | Delete with `federated_sync` unless WAN multisig is ratified |
| `teaagent/domain/workflow_engine.py` (multi-step, simulated execution) | 768 + 91 test | **No production caller**; `_execute_step` simulated | `legacy-competitive` | **Strongest deletion candidate** — needs an importer sweep first |
| `teaagent/workflow_engine.py` (root compat shim) | 24 | Import shim only | `harness-migration` | Keep while ADR-0030 root-module freeze stands; delete with its target |
| `teaagent/consensus/` + `teaagent/cli/_handlers/_consensus.py` | 475 + engine/registry/voting | No — `teaagent consensus`, `enable_consensus=False` by default | `legacy-competitive` | Delete per ADR-0029 precedent unless swarm consensus is ratified |
| `teaagent/jit_approval_server.py` (remote SSE JIT approval) | 445 + 286 test | No — `teaagent control-plane serve` | M4 carve-out, needs `owner-override` | Covered by the M4 background-lifecycle/operator-cockpit carve-out **only if** a dogfood session is scheduled; else delete |
| `teaagent/context_bus.py` (DeltaCard store) | — | No — used by `teaagent/swarm.py` | `harness-migration` | Governed by G3/ADR-0032, not by this ADR; see the accepted fourth-parallel-system risk |

## Consequences

- Positive: the contradiction between harness-first §2 and the shipped surface is now
  recorded in one dated place with an expiry, instead of being invisible.
- Positive: `governance-gate` continuing to run these tests is now *justified* — they
  guard quarantined-but-live code, rather than silently enforcing non-goals.
- Negative: the harness keeps carrying roughly 2,900 LOC of quarantined surface plus
  ~1,000 LOC of tests, and their security surface (SSRF validation, HTTP relay auth,
  SQLite/WAL locking) stays in scope for review.
- Negative: quarantine is weaker than deletion. If the 2026-12-09 expiry passes
  without a disposition, this ADR has failed in exactly the way ADR-0031's own
  rationale warns about ("wired quietly becomes the new implemented-but-unwired").

## Falsifier

This decision was wrong if, at the 2026-12-09 review, no surface has been either
promoted under a recorded `owner-override` or deleted — i.e. if quarantine merely
became a permanent parking lot with a nicer label.

## References

- [Harness-First Direction](../strategy/harness-first-direction-2026-06-13.md) §2 non-goals
- [DR-006 Owner Decision](../strategy/dr-006-owner-decision-2026-06-22.md) scheduling gates + M4 carve-out
- ADR 0029 (deletion precedent: preserve intent, then delete), ADR 0030 (root-module compat shims), ADR 0032 (run event taxonomy)
- [Roadmap/intent Socratic panel record](../reviews/roadmap-intent-socratic-2026-09-09.md) (R-09)
