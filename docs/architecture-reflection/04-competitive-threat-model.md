# 04: Competitive Threat Model

> **Core question:** What would a well-funded competitor's winning argument against TeaAgent look like?
> **Priority:** P1 — strategic clarity, not immediately blocking.
> **Last reviewed:** 2026-06-09
> **Depends on:** [01-founder-playbook-reflection.md](01-founder-playbook-reflection.md) (Learning 2)
> **Work plan:** [Phase 03: Competitive Analysis](../plans/phase-03-competitive-analysis.md)

## Methodology

The Founder's Playbook warns that confirmation bias is amplified by AI: ask AI to validate your idea, and it will find supporting evidence. The antidote is **structured devil's advocacy** — building the strongest possible case for why a competitor would win, not just why TeaAgent is better.

This document follows the playbook's prescription:

> "要它為『競爭者會贏、而你不會』做最有說服力的論證。"

Each competitor analysis below makes the **strongest version** of the competitor's case, then evaluates what TeaAgent would need to do to invalidate that case.

---

## Competitor 1: Claude Code (Anthropic)

### The Strong Case for Claude Code Winning

"Claude Code is the default. TeaAgent has a governance layer, sure — but 95% of developers don't wake up wanting to configure permission modes and audit trails. They want to ship code. Claude Code ships code with zero friction. By the time TeaAgent finishes its `--setup` flow, Claude Code has already generated, tested, and committed a feature.

Anthropic has the brand, the distribution (1M+ developers on Claude), and the talent. They can add audit trails and permission modes in a quarter — they've already done `deny/ask/allow` modes. When they do, TeaAgent's differentiator collapses to 'they had it first' instead of 'they do it better.'

And here's the real problem: Claude Code integrates with the model that powers it. TeaAgent has 14 providers, but that means it's optimized for none. Claude Code can ship model-specific features (thinking mode, extended context, artifact rendering) that a generic adapter layer cannot match.

The governance wedge is real but small. Enterprise IT buyers care, but developers — who actually choose the tool — care about speed. TeaAgent is selling to the wrong buyer."

### Disconfirming Analysis

| Claim | Counterargument | Required Evidence |
|-------|-----------------|-------------------|
| "Claude Code can add audit in a quarter" | Audit trail is table-stakes; hash-chain integrity + verifiable replay is hard. Claude Code's deny/ask/allow is binary; TeaAgent has 5-tier + plan-before-write + approval queue | Ship hash-chain audit in Claude Code |
| "95% of devs don't need governance" | True for individuals, false for teams/enterprise. TeaAgent's wedge is team/enterprise, not solo dev | P0 adoption by small teams (3-5 devs) |
| "14 providers = optimized for none" | Adapter layer is thin by design. Provider-specific features (thinking, artifacts) are additive; governance layer is independent | Show that adding provider-specific features doesn't break governance |
| "Developers choose tools, not IT" | True. TeaAgent needs a compelling developer story *plus* governance — not governance alone | Developer UX benchmark: time-to-first-task vs Claude Code |

### TeaAgent's Required Response

1. **Compete on trust, not speed**: Own the enterprise governance narrative that Claude Code cannot credibly claim (hash-chain audit, verifiable runs, compliance exports)
2. **Don't fight the default**: TeaAgent should be *the* governance layer for Claude Code users too (via MCP/ACP integration), not a replacement
3. **Invest in developer UX**: Governance-first must not mean developer-hostile. Golden path must be ≤5 minutes

---

## Competitor 2: OpenCode

### The Strong Case for OpenCode Winning

"OpenCode is open-source, 11+ providers, and TUI-first — it occupies almost the same design space as TeaAgent. The difference is OpenCode has more contributors, more community traction, and a simpler architecture. It doesn't have TeaAgent's governance complexity, but it doesn't need it: it's a tool for developers, not a platform for compliance teams.

OpenCode's TUI is more mature. Its permission model (3 modes) covers 90% of what TeaAgent's 5 modes cover. It has auto-compaction, session management, and a plugin system. What OpenCode lacks (hash-chain audit, plan-before-write, enterprise whitepapers) its community can add — and they will, once enterprise demand materializes.

OpenCode wins because it's *simpler*. TeaAgent has 203 Python files; OpenCode has fewer. TeaAgent has 29 ADRs; OpenCode has none. Simplicity is a feature for developers. Complexity is a tax. TeaAgent charges the tax upfront for benefits that few developers need today."

### Disconfirming Analysis

| Claim | Counterargument | Required Evidence |
|-------|-----------------|-------------------|
| "OpenCode will add governance features as demand materializes" | Governance is not a feature — it's an architecture. You cannot bolt hash-chain audit onto a design that wasn't built for it. TeaAgent's governance is baked into the decision loop, not added as a plugin | Show a competitor attempting to add audit-chain integrity and failing |
| "Simplicity wins developer adoption" | For individual developers, yes. For engineering orgs with compliance requirements, governance is the price of entry | Reference case where an org chose TeaAgent specifically for audit capability |
| "OpenCode's 3 modes cover 90%" | 3 modes (deny/ask/allow) vs 5 (read-only/workspace-write/prompt/allow/danger-full-access) + plan-before-write + approval queue. The gap is at the top (enterprise control) and the bottom (automation safety) | Map each permission mode to a real compliance scenario |

### TeaAgent's Required Response

1. **Don't compete on features — compete on architecture**: Governance is not a feature checklist; it's a design philosophy. Make this argument explicit in docs
2. **Dogfood as differentiator**: TeaAgent should be *the* tool used to build TeaAgent. This creates a credibility gap OpenCode cannot close for its own development
3. **Be the governance layer for all tools**: MCP-first means TeaAgent can govern OpenCode sessions too. That's a stronger position than competing head-to-head

