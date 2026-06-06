# Competitive Landscape and Positioning — TeaAgent
# 2026-06-06

> **Claim class:** Dated strategic synthesis.
>
> **Supersession note, 2026-06-06:** For current reusable competitor claims, use
> [Competitor Self-Comparison Matrix](competitor-self-comparison-matrix-2026-06-06.md)
> and [Competitive Claim Audit](competitive-claim-audit-2026-06-06.md). This file
> remains useful for strategic reasoning, anti-personas, and opportunity framing,
> but any exact star counts, pricing labels, plan details, model names, hosted
> availability, or adoption rankings below are historical unless refreshed from
> official/upstream sources on the same day.

> **2026-06-06 source note:** This file is a strategic synthesis. For the
> source-backed competitor-by-competitor comparison and refreshed official-doc
> source map, use
> [Competitor Self-Comparison Matrix](competitor-self-comparison-matrix-2026-06-06.md).
> Avoid reusing volatile star counts, pricing, model availability, or adoption
> claims from this file without a same-day refresh.

> **Purpose:** Honest, evidence-grounded positioning assessment for TeaAgent against
> the AI coding-agent market as of June 2026. Separates confirmed strengths from
> aspirational claims. Designed to inform go-to-market decisions, roadmap triage,
> and resource allocation.
>
> **Sources:** `docs/analysis/competitor-signal-survey-2026-06-04.md`,
> `docs/analysis/seven-control-loops-competitor-survey-2026-06-05.md`,
> `docs/analysis/community-agent-pain-points-survey-2026-06-05.md`,
> `docs/analysis/agent-competitive-risks-2026-05-31.md`, official product docs for
> all listed competitors, and the TeaAgent codebase at HEAD (ad5e2d7).

---

## 1. Competitive Set

### Tier 1 — Direct Competitors (same primary market: developer terminal agents)

| Agent | Backer | Model | Stars | Primary surface | Default safety | Pricing model |
|---|---|---|---|---|---|---|
| **Claude Code** | Anthropic | Claude 3.x/4.x | N/A (hosted) | Terminal CLI + IDE extensions | HITL approval, permission modes | Usage subscription |
| **OpenCode** | Open source | Any | 164K | Terminal TUI + IDE + desktop | Explicit per-agent permissions | Free (OSS) |
| **Aider** | Open source | Any (API key) | ~28K | Terminal CLI | Git-commit-per-change, manual | Free (OSS) |
| **Pi.dev** | Earendil | Any | ~12K | Terminal CLI | Extension-fragmented, opt-in only | Free (OSS) |
| **Cline** | Open source | Any | ~30K | VS Code extension | Plan/Act mode, approve each tool | Free (OSS) |
| **Roo Code** | Open source | Any | ~24K | VS Code extension | Cline fork; improved approvals | Free (OSS) |

### Tier 2 — Adjacent Competitors (different surface, overlapping use cases)

| Agent | Backer | Primary surface | Primary differentiator |
|---|---|---|---|
| **GitHub Copilot** | Microsoft/GitHub | IDE extension + GitHub.com | Ubiquitous, deeply integrated into GitHub PRs/CI |
| **Cursor** | Cursor Inc | IDE (VS Code fork) | Inline diff UX, fast agent mode |
| **Windsurf** | Codeium | IDE | Cascade agentic flow, beginner-friendly |
| **Kiro (AWS)** | Amazon | IDE + cloud | Spec-driven development, steering docs, cloud-native |
| **Devin** | Cognition | Web dashboard | Full task delegation, cloud sandbox |
| **OpenHands** | All-Hands AI | Web + local | Docker sandbox, safety-first open source |

### Tier 3 — Orchestration Frameworks (foundational, not daily-driver agents)

| Framework | Backer | Use case | Threat relevance |
|---|---|---|---|
| **CrewAI** | Open source | Multi-agent role orchestration | Low — no tool governance |
| **LangGraph** | LangChain Inc | Graph-based multi-agent workflows | Low — framework, not harness |
| **AutoGPT** | Significant Gravitas | Autonomous general agent | Low — degraded community; no daily-driver footprint |
| **OpenHands** | All-Hands AI | Production agent deployment | Medium — has Docker safety model |
| **OpenAI Codex** | OpenAI | Command-center multi-agent | Medium — cloud-first, worktrees, automations |

