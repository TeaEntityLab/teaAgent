# System Critical Review Package — TeaAgent
# 2026-06-10

> **Status:** Current dated evidence package.
> **Scope:** TeaAgent at commit `8fcd781` (HEAD on 2026-06-10). Competitor
> facts are consolidated from dated prior sources and were **not** re-verified
> on 2026-06-10.
> **Refreshes:** the [2026-06-06 package](system-critical-review-2026-06-06-INDEX.md)
> (anchored `ad5e2d7`; delta to this anchor: 81 commits, ~75k insertions).
> **Audience:** maintainers, product/engineering leads, security reviewers,
> and future agents deciding where to focus.
>
> This package records public reasoning summaries and evidence, not private
> chain-of-thought. Each conclusion is direct evidence, a bounded inference,
> or an open unknown — see the reasoning ledger for per-claim classification.

---

## Package Contents

| Document | Role | Primary question |
| --- | --- | --- |
| [Engineering Architecture Critique Refresh](engineering-critique-refresh-2026-06-10.md) | Code-grounded delta review | What did 81 commits actually change about maintainability and integrity? |
| [Remote Multi-Agent Readiness Refresh](remote-multi-agent-readiness-refresh-2026-06-10.md) | Non-goals re-scoring | Did any remote/multi-agent claim become safe to make? |
| [General-User Conversation Experience Refresh](conversation-experience-refresh-2026-06-10.md) | Daily-driver UX review | Would an ordinary developer now understand and enjoy the conversation loop? |
| [Competitor Analyses vs Self Consolidation](competitor-analyses-vs-self-consolidation-2026-06-10.md) | 14-document market synthesis vs verified HEAD | Where does TeaAgent actually stand on every axis the corpus measured? |
| [System Review Reasoning Ledger](system-review-reasoning-ledger-2026-06-10.md) | Public reasoning record | What was asked, what answered it, what remains unknown? |
| [Work Direction Decomposition](../plans/work-direction-decomposition-2026-06-10.md) | Execution backlog (WD-A … WD-H) | What should be done next, in what order, with what gates? |
| [Work Direction Execution Index](../plans/work-direction-execution-index-2026-06-10.md) | Sprint calendar + S1 ticket plans | What is scheduled this week, and what is the critical path? |

---

## Executive Verdict

The 06-06 backlog worked: receipts, approval selectors, isolation defaults,
batch timeouts, durable-queue interface, audit-integrity P0s, and the TUI
decomposition all verifiably closed. The project's recurring failure mode then
reproduced at larger scale: a ~12,000-line H4/H5/H6 component drop whose
governance (RBAC, policy engine, consensus) and eval (eval suite, release
gate) clusters are imported by **no production code path**, while the
canonical roadmap simultaneously calls those horizons Pending and the commit
log calls them implemented. TeaAgent's product thesis is provable
trustworthiness; its main competitive risk is now internal doc⇄reality drift,
not any competitor. The decomposed work directions therefore put truth
automation (wire-or-quarantine validator, status-claim gates, suite tiering)
ahead of any new capability.

---

## Verification Evidence (run on 2026-06-10, Python 3.12.8)

| Check | Result |
| --- | --- |
| H4/H5/H6 + tenant-isolation test subset (18 files) | **296 passed** in 12.4 s |
| Acceptance + regression tiers | **628 passed** (+11 subtests) in 51.3 s |
| Full suite | **Unverifiable in this environment:** two attempts were killed by SIGXCPU (CPU-time limit, exit 152) at ~50% progress with zero failures observed up to the kill point. The roadmap's "4,758 tests pass" claim (06-07) is therefore neither confirmed nor contradicted at HEAD. Tracked as WDG-001/002 |
| `scripts/validate_docs_consistency.py` | Pass after package registration (generated inventories refreshed) |
| Import-graph wiring check on new modules | H4 governance and H5 eval clusters unwired; cockpit data source is the only wired H4 surface |

---

## Findings Roll-Up

| ID | Severity | Finding | Owning doc |
| --- | --- | --- | --- |
| ENG-R1 | High | H4/H5 component clusters implemented but unwired; 291 new tests verify islands | Engineering refresh |
| ENG-R2 | High | Canonical roadmap contradicts commit log (H2–H6 status); merge gate cannot see doc-vs-code drift | Engineering refresh |
| ENG-R3 | Medium | Root-module sprawl: 183 top-level modules; new code bypassed existing packages | Engineering refresh |
| ENG-R4 | Medium | Change velocity exceeds review/gating capacity; no "wired or labeled" gate exists | Engineering refresh |
| ENG-R5 / WDG | P0 work | Suite outgrew constrained environments; killed by SIGXCPU at ~50%; no smoke tier | Engineering refresh + work directions |
| MA-R* | — | 4 of 9 remote non-goal rows closed; all remote-gating rows (identity, federation, remote orchestration) still open; non-goals doc remains binding | Multi-agent refresh |
| MA-R-T | Medium | Tenant partitioning is data separation, not inter-tenant security; claim guidance recorded | Multi-agent refresh |
| UX-R1 | High | Register mismatch: governance vocabulary saturates the daily conversational path | UX refresh |
| UX-R2/R4 | Medium | Operator persona out-invested the general-user persona; first-run ceremony unchanged | UX refresh |
| COMP-1 | — | Market lane confirmed a fifth time; further competitor surveys near-zero marginal value | Consolidation |
| COMP-2 | Opportunity | Eval gating is the only axis where TeaAgent can set the benchmark; H5 components exist, wiring is the missing step | Consolidation |

---

## Recommended Read Order

1. This index.
2. [Engineering refresh](engineering-critique-refresh-2026-06-10.md) — the central ENG-R1/R2 findings.
3. [Work Direction Decomposition](../plans/work-direction-decomposition-2026-06-10.md) — the execution queue (WD-A truth pass first).
4. [Competitor consolidation](competitor-analyses-vs-self-consolidation-2026-06-10.md) — before any positioning or roadmap debate.
5. [Multi-agent refresh](remote-multi-agent-readiness-refresh-2026-06-10.md) and [UX refresh](conversation-experience-refresh-2026-06-10.md) — per-angle depth.
6. [Reasoning ledger](system-review-reasoning-ledger-2026-06-10.md) — when you need to know *why* a conclusion was reached or what would overturn it.

---

## Maintenance Rules

- Dated snapshot, not timeless truth; re-anchor on the next significant delta.
- Competitor facts must be same-day refreshed before external use
  ([Competitive Claim Audit](competitive-claim-audit-2026-06-06.md) rules apply).
- When a WD item lands, link its validating test back to the finding row here.
- Supersede with a note, never delete the evidence trail.