---

## Competitor 3: Codex (OpenAI)

### The Strong Case for Codex Winning

"Codex has the OpenAI distribution machine, $10B+ in funding, and deep integration with ChatGPT. It doesn't need to be better than TeaAgent at governance — it needs to be good enough. For most organizations, 'good enough' governance (file sandboxing, approval prompts) is sufficient.

Codex's real advantage is the **ecosystem**: ChatGPT plugins, GPTs, the OpenAI API platform. TeaAgent can integrate with 14 providers, but Codex integrates with the entire OpenAI ecosystem. When a team asks 'should we use TeaAgent or Codex?' the answer is already decided by which models they already use.

Codex can add governance features faster than TeaAgent can build distribution. OpenAI can hire a compliance team, write SOC 2 docs, and ship audit trails in a quarter. TeaAgent cannot hire 100 people to build distribution."

### Disconfirming Analysis

| Claim | Counterargument | Required Evidence |
|-------|-----------------|-------------------|
| "OpenAI can outspend on governance features" | Governance depth is not a function of spending. Hash-chain audit, verifiable run receipts, and plan-before-write require architectural decisions, not just feature work | Document the architectural depth that spending cannot shortcut |
| "Codex's ecosystem lock is decisive" | True for existing OpenAI customers. But multi-provider is itself a lock-breaker: organizations avoiding vendor lock-in will prefer TeaAgent | Identify the "multi-provider necessity" buyer persona |
| "Codex can add governance in a quarter" | If governance could be added in a quarter, every agent tool would already have it. The gap is architectural, not temporal | Time the actual development of TeaAgent's governance system as a reference |

### TeaAgent's Required Response

1. **Own the multi-provider governance narrative**: The only tool that can govern *any* model provider. This is a unique position
2. **Build open standards, not proprietary integration**: MCP, ACP, A2A — protocol-based governance that works across the ecosystem
3. **Distribution through integration, not replacement**: TeaAgent should work *with* Codex, not instead of it

---

## Competitor 4: Custom In-House Solutions

### The Strong Case for In-House Winning

"Every well-resourced engineering org will ask: 'Why not build our own thin governance wrapper around Claude Code/Codex?' The argument is compelling:
- We control the compliance requirements exactly
- We integrate with our existing auth, audit, and deployment systems
- We don't depend on a startup's roadmap
- We can start with a 200-line Python script and grow as needed

TeaAgent's value proposition — 'buy our governance layer instead of building your own' — is the hardest sell in enterprise software. The 'build vs buy' calculus favors build when the problem seems simple, and governance looks simple until you've spent 6 months building it."

### Disconfirming Analysis

| Claim | Counterargument | Required Evidence |
|-------|-----------------|-------------------|
| "Build costs 200 lines" | The first 200 lines are easy. The next 5000 (hash-chain audit, permission modes, plan validation, approval queue, run store, undo, context compaction, OAuth, MCP) are what TeaAgent already built | Build-cost comparison: 200 lines vs full governance system |
| "We control our roadmap" | But you also maintain it. Governance is not a set-it-and-forget-it problem — it requires continuous updates as models, protocols, and compliance requirements evolve | Maintenance cost comparison over 12 months |
| "We know our compliance needs" | Most orgs discover their compliance gaps during an audit, not during design. TeaAgent's off-the-shelf coverage (NIST mapping, SOC 2 prep, audit chain) already exceeds most in-house first iterations | Compliance gap analysis: what an in-house first version misses |

### TeaAgent's Required Response

1. **Make TeaAgent embeddable**: The strongest argument against in-house is "use TeaAgent as your starting point and customize." Open source + permissive license is the right model
2. **Provide compliance artifacts**: Whitepapers, NIST mappings, SOC 2 docs — the stuff in-house teams would spend months producing
3. **Document the hidden costs**: What in-house teams discover after month 3 (audit chain integrity, permission edge cases, provider compatibility)

---

## Cross-Competitor Threat Matrix

| Threat | Source | Severity | TeaAgent Advantage | Window |
|--------|--------|----------|-------------------|--------|
| Claude Code adds governance | Anthropic | High | Architectural depth (hash chain, 5-tier, plan validation) | 6-18 months |
| OpenCode erodes differentiation | Community | Medium | Built-in vs bolted-on governance philosophy | 12-24 months |
| Codex ecosystem lock | OpenAI | High | Multi-provider independence | Ongoing |
| In-house build decision | Enterprise | Medium | Accumulated complexity = buy signal | Per-deal |
| New AI-native competitor | Unknown | Medium | First-mover in governance category | 3-6 months |

## Required Actions

| Priority | Action | Addresses |
|----------|--------|-----------|
| P0 | Document architectural depth that competitors cannot easily duplicate | All competitors |
| P1 | Create "Multi-provider governance" buyer persona documentation | Codex, OpenCode |
| P1 | Build SOC 2 readiness package (docs + evidence) | Claude Code, In-house |
| P2 | Develop integration stories for Claude Code/Codex/OpenCode | Claude Code, Codex |
| P2 | Build open-standard governance protocol proposals (MCP extensions) | All competitors |

## References

- Founder's Playbook Learning 2: "AI as Devil's Advocate, Not Cheerleader"
- [Competitive feature matrix in README](../../README.md#what-makes-it-different)
- [Maturity Matrix](../maturity-matrix.md)
- [When Not to Use TeaAgent](../guides/when-not-to-use-teaagent.md)