---

## 2. Feature Matrix

A `✅` means shipped and tested. `⚠️` means present but rough or Beta. `❌` means absent. `🔲` means planned but not shipped.

| Feature | TeaAgent | Claude Code | OpenCode | Aider | Cline/Roo | GitHub Copilot | Kiro |
|---|---|---|---|---|---|---|---|
| **LLM provider support** | ✅ multi-adapter (OpenAI, Anthropic, OpenRouter, custom) | ❌ Claude only | ✅ multi | ✅ multi | ✅ multi | ❌ GPT-5 family only | ❌ Bedrock/Anthropic |
| **CLI surface** | ✅ full CLI | ✅ full CLI | ✅ | ✅ | ❌ IDE only | ❌ IDE only | ⚠️ IDE only |
| **REPL/interactive chat** | ✅ `teaagent chat` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **TUI (terminal UI)** | ✅ `teaagent tui` | ❌ | ✅ Rust/Tauri | ❌ | ❌ | ❌ | ❌ |
| **Web UI / dashboard** | ⚠️ `audit serve` HTML viewer | ❌ | ❌ | ❌ | ❌ | ✅ GitHub.com | ❌ |
| **IDE integration** | ✅ VS Code MCP extension | ✅ deep (Zed, VS Code, JetBrains) | ✅ | ⚠️ partial | ✅ VS Code | ✅ all IDEs | ✅ |
| **Permission modes (granular)** | ✅ 5 modes (read-only→danger) | ✅ approvals | ⚠️ per-agent | ❌ | ⚠️ Plan/Act | ❌ | ⚠️ |
| **Tool-level approval workflow** | ✅ ApprovalPolicy + JIT TTY | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Audit trail (hash-chained JSONL)** | ✅ L0–L3 tiered, SHA-256 | ❌ chat history only | ❌ | ❌ git log | ❌ | ❌ | ❌ |
| **Cost cap / budget enforcement** | ✅ hard `--max-estimated-cost-cents` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Cost tracking (per-run)** | ✅ per-run cost in audit | ⚠️ session total | ❌ | ✅ partial | ❌ | ❌ | ❌ |
| **Undo (surgical)** | ✅ `teaagent undo --last`, UndoJournal | ✅ | ❌ | ✅ git reset | ❌ | ❌ | ❌ |
| **Plan-before-write enforcement** | ✅ `--require-plan`, PlanContract | ✅ spec mode | ✅ Plan mode | ❌ | ✅ Plan mode | ❌ | ✅ spec-first |
| **Multi-agent / swarm** | ✅ Beta (SwarmManager, tournament) | ✅ subagents | ✅ parallel sessions | ❌ | ❌ | ✅ GitHub Actions | ❌ |
| **Consensus / multi-sig approvals** | ✅ Beta (ConsensusEngine, SSH vote relay) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Federated peer agents (A2A)** | ✅ Beta (A2ADispatcher, FederatedAgentRegistry) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MCP server (expose tools)** | ✅ `teaagent mcp serve` | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **Plugin/skill extension** | ✅ tool-authoring, skills, WASM | ✅ rich | ✅ | ❌ | ❌ | ✅ | ✅ steering docs |
| **LSP code analysis** | ✅ Beta (tree-sitter, `code_analysis_lsp`) | ✅ | ✅ | ⚠️ | ❌ | ✅ | ⚠️ |
| **Sandbox execution** | ✅ Beta (Docker `prepare_subagent_isolation`, gVisor, WASM) | ⚠️ | ❌ | ❌ | ❌ | ✅ (Actions) | ❌ |
| **Declarative subagent defs (.md)** | ✅ (matches Claude Code AGENTS.md convention) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Compliance audit exporter** | ✅ Beta (signed JSON bundle, chain verify) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OpenAPI schema from tool registry** | ✅ `workspace openapi` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Memory catalog (cross-session)** | ✅ `MemoryCatalog`, pinned files, TTL | ✅ CLAUDE.md | ✅ | ⚠️ | ❌ | ❌ | ✅ steering docs |
| **Operator deployment guide** | ✅ `agent-mode-operator-guide.md` | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Hosted/cloud version** | ❌ (`managed_runtime` stub only) | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Team collaboration features** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **SOC 2 / compliance certification** | ❌ (whitepaper doc only) | ✅ (Anthropic) | ❌ | ❌ | ❌ | ✅ | ✅ AWS |
| **Community adoption signals** | Early (internal only) | Very high | Very high (164K stars) | High (~28K stars) | High (~30K stars) | Very high | Growing |

