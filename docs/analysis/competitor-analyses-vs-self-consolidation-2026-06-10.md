# Competitor Analyses vs. Self — Consolidation
# 2026-06-10

> **Claim class:** Dated evidence package (self-state verified at HEAD
> `8fcd781` on 2026-06-10; **competitor facts NOT re-verified today** — they
> carry the date of their source document and must be refreshed per the
> [Competitive Claim Audit](competitive-claim-audit-2026-06-06.md) before any
> external use).
>
> **Purpose:** every prior competitor-facing analysis in this repo, compared
> against TeaAgent's *current* state, in one place — so the next strategy
> decision reads one document instead of fourteen.

---

## Input Corpus (all prior competitor-facing analyses)

| Date | Document | What it contributed |
| --- | --- | --- |
| 05-31 | [Agent Competitive Risks](agent-competitive-risks-2026-05-31.md) | First risk framing vs market |
| 05-31 | [Agent Market UX Survey](agent-market-ux-survey-2026-05-31.md) | UX pattern baseline across tools |
| 05-31 | [Competitor Community Feedback Synthesis](competitor-community-feedback-synthesis-2026-05-31.md) | What users complain about elsewhere |
| 06-01 | [Competitive Feedback Refresh](competitive-feedback-refresh-2026-06-01.md) | Updated complaint patterns |
| 06-01 | [Daily-Driver Popular Agent Feedback Survey](daily-driver-popular-agent-feedback-survey-2026-06-01.md) | Daily-driver expectations |
| 06-01 | [Daily-Driver Agent Market Source Map](daily-driver-agent-market-source-map-2026-06-01.md) | Source provenance map |
| 06-04 | [Competitor Signal Survey](competitor-signal-survey-2026-06-04.md) | Signal snapshot |
| 06-05 | [Seven Control Loops Competitor Survey](seven-control-loops-competitor-survey-2026-06-05.md) | Control-loop comparison frame |
| 06-05 | [Community Agent Pain Points Survey](community-agent-pain-points-survey-2026-06-05.md) | Pain-point overlay |
| 06-06 | [Competitor Signal Survey](competitor-signal-survey-2026-06-06.md) | Refreshed signals |
| 06-06 | [Competitor Self-Comparison Matrix](competitor-self-comparison-matrix-2026-06-06.md) | Source-backed 13-competitor matrix (the structural backbone reused below) |
| 06-06 | [Competitive Claim Audit](competitive-claim-audit-2026-06-06.md) | Claim hygiene rules |
| 06-06 | [Competitive Landscape and Positioning](competitive-landscape-and-positioning-2026-06-06.md) + [strategy version](../strategy/competitive-analysis-and-positioning-2026-06-06.md) | Strategic synthesis |
| 06-07 | [Competitor Chunking Audit](../research/competitor-chunking-audit-2026-06-07.md), [Segment-Aware Strategy Synthesis](../research/segment-aware-strategy-synthesis-2026-06-07.md) (+2 companions) | Long-context/chunking comparison; segment positioning |

**Convergent message of the corpus** (stable across all six dates): the market
is converging on remote/cloud async agents, IDE-native UX, plan/spec-first
workflows, subagents, hooks, MCP, permissions, and PR workflows. TeaAgent's
only defensible lane is **governed, auditable, provider-agnostic, local-first
agent work** — and the corpus repeatedly warns that governance must become
*visible and useful*, not just implemented.

---

## Axis-by-Axis: Market Benchmark vs TeaAgent THEN (06-06) vs TeaAgent NOW (06-10)

