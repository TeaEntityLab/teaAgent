# Remote Multi-Agent Readiness — Refresh
# 2026-06-10

> **Claim class:** Dated evidence package.
> **Anchor:** TeaAgent at commit `8fcd781` (HEAD on 2026-06-10).
> **Refreshes:** [Multi-Agent Coordination Critique (2026-06-06)](multi-agent-coordination-critique-2026-06-06.md).
> **Companion:** [Remote Multi-Agent Non-Goals (2026-06-06)](../strategy/remote-multi-agent-non-goals-2026-06-06.md) — the authoritative list of claims TeaAgent does **not** make. This refresh re-scores each non-goal row against HEAD.

---

## Verdict

TeaAgent moved from "local subagents are unsafe by default" to "local subagents
are bounded by default" — isolation, batch timeout, permission capping, and a
durable approval-backend interface all landed. Tenant-level path partitioning
adds a real second axis of separation. **The remote multi-agent posture is
unchanged: not supported, and the non-goals doc should stay in force.** The new
H4 collaboration components (RBAC, policy routing, consensus validation) look
like the missing team-operations layer on paper, but none of them touch the
live execution path yet, so they change the roadmap, not the readiness.

---

## Non-Goals Table Re-Scored Against HEAD

| Non-goal (06-06) | Re-enable gate | Status at `8fcd781` | Evidence / note |
| --- | --- | --- | --- |
| Cryptographic peer identity | Ed25519 agent identity + signed approvals | **Still open.** Ed25519 use exists in `tsb_format.py` and `memory/pinned_file.py` (artifact/memory signing), but `agent_id` remains an unsigned string; approvals are not agent-signed. | Import grep; no identity module |
| Remote approval orchestration | Durable coordination abstraction (WS2-005) | **Partially advanced.** `coordination/approval_backend.py` defines file-backed durability with snapshot recovery and a named `remote` backend constant — the abstraction exists, the remote implementation does not. | Module at HEAD |
| Federated trust by URL/name alone | Certificate-backed MCP trust policy | **Still open.** MCP trust remains operator-config anchored. | No PKI layer found |
| Prompt-injection detection | SEC-NEW2 detector module | **Still open.** Approval gates remain the only boundary. | — |
| Behavioral contracts at run start | SEC-NEW3 signed pre-run contract | **Still open.** Plan/spec receipts exist but are not signed contracts. | — |
| Shared workspace as silent subagent default | WS2-001 explicit isolation default | **Closed.** Shared now requires explicit argument; worktree default on git workspaces; non-git fallback warns. | `subagents/_isolation.py:26-60` |
| Unbounded subagent batches | WS2-002 batch deadline | **Closed.** 300 s default batch timeout. | `subagents/_isolation.py:19` |
| Child budget inheritance | WS2-003 envelope propagation | **Largely closed.** Tier 0/1 hardening (`0f30750`) added budget envelope work; child permission modes are inherited and capped at `MAX_CHILD_PERMISSION`. Residual: verify cost-budget (cents) inheritance has a named acceptance test before flipping this row. | `subagents/_manager.py:130-152`; commit `0f30750` |
| Depth/concurrency bypass | WS2-004 global depth controls | **Needs verification.** Not re-verified in this pass; treat as open until a test is cited. | — |

**Rule consequence:** 4 of 9 rows closed or largely closed, 5 still open —
including all three that gate *remote* (identity, federation, remote
orchestration). The documentation rule ("no enterprise/WAN-ready/federated
language until every row is supported") **remains binding**.

---

## What the Tenant Isolation Work Actually Buys (and Doesn't)

Commit `4e0a9e9` added path partitioning under `.teaagent/tenants/{tenant_id}/`,
cross-tenant path checks in `ApprovalManager`, and `tenant_id` propagation
through audit, run store, background runs, and the gateway base.

- **Buys:** an honest data-separation story for a single trusted operator
  running work on behalf of multiple tenants/workspaces; per-tenant cost
  attribution and audit trails become structurally possible (H4-004
  prerequisite).
- **Does not buy:** security isolation between mutually distrusting tenants.
  Everything still runs in one process with one OS user; `tenant_id` is a
  string, not a principal. A malicious tool or injected prompt in tenant A's
  run is not contained from tenant B's files by anything stronger than path
  checks in `ApprovalManager`.
- **Claim guidance:** "tenant-aware partitioning" is safe to say.
  "Multi-tenant isolation" is not, without a process/container boundary.

---

## The H4 Collaboration Cluster: Right Shape, Zero Authority

`rbac.py` (639 lines), `policy_engine.py` (513), `policy_routing.py` (438), and
`consensus_validation.py` (626) implement role-based access, policy evaluation,
role-aware routing, and multi-agent consensus patterns — exactly the H4-002
requirement list. But (see
[Engineering Refresh ENG-R1](engineering-critique-refresh-2026-06-10.md)) no
runner, approval, or subagent code imports them. Until wired:

- "Agents respect role boundaries" (H4-002 acceptance) is **not met** — no
  agent action passes through RBAC.
- Consensus-for-destructive-actions is **not met** — destructive actions are
  gated by the existing approval queue only.
- Any team-operations claim derived from these modules would be claim-hygiene
  violation per `docs/governance/do-not-claim.md`.

The wiring order that minimizes risk: policy engine behind the existing
approval path first (shadow mode — log decisions, enforce nothing), then RBAC
on subagent launch parameters, then consensus on the destructive-action gate.
Shadow-mode receipts would also produce the evidence needed to tune policies
before they can break daily use.

---

## Remote Scenario Walkthrough (Thought Experiment, Re-Run)

The 06-06 critique asked: *what breaks if two operators on two machines share
work?* Re-answered at HEAD:

1. **Task handoff** — improved: durable run state, background run lifecycle,
   and resume parity (`ac6b318`, `0f30750`) mean a run can be suspended on one
   machine and inspected from its artifacts. Still no transport: handoff is
   "copy the `.teaagent` directory or share the filesystem."
2. **Approval from a second machine** — the backend abstraction now names a
   `remote` mode, but nothing implements it; approvals remain local-file
   authoritative. Multi-sig templates (`templates/multi-sig/`) and replay
   guards (`0f30750`) prepare for this but don't deliver it.
3. **Identity and authority** — unchanged: any process that can write the
   queue file can approve. This is the hard gate for anything remote.
4. **Conflict** — two writers on one workspace are now *less* likely to
   collide silently thanks to worktree-default isolation, but there is no
   lease/lock concept for a workspace claimed by another agent.

Conclusion unchanged from 06-06, with sharper boundaries: TeaAgent is a
**single-operator, multi-agent, multi-tenant-data** system. It is not yet a
multi-operator or multi-machine system, and the fastest credible path there is
the `remote` approval backend + signed approvals, not more orchestration
features.

---

## Recommendations (feed into work directions)

1. Re-score the non-goals table in the strategy doc itself (it still shows all
   rows open); closed rows should cite their acceptance tests. Keep the doc's
   binding rule.
2. Add the missing acceptance citations for WS2-003 (cost-cents inheritance)
   and WS2-004 (depth/concurrency bypass) — or reopen those rows.
3. Wire the H4 policy cluster in **shadow mode** before any enforcement claim.
4. Define the remote approval backend as the single next remote-facing
   investment; explicitly defer federation/PKI until it exists.
5. Keep marketing language at "local-first governed multi-agent harness with
   tenant-aware partitioning."
