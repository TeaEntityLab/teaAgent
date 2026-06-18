# 03: Scope Governance Framework

> **Core question:** Which existing features are essential vs. premature for TeaAgent's current PMF stage?
> **Priority:** P0 — scope sprawl is the #1 AI-native startup failure mode per the Founder's Playbook.
> **Last reviewed:** 2026-06-09
> **Depends on:** [01-founder-playbook-reflection.md](01-founder-playbook-reflection.md) (Learning 4)
> **Work plan:** [Phase 02: Scope Audit](../plans/phase-02-scope-audit.md)

## Problem Statement

The Founder's Playbook identifies **zero-friction scope creep** as a defining failure mode of the AI era: when adding a feature costs an afternoon instead of a sprint, the natural brake (engineering cost) disappears. Every individual addition seems reasonable; the aggregate destroys focus.

TeaAgent's scope at one month:

| Category | Count | Status |
|----------|-------|--------|
| Python source files | 203 | All shipped |
| Test files | 332 | Covering P0 through P6 |
| ADRs | 29 | Documenting continuous decisions |
| LLM providers | 14 | All integrated |
| Protocol surfaces | 5 (MCP stdio, MCP HTTP, ACP, A2A, ANP) | All shipped |
| Development phases | P0 through P6 | P0-P3 Stable, P4-P6 Beta |

**The tension:** This breadth is impressive but unfocused. The project has Beta features (Swarm Consensus, WASM sandbox, Control Plane) that are reasonable for a post-PMF company but questionable pre-PMF.

## The Framework

Every existing and proposed feature should be classified along two axes:

```
Necessity for PMF
     ^
     | [Build Now]          [Build After PMF]
     |   Core governance     Swarm consensus
     |   CLI/TUI             WASM sandbox
     |   14 providers        Control plane
     |   MCP/ACP            Tournament scoring
     |   Audit trail
     |   Memory system
     |
     +---------------------------> Dogfooding Value
     |
     | [Questionable]        [Defer Indefinitely]
     |   (empty)              Dashboard hosting
     |                        Cloud managed runtime
     |                        Enterprise SSO
     |
```

### Classification dimensions

**Necessity for PMF:**
- *Critical*: Without this, the core value proposition is not deliverable
- *Important*: Users can get value without it, but adoption would be significantly slower
- *Enhancement*: Nice-to-have; does not affect initial adoption
- *Distraction*: Actively harms focus without proportional user benefit

**Dogfooding Value:**
- *Direct*: The founder/team uses this actively in developing TeaAgent
- *Adjacent*: Useful occasionally but not part of daily workflow
- *None*: Cannot be dogfooded effectively

### TeaAgent's specific context

TeaAgent is unusual because **it is a development tool being built with itself**. This means features that would be "premature" for an e-commerce startup (e.g., Swarm Consensus) have genuine dogfooding value: they test the tool's own capabilities. The framework must account for this without using it as blanket justification for scope sprawl.

## Feature Audit: P0-P3 (Stable)

| Feature | PMF Necessity | Dogfood Value | Verdict | Rationale |
|---------|--------------|---------------|---------|-----------|
| AgentRunner (core loop) | Critical | Direct | ✅ Stay | Defines the product category |
| 14 LLM providers | Critical | Direct | ✅ Stay | Multi-provider is a core differentiator |
| Permission matrix (5 modes) | Critical | Direct | ✅ Stay | Defines the product category |
| Hash-chain audit | Critical | Direct | ✅ Stay | Governance wedge |
| CLI/TUI | Critical | Direct | ✅ Stay | Primary interface |
| MCP server/client | Important | Direct | ✅ Stay | Extensibility surface |
| Run store / resume | Important | Direct | ✅ Stay | Usability requirement |
| Memory catalog (3-tier) | Important | Direct | ✅ Stay | Context continuity |
| Plan-before-write | Important | Direct | ✅ Stay | Safety guarantee |
| Context compaction | Important | Direct | ✅ Stay | Session management |
| Self-healing validation | Enhancement | Direct | ✅ Stay | Engineering productivity |
| Failure cards | Enhancement | Direct | ✅ Stay | Memory hygiene |
| Hook system | Enhancement | Direct | ✅ Stay | Extensibility |