| Axis | Benchmark setters (per corpus, dated) | TeaAgent at 06-06 | TeaAgent at 06-10 (verified) | Gap trend |
| --- | --- | --- | --- | --- |
| Governance, audit, compliance | Codex compliance API; Devin enterprise logs | Strong internals, weak visibility | **Stronger and more visible:** receipts wired, A2/A3 mutation+permission gates, tenant-aware audit partitioning, multisig replay guards | **Widening lead** (TeaAgent's lane) |
| Cost discipline | Devin ACU hard caps; usage dashboards elsewhere | Hard caps, estimation gaps, redaction bugs | Caps + honest token metrics + per-tenant attribution scaffolding | Improving |
| Plan/spec before write | Cline Plan/Act; Kiro specs | Enforcement strong, receipts weak | Enforcement + plan receipts + spec quality gate (A1) | Narrowing |
| Local subagent safety | OpenCode/Claude Code permissions | Shared-default isolation, no batch timeout | Worktree-default isolation, batch deadline, permission capping, durable queue interface | Narrowing |
| Remote/cloud async agents | Codex, Copilot, Cursor background agents, Devin, Jules | Not supported (non-goals doc) | **Still not supported** — abstraction landed, no transport, no identity (see [remote refresh](remote-multi-agent-readiness-refresh-2026-06-10.md)) | **Unchanged; market keeps moving** |
| IDE/PR-native workflow | Cursor, Copilot, Cline, Windsurf | CLI/TUI only; VS Code stub | Unchanged in this delta | **Unchanged; largest adoption gap** |
| Team operations / RBAC | Devin enterprise controls; Copilot org policies | Absent | Components exist (RBAC, policy engine, consensus) but **unwired — claimable as nothing yet** | Nominally narrowing, actually unchanged |
| Eval/release gating | No competitor in the corpus exposes user-facing eval gates | Absent | H5 components exist (eval suite, prompt regression, repo-map benchmark, release gate) but unwired into CI | **Potential differentiator if wired** — corpus shows no benchmark setter here |
| Packaging/distribution | Codex/Copilot bundled distribution; Cursor installer | pip/source only | `update/` package (installer, delta, changelog) exists, unwired; no signed artifact | Nominally narrowing |
| Conversational simplicity | Jules "experimental but simple"; Claude Code onboarding | Heavy ceremony | Ceremony unchanged; governance vocabulary increased (see [UX refresh](conversation-experience-refresh-2026-06-10.md)) | **Mildly worsening** |
| Long-context/chunking | Per 06-07 research: context-window management productized by leaders | Context health checks partial | `context_health.py` extended (H5), long-session tests planned | Narrowing on paper |

---

## The Honest Scoreboard

**Where TeaAgent now genuinely leads (defensible with evidence at HEAD):**

1. **Auditability:** hash-chained, HMAC-keyed, export-hardened, tenant-
   partitioned audit with mutation-tested trust modules. No tool in the corpus
   matches this depth in an open, local-first package.
2. **Approval rigor:** numbered selectors, scope-exact authority receipts,
   multisig templates, replay guards, JIT timeout defaults.
3. **Claim hygiene as a practice:** do-not-claim list, dated evidence
   packages, claim-class headers — itself a differentiator for
   trust-sensitive adopters, and unique in the surveyed market.

**Where the corpus says TeaAgent loses and HEAD does not change the answer:**

1. Hosted/remote async delegation (Codex/Cursor/Copilot class).
2. IDE-native daily ergonomics (Cursor/Cline/Windsurf class).
3. Zero-config onboarding (Jules/Codex class).
4. Distribution surface (GitHub-native entry points, Slack/Teams handoffs).

**Where the corpus is now stale and must not be quoted without refresh:**

- Roo Code shutdown status (was "shutdown May 15, 2026" — verify before reuse).
- Any pricing, plan, model name, star count, or availability claim in the
  05-31 through 06-07 documents.
- Devin/Kiro/Jules feature sets — these were moving monthly as of the matrix
  snapshot.

---

## Strategic Readout (inference, not evidence)

1. **The lane is confirmed and deepening.** Four consecutive review cycles
   (05-31, 06-01, 06-06, 06-10) reach the same conclusion from different
   angles; this consolidation makes it the *fifth*. The marginal value of
   another competitor survey is now near zero. The binding constraint is not
   market understanding — it is converting two specific gaps (visible
   simplicity; one remote-capable workflow) into shipped product.
2. **The eval-gate axis is the only axis where TeaAgent could set the
   benchmark rather than chase one.** No corpus competitor exposes
   user-auditable eval gating of agent behavior. The H5 components exist;
   wiring them into a public release profile would create a claim nobody else
   in the matrix can copy quickly — and it is honest, unlike a premature
   team-ops claim.
3. **The biggest competitive risk is internal:** unwired components plus
   stale status docs reproduce, at project scale, exactly the "trust gap"
   the corpus says users punish competitors for. A project whose product *is*
   trustworthiness cannot afford doc⇄reality drift; it converts a marketing
   weakness into a thesis refutation.

---

## Maintenance Rule

This document supersedes no source; it consolidates them. When the next
competitor refresh happens (per WS6-003, quarterly or pre-publication), update
the axis table's *benchmark* column from fresh sources and the *NOW* column
from a fresh HEAD verification, and add a new dated row to the input corpus.