---

## 3. Positioning Assessment

### What TeaAgent does better than every direct competitor

**1. Governance depth as a first-class system — not an afterthought.**

TeaAgent is the only open-source agent harness that ships a complete 5-loop governance system as a core product invariant:
- **Tool governance** — ToolRegistry with security-tier annotations, static AST linting, capability manifests
- **Coding safety** — PlanContract file-target validation, strict plan-before-write, rollback on validation failure
- **Audit replay** — tiered L0–L3 JSONL audit with SHA-256 hash-chain integrity, `runs trace/export/replay`
- **Memory hygiene** — TTL-expiring failure cards, auto-invalidation rules, confidence-based blocking
- **Swarm hardening** — approval lineage tracing, fail-fast tournament, git worktree isolation

No competitor (as of June 2026) ships all five loops as integrated, tested, reviewable primitives. Claude Code has strong approval UX but no audit replay or swarm consensus. OpenCode has parallel sessions but no permission matrix or audit chain.

**2. Hard cost caps (only agent with enforced spending limits)**

`--max-estimated-cost-cents` is a hard block, not a UI warning. Competitors either show a running total (Claude Code's session cost) or nothing. The "Claude Is Dead" thread (841 upvotes, August 2025) represents exactly the trust failure TeaAgent's budget model prevents. No other open-source agent ships this.

**3. Multi-provider flexibility with governance preserved**

Provider adapters (OpenAI, Anthropic, OpenRouter, extensible) let users route to any model without losing the governance layer. Claude Code locks to Claude; GitHub Copilot locks to GPT-5 family; Kiro locks to Bedrock. For cost-sensitive or model-agnostic teams, TeaAgent is the only governed harness that doesn't impose a provider.

**4. Hash-chained audit trail (compliance-grade)**

The `AuditLogger` with SHA-256 chain verification and signed export bundle is a feature that doesn't exist in any direct competitor. This is the technical foundation for SOC 2 artifacts, NIST AI agent compliance, and regulated-industry deployment. No other terminal agent has it.

**5. Plan-before-write as a safety invariant (not a mode)**

`workspace-write` requires a plan by default. This is not a UI prompt — it is an enforcement gate that prevents unreviewed writes. Competitors (Cline, OpenCode) have a Plan/Act separation, but it is a workflow choice, not an enforced invariant with file-target validation and rollback.

### Where TeaAgent is behind

**1. Community visibility and adoption** — OpenCode has 164K GitHub stars. Aider has ~28K. TeaAgent is internal only. This is the largest gap. The technical differentiation is real; the market does not know it yet.

**2. IDE-first UX** — Cursor, Windsurf, Cline, Copilot, and Kiro are IDE-native. The majority of developers live in an editor, not a terminal. TeaAgent's VS Code MCP extension exists but is not the primary onboarding path.

**3. No hosted/cloud version** — `managed_runtime` is a stub. Devin ($500/mo), GitHub Copilot Workspace, and Kiro are cloud-first. TeaAgent is local-only today.

**4. No team collaboration features** — All work is single-operator. Shared approval queues, PR-linked workflows, and team audit dashboards do not exist.

**5. Docs-to-reality drift** — The project has a recurring documentation honesty problem (identified in `total-review-2026-06-04`). Some features in docs are Beta-labeled code without production hardening. This is manageable internally; it becomes a trust liability when exposed to external evaluators or buyers.

---

## 4. Market Positioning

### Who TeaAgent is for (primary personas)

**Persona A — Security-Conscious Engineering Lead (Best fit)**
- Team of 5–20 engineers at a startup handling sensitive data (fintech, health tech, infosec tooling)
- CTO is tired of engineers running `--yolo` Cursor agents on production-adjacent code
- Needs: per-run audit, budget caps, approval workflows, undo, and something they can show to a CISO
- Pain solved: TeaAgent is the only agent that gives them a governance paper trail without building it themselves

**Persona B — DevOps / Platform Engineering (Good fit)**
- Running agents headlessly in CI/CD pipelines
- Needs: CLI-first, scriptable, permission modes, predictable spend, provider flexibility
- Pain solved: TeaAgent's `read-only` mode + budget cap + audit export is production-safe in a way that most agents are not

**Persona C — Compliance-Heavy Organization (Enterprise target, pre-revenue)**
- Financial services, healthcare, government contractors
- Needs: SOC 2 artifacts, audit trail, data-never-leaves-local guarantees, operator deployment guide
- Pain solved: Audit chain + tiered logging + compliance audit exporter is the right architecture; missing SOC 2 certification and tenant isolation hardening to close the deal

**Persona D — Power Developer (Current adopter, not the primary TAM)**
- Wants governance but also wants speed; runs multiple agents in tournament mode; values extensibility
- Pain solved: TeaAgent's WASM skill extension, SwarmManager, and multi-provider support are unique
- Risk: This user will migrate to OpenCode if OpenCode adds a permission matrix

### Who TeaAgent is NOT for (honest anti-personas)

- Developers who want instant code completion (Copilot/Cursor own this)
- Beginners who want a plug-and-play IDE experience (Windsurf/Cursor own this)
- Teams that want to "just fire an issue and forget it" (Devin owns this)
- Organizations needing a cloud-hosted multi-tenant platform today (nothing to offer yet)

---

## 5. Strategic Gaps — Prioritized

| Gap | Severity | Competitive pressure | Effort to close | Owner |
|---|---|---|---|---|
| **G1: No external community / visibility** | Critical | OpenCode/Aider already own mindshare | Medium (docs, talks, README polish) | Marketing/DevRel |
| **G2: No hosted or SaaS version** | High | Devin, Kiro, Copilot Workspace are cloud-first | Large (6–12 months) | Product/Infra |
| **G3: SOC 2 / compliance certification** | High | Required for enterprise buyers; Anthropic/Microsoft have it | Large (12–18 months) | Security/Legal |
| **G4: IDE-native experience** | High | Cursor/Copilot/Cline own developer daily-driver mindshare | Large (new surface) | Engineering |
| **G5: Team collaboration (shared approvals, team audit)** | High | Copilot/Kiro have team workflows | Medium | Product/Engineering |
| **G6: Docs-to-reality CI enforcement** | Medium | Internal credibility problem before external trust problem | Small (FO-1 task) | Engineering |
| **G7: Security whitepaper for enterprise evaluation** | Medium | Enterprise evaluators need a formal document | Small (write, not build) | Security/Technical Writing |
| **G8: Budget UX (show burn proactively, not at exhaustion)** | Medium | Claude Code's cap failure is the industry's most-cited trust collapse | Small (CR-1 task) | Engineering |
| **G9: Tournament/swarm UI for multi-agent workflows** | Low | Codex has a multi-agent command center; TeaAgent's is CLI-only | Medium | Engineering |
| **G10: WASM skill signing and org-wide CI integration** | Low | Niche power-user need | Medium | Engineering |

### G1 is the highest-leverage gap — technical differentiation without market awareness is zero go-to-market.

---

## 6. Threat Matrix

### T1 — OpenCode (Highest near-term threat)

**Why:** 164K GitHub stars, MIT license, multi-provider, LSP-aware, multi-session, multi-surface (terminal + IDE + desktop). Growing extremely fast. Community energy is high. If OpenCode ships a permission matrix and audit chain in the next 6 months, TeaAgent's primary CLI differentiator is gone.

**What would happen:** Developer community defaults to OpenCode for its broader surface. TeaAgent's governance primitives are the moat, but the moat requires communication and documentation to be defensible.

**What it would take to win:** Ship faster in the governance layer (multi-sig, compliance exporter) before OpenCode copies it. Get external developers using the governance features so they create social proof. A blog post titled "What OpenCode's permission model is missing" would cost nothing and reach the right audience.

### T2 — Claude Code (Highest adoption pressure, medium technical threat)

**Why:** Anthropic has brand trust, a world-class model, and is rapidly adding features (skills, subagents, hooks, tasking). As Claude Code adds governance features (there is no announced roadmap to do so, but it's plausible), TeaAgent's differentiation in the Anthropic-using developer segment shrinks.

**Asymmetric advantage:** Claude Code is locked to Claude. TeaAgent's multi-provider support is a permanent differentiator as long as model plurality exists in the market.

**What it would take to win:** TeaAgent's governance layer should be explicitly positioned as the governance bridge over Claude Code — i.e., run TeaAgent on top of Claude Code's model while adding audit, cost caps, and strict approvals. This is not mutually exclusive with Claude Code; it's additive.

### T3 — Kiro / AWS (Enterprise threat, medium term)

**Why:** Spec-driven development, steering docs, cloud-native deployment, AWS backing, enterprise trust chain. If an enterprise evaluates Kiro and TeaAgent, Kiro wins on procurement and compliance without even comparing features.

**Why TeaAgent can still win:** Kiro is locked to AWS/Bedrock. TeaAgent's audit chain and multi-provider support are better governance primitives for orgs that don't want cloud lock-in. The argument: "all your agent decisions, all your tool calls, all your cost — on-premises, auditable, hash-chained."

### T4 — GitHub Copilot (Indirect, enterprise silo risk)

**Why:** The GitHub distribution moat is enormous. Copilot is already in the enterprise procurement cycle. As Copilot adds autonomous agents and code review to GitHub Actions, the path of least resistance for many enterprises is "just use Copilot."

**TeaAgent response:** Copilot cannot run on-premises, cannot be multi-provider, and does not have a per-run audit chain. For regulated industries, TeaAgent's local-first design is a requirement, not a preference.

### T5 — Cursor / Windsurf (Developer daily-driver threat)

**Why:** IDE-native agents with inline diff UX win developer attention. Terminal agents lose mindshare to IDE agents when onboarding friction is high.

**Mitigation:** TeaAgent's VS Code extension is a legitimate answer here. The risk is that the extension is not the primary onboarding path today.

---

## 7. Differentiation Opportunities

### O1 — "Governance-as-a-Layer" positioning

TeaAgent can be the governance harness that wraps *any* agent, not just a standalone agent. The architecture already supports this (provider adapters, MCP server mode). Position TeaAgent as: "Run Claude Code tasks under TeaAgent governance — same model, same quality, now with audit trail and cost cap." This is a compelling enterprise message that avoids head-to-head with Claude Code's model quality.

### O2 — Compliance-First Open Source

No open-source agent has a compliance-grade audit trail. TeaAgent's L3 tiered audit, hash-chain integrity, and signed export bundle are unique. Position as the answer to: "We want to use AI agents in our fintech/health/government environment, but we need an audit trail we can produce in a vendor review." This is a TAM with budget. Competitors have not claimed it.

### O3 — The Budget Transparency Pioneer

The "Claude Is Dead" thread (841 upvotes) identified cost surprises as the #1 community rage trigger across all agents. TeaAgent's hard cost cap + proactive burn display is a unique feature that could generate significant organic awareness if marketed directly to that thread's audience. "The agent that never surprises your finance team."

### O4 — Multi-Provider Governance Hub

As model plurality increases (Claude, GPT-5, Gemini, Llama, local Ollama), the governance problem becomes *harder* across providers, not easier. TeaAgent as the provider-agnostic governance layer captures value regardless of which model wins the quality race. This is an infrastructure play, not a model play.

### O5 — Enterprise On-Premises Package

A hardened, one-command Docker Compose deployment of TeaAgent with control plane, audit viewer, approval queue UI, and tenant isolation would have no direct competitor at the $5K–$20K/year enterprise license tier. The architecture exists (control plane API, multi-tenant registry, OAuth 2.1/DPoP). The packaging and sales motion do not.

---

## 8. Critical Assessment — Where We May Be Delusional

### D1 — "Governance-first" may be a feature, not a market

The honest question: does the median developer want governance, or do they want speed? The 164K stars on OpenCode and the "just let it rip" threads on r/LocalLLaMA suggest the market's primary demand is velocity, not auditability.

The governance story resonates with **security teams, compliance leads, and DevOps engineers** who have been burned by ungoverned agent runs. It is a vertical story (regulated industries, enterprise security), not a horizontal story (every developer). If we treat it as horizontal, we will build a product no one uses. If we treat it as vertical, we have a fundable niche.

**Delusional version:** "Every developer will want governance once they see it."
**Realistic version:** "5–10% of the market actively needs governance. That's still a large TAM, but go-to-market must be vertical."

### D2 — Architecture depth ≠ market readiness

TeaAgent has 88 test files, 441 acceptance tests, a 5-loop governance system, WASM skills, OAuth 2.1/DPoP, SSH vote relay, and multi-tenant control plane. The engineering quality is real. But:

- External community adoption is zero.
- The docs have documented honesty problems (doc⇄reality drift).
- "Beta" labels on the maturity matrix cover a wide range from "almost stable" to "stub with tests."
- The `managed_runtime` is a protocol with provider stubs — not a deployed cloud service.

The risk: presenting TeaAgent's architecture as a competitive strength to a CISO without acknowledging external adoption signals produces a credibility problem when they do their own diligence.

**Delusional version:** "Our architecture is enterprise-ready."
**Realistic version:** "Our architecture is the right foundation for enterprise. We need 6–12 months of external usage, a security whitepaper, and at least one reference customer before the CISO conversation is winnable."

### D3 — Multi-provider may be table stakes, not a differentiator

Most open-source agents support multiple providers. In 6 months, any remaining single-provider agents will likely add multi-provider support. The moat from provider flexibility alone will not last. The real moat is governance depth + audit chain + compliance exporter — which no competitor is actively building.

### D4 — The TUI is a niche, not a beachhead

OpenCode has 164K stars. TeaAgent has a TUI too. The TUI is not the reason users choose TeaAgent; it is table stakes for a terminal-native agent. The differentiation must be governance, not interface.

### D5 — We are one OpenCode PR away from losing the permission-matrix moat

OpenCode's community is large, active, and technically capable. A well-scoped PR adding a permission matrix to OpenCode could ship in weeks. The governance primitives in TeaAgent need to be 6–12 months ahead of where OpenCode currently is — not 1 month ahead. The multi-sig consensus engine, SSH vote relay, and compliance audit exporter are the features that cannot be copied in a weekend.

---

## 9. Go-to-Market Implications

### Recommended positioning (3-sentence version)

TeaAgent is the **governance-first agent harness for teams that cannot afford to explain an ungoverned AI action to their CISO**. It wraps any LLM provider — Claude, GPT, Gemini, local models — with a hash-chained audit trail, hard cost caps, human-in-the-loop approval gates, and a compliance export bundle. It is the infrastructure layer between "AI agents are powerful" and "AI agents are production-safe."

### Prioritized go-to-market actions

1. **Publish externally** — README, product docs, and blog posts aimed at the security-conscious developer persona. Target the "Claude Is Dead" community and r/LocalLLaMA with the budget cap story. Zero cost, high reach.

2. **Write the security whitepaper** — A 10-page document mapping TeaAgent's controls to NIST AI Agent Standards and OWASP LLM Top 10. This unlocks the enterprise conversation and costs nothing to build.

3. **Close G6 first** — The doc-to-reality drift problem is a trust liability. Ship the CI guard (FO-1) before any external marketing push. External evaluators will find inconsistencies faster than internal ones.

4. **Pick one vertical beachhead** — Security tooling companies, fintech startups, or government contractors are the fastest path to a reference customer. Pick one, deploy there, document what happened.

5. **Position against Claude Code's gaps explicitly** — "Run your Claude Code-quality tasks with TeaAgent governance" is a message that reaches Claude Code's existing user base and positions TeaAgent as additive, not competitive.

6. **Defer cloud/hosted until G1–G5 are closed** — Building a SaaS before the product has external traction is premature. Govern the spending at the roadmap level the way TeaAgent governs spending at the agent level.

---

## Related Documents

- `docs/analysis/competitor-signal-survey-2026-06-04.md` — primary competitor evidence base
- `docs/analysis/seven-control-loops-competitor-survey-2026-06-05.md` — governance loop comparison
- `docs/analysis/community-agent-pain-points-survey-2026-06-05.md` — community pain point synthesis
- `docs/analysis/agent-competitive-risks-2026-05-31.md` — competitive risk register (historical)
- `docs/product-contract.md` — what TeaAgent is and is not
- `docs/maturity-matrix.md` — honest feature readiness assessment
- `docs/analysis/total-review-future-outlook-2026-06-04.md` — re-prioritized backlog with falsifiable exit criteria