## Feature Audit: P4-P6 (Beta)

| Feature | PMF Necessity | Dogfood Value | Verdict | Rationale |
|---------|--------------|---------------|---------|-----------|
| Swarm/Consensus engine | Distraction | Adjacent | ⚠️ Gate to experimental | Useful for multi-agent scenarios but not core to governance wedge |
| Tournament execution | Distraction | Adjacent | ⚠️ Gate to experimental | Parallel approach comparison is useful but not PMF-critical |
| WASM runtime | Distraction | None | ⚠️ Gate to experimental | Over-engineered for current stage; simple subprocess suffices |
| Docker sandbox | Enhancement | Adjacent | ⚠️ Gate to experimental | Useful for isolation but few users will need it pre-PMF |
| Control plane API | Distraction | None | ⚠️ Gate to experimental | Admin dashboard is a Scale concern |
| Skill writer pipeline | Enhancement | Direct | ⚠️ Gate to experimental | Useful but can be simpler |
| OAuth 2.1/DPoP | Enhancement | None | ✅ Already stable | Required for enterprise; okay to keep |
| ACP adapter | Enhancement | Direct | ✅ Stay | IDE integration necessary for adoption |
| Remote JIT approval | Enhancement | None | ⚠️ Gate to experimental | Enterprise feature, pre-PMF |
| Context bus (cross-sandbox) | Distraction | None | ⚠️ Gate to experimental | Over-engineered for current needs |
| Telemetry | Enhancement | Direct | ✅ Stay | OTel integration useful but not critical |

## Gate Criteria for Beta Features

To graduate from "experimental" status, a Beta feature must meet **at least two** of:

1. **User demand signal**: At least 3 external users (not the founder) explicitly request it
2. **PMF blocker identified**: A target user segment says they cannot adopt TeaAgent without it
3. **Revenue impact**: Directly enables a paid tier or enterprise deal
4. **Dogfooding proof**: The founder/team uses it in daily development for 2+ weeks without issues

Until a feature meets at least two criteria, it remains `--experimental` flag or opt-in plugin.

## Scope Decision Protocol

When a new feature is proposed:

```
Proposal → [PMF Necessity] → [Dogfooding Value] → [Build Cost] → Decision
                ↓                   ↓                   ↓
           If Distraction      If None             If >2 weeks → Non-blocking
           → Reject            → Reject            post-PMF item
           If Enhancement      If Adjacent         If <2 days → Accept as
           → Gate to           → Gate to              experimental
             experimental         experimental
           If Important/       If Direct
           Critical            → Likely accept
           → Accept
```

## Non-Goals (Explicit)

The following are **deliberately out of scope** pre-PMF:

1. **Hosted cloud platform** (managed runtime, dashboard-as-a-service)
2. **Enterprise SSO/SAML** (OAuth 2.1/DPoP is sufficient for now)
3. **Native mobile/desktop app** (CLI + IDE integration is the surface)
4. **Plugin marketplace hosting** (plugin system exists; marketplace is a Scale concern)
5. **Third-party security certifications** (SOC 2 readiness docs exist; certification is post-PMF)
6. **Multi-tenant server** (local-first is the wedge; server comes later)

## Success Criteria

- [ ] At least one Beta feature is demoted to experimental or removed
- [ ] No new feature is added to the codebase without passing the Scope Decision Protocol
- [ ] A non-goals list exists and is reviewed monthly
- [ ] Every existing feature has a documented PMF-necessity classification
- [ ] Feature bloat stops growing faster than core adoption

## Risks

| Risk | Mitigation |
|------|-----------|
| Demoting features causes contributor frustration | Document rationale transparently in ADR format |
| Scope protocol becomes bureaucratic | Keep it lightweight: a single PR comment template |
| "Dogfooding value" becomes a loophole for any feature | Require 2+ weeks of actual daily usage as evidence |
| Pre-PMF scope is too restrictive and misses opportunities | Quarterly review of the non-goals list |

## References

- Founder's Playbook Learning 4: "Zero-Friction Scope Creep"
- ADR 0015: Rejected — Plugin system config (example of scope discipline)
- ADR 0010/0012/0014/0017: Closed — Superseded/Archived (more scope discipline evidence)
- [Maturity Matrix](../maturity-matrix.md): Current status of all features
