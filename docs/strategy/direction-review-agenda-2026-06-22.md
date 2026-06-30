# Direction Review Agenda — Post-Intent Debate

> **Claim class:** Direction review agenda (owner action required).
> **Date:** 2026-06-22.
> **Derived from:** parallel intent debate (Harness Purist, Product/UX, Protocol
> Portability, Runtime Safety, Devil's Advocate) and
> [Harness-First Direction](harness-first-direction-2026-06-13.md).
> **Human review required before:** backlog reprioritization, release-gate changes,
> deleting platform code, or changing public positioning.

---

## 1. Converged Intent (baseline for this review)

TeaAgent is the **owner-operator's personal, local-first, governance-first
coding-agent harness** — one person who maintains, uses, and audits his own
agentic coding runs.

| Axis | Converged answer |
| --- | --- |
| Identity | Governance-first **coding-agent harness** (not harness-only platform, not market Claude Code clone) |
| Thin harness | **Binding constraint on new work**; not a present-tense description of `runner/_core.py`, `domain/`, or `swarm.py` |
| Protocol | Portable governance artifacts (tools, audit, skills, run records) = north star; Claude-ecosystem ergonomics = current substrate |
| Safety | PRIMARY = governed, recorded, bounded action; gates adjustable by explicit owner choice, never silent |

---

## 2. Owner Decisions Required (five tensions)

Each item needs an **owner call** before engineering can proceed without
re-litigating intent.

### T1 — Epistemology: friction log vs competitor backlog

**Status:** **Resolved** — Option B+ ratified in [dr-006-owner-decision-2026-06-22.md](dr-006-owner-decision-2026-06-22.md) (2026-06-22).

**Tension:** `operator-friction-log.md` has **0 owner evidence entries** while
backlog and release checklist still optimize for competitive surveys and
platform surface.

**Owner question:** Is harness-first **scheduling discipline** or **positioning
discipline only**?

**Options:**

| Option | Implication |
| --- | --- |
| **A. Enforce friction-first** | No new UX/platform tickets without friction-log evidence or governance-gap proof; downgrade competitive refresh from release blocker |
| **B. Dual track** | Keep competitive hygiene for docs; code backlog requires friction log or explicit owner override with dated rationale |
| **C. Revert positioning** | Admit OSS competitive agent intent; supersede harness-first non-goals with new direction record |

**Falsifier (3 months):** If Option A and log stays at 0 while CP-* / M4 items ship → A failed.

---

### T2 — Runner gravity well vs UX delivery

**Tension:** G3/G4 (event spine, hooks-not-forks) vs shipping UX through
`AgentRunner` (~1,104 LOC gravity well).

**Owner question:** Freeze feature work on runner internals until M0–M1, or
allow UX fixes inline with extraction debt tracked?

**Recommended default:** UX fixes that touch runner require a **lifecycle test**
asserting event sequence (TASK-006 dependency), not internal-method tests.

---

### T3 — `domain/` and `swarm.py` fate

**Tension:** ~2,761 LOC in `teaagent/domain/`, ~1,010 in `swarm.py` violate
thin-harness spirit; A-P1-1 moved code but did not expel it.

**Owner question:**

| Option | Action |
| --- | --- |
| **Migrate** | Move workflows to skills/hooks; archive domain modules |
| **Retain** | Mark as permanent harness-adjacent product layer with ADR |
| **Freeze** | No new domain logic; existing code maintenance-only |

---

### T4 — Platform code scope (multi-tenant, federation, cloud)

**Tension:** Shipped multi-tenant control plane, A2A federation, OAuth/Redis
stores read as OSS platform, not solo owner-operator harness.

**Owner question:** Mark experimental/non-default, document owner-only scenarios,
or schedule deprecation?

**Devil's advocate break condition:** If no owner scenario requires
`X-TeaAgent-Tenant`, treat as latent OSS intent residue.

---

### T5 — Release gates vs harness-first non-goals

**Status:** **Resolved** — Option C (split gate) ratified in [dr-006-owner-decision-2026-06-22.md](dr-006-owner-decision-2026-06-22.md); implemented in [release-checklist.md](../release-checklist.md).

**Tension:** `release-checklist.md` still requires `refresh_competitive_docs.py
--check` before minor releases; harness-first §2 lists competitor parity as
non-goal.

**Owner question:** Keep competitive refresh as **docs hygiene** (read-only
check) or remove as **release blocker**?

---

## 3. Immediate Actions (parallel batch)

Aligned with harness-first §7 TASK sequencing and debate gaps.

| ID | Action | Owner | Agent-executable | Acceptance |
| --- | --- | --- | --- | --- |
| **DR-002** | Reconcile `AGENTS.md` with permission modes + thin-harness target | Agent | **Done in this batch** | Rules match `approval/manager.py` behavior |
| **DR-003** | Stale compliance matrix refresh | Agent | **Done (2026-06-22)** | [05-compliance-matrix.md](../retrospective/05-compliance-matrix.md) — 0 Violated, 2 Partial |
| **DR-001** | Seed friction log with ≥5 **owner-written** evidence entries | **Owner** | **Done (2026-06-22)** — 5 entries (F2/F3/F6/F7/F8) |
| **DR-004** | Backlog triage: tag each open item `friction-driven` \| `governance-gap` \| `legacy-competitive` \| `owner-override` | Agent + Owner | **Done (2026-06-22)** | `backlog-priority.md` provenance section |
| **DR-005** | Platform inventory: list multi-tenant/federation/cloud modules with `owner-scenario: yes/no/unknown` | Agent | **Done (2026-06-22)** | Table in §4 below |
| **DR-006** | Owner decision on T1 + T5 (epistemology + release gates) | **Owner** | **Ratified 2026-06-22** — [dr-006-owner-decision](dr-006-owner-decision-2026-06-22.md) |

**Sequencing:** DR-001 and DR-006 complete (2026-06-22). Friction-first UX scheduling may cite owner evidence IDs F2–F8 subset.

---

## 4. Platform Inventory (DR-005)

Modules shipped as **Beta** that exceed solo owner-operator scope unless explicitly
enabled. Owner scenario column is **unknown** until validated in friction log or
owner override (T4).

| Module / surface | Path | Default in daily path? | Owner scenario | Direction |
| --- | --- | --- | --- | --- |
| Multi-tenant control plane | `teaagent/control_plane_tenant.py`, `control_plane_api.py` | No — `teaagent control-plane serve` | **unknown** | Hold — mark experimental or document owner-only use |
| Control plane CLI | `cli/_handlers/_control_plane.py` | No | **unknown** | Hold |
| Federated A2A registry | `teaagent/agentcard.py` (`FederatedAgentRegistry`) | No | **unknown** | Hold |
| A2A HTTP discovery | `agentcard.py` (`A2ADiscoveryServer`) | No | **unknown** | Hold |
| Consensus + SSH vote relay | `teaagent/consensus.py`, `vote_relay.py` | No | **unknown** | Hold |
| PostgreSQL / Redis OAuth stores | `oauth21/_pg_store.py`, `_redis_store.py` | No | **no** (hosted deploy) | Downgrade default docs emphasis |
| JIT approval server | `teaagent/jit_approval_server.py` | No | **unknown** | Hold |
| Swarm + tournament | `teaagent/swarm.py`, `tournament/` | No (opt-in) | **yes** (dogfood) | Freeze per T3 — no new logic |
| Domain workflows | `teaagent/domain/` | Yes (issue intake, intent) | **yes** (in-repo) | T3 owner call: migrate / retain / freeze |
| Claude-ecosystem hooks | `teaagent/hooks.py`, `plan_mode.py` | Yes (chat/TUI) | **yes** (substrate) | Protocol migration behind event spine |
| M4 cloud/background (roadmap) | `docs/roadmap-status.md` M4 | No | **unknown** | **Hold** until T4 + DR-001 |

**Line-count debt (thin-harness target):**

| Area | LOC (approx.) | Notes |
| --- | ---: | --- |
| `teaagent/domain/` | 2,761 | Workflow/intent logic in harness package |
| `teaagent/runner/_core.py` | 1,104 | Gravity well; TASK-006 target |
| `teaagent/swarm.py` | 1,010 | Second orchestration surface |
| `subagents/_hybrid_store_*.py` | 4,888 | Decomposed from monolith; still large product surface |

---

## 5. Backlog Reprioritization (recommended)

Until DR-001 completes, treat backlog as **hypothesis backlog**, not
evidence-backed.

### Promote (aligns with ratified goals G1–G6)

| Work | Rationale |
| --- | --- |
| TASK-006 RunEvent taxonomy + M0 dual-write | G3, thin runner migration |
| TASK-001 constitution doc repositioning | Persona truthfulness |
| TASK-004 flagship tests off deprecated approval | Governance correctness |
| TASK-003 test typing pass | G6 |
| TASK-002 docs tiering | G5 |

### Hold (pending owner decision)

| Work | Blocker |
| --- | --- |
| M4 cloud/background/control-plane cockpit | T4 platform scope |
| New Claude Code field-parity features | T1 friction evidence |
| Seven-control-loops SCL-P0 tickets | T1 — competitor-derived until owner validates |
| RBAC enforce flip (ADR 0031, expiry 2026-09-12) | T4 — need owner demand signal |

### Downgrade (docs-only unless owner overrides)

| Work | Rationale |
| --- | --- |
| Competitive refresh as **release blocker** | Conflicts with harness-first §2 non-goals; keep `--check` as optional CI job |
| CP-6 community presence execution | External acquisition non-goal |
| OpenCode gap watch **escalation → feature sprint** | Hypothesis intake only per §5.1 |

---

## 6. Falsifiability Dashboard (review monthly)

| Signal | Harness-first real | Harness-first lip service |
| --- | --- | --- |
| Friction log owner entries | ≥5, cited by new tickets | Stays 0 |
| New UX tickets | Cite friction log ID | Cite competitive-positioning-plan |
| M4 cloud track | Deferred with rationale | Advances without friction entry |
| `domain/` LOC | Shrinks or ADR-retained | Grows |
| Release gate | Competitive check optional | Still blocking |
| README persona | Owner-operator only | Enterprise/CISO golden paths as present-tense |

---

## 7. AGENTS.md Reconciliation (DR-002)

Changes applied in `AGENTS.md` (same commit family as this agenda):

1. Thin harness = **target invariant**, not current-size claim.
2. Destructive-tool approval = **mode-relative** (`prompt`/`read-only`/`workspace-write` enforce exact-call tokens; `allow`/`danger-full-access` are declared widenings with audit).
3. Governed path = policy before `ToolRegistry.execute()` for production runs.

---

## 8. Next Review

- **Trigger:** Owner completes DR-001, or 2026-07-22 (monthly), whichever first.
- **Output:** Update falsifiability dashboard; close or promote tension items T1–T5.

## Related

- [Harness-First Direction](harness-first-direction-2026-06-13.md)
- [Operator Friction Log](../work-log/operator-friction-log.md)
- [Product Contract](../product-contract.md)
- [Backlog Priority](../backlog-priority.md)
- [DR-006 Owner Decision](dr-006-owner-decision-2026-06-22.md)
- [Compliance Matrix (AGENTS.md)](../retrospective/05-compliance-matrix.md)
