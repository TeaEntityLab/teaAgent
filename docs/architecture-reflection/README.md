# TeaAgent Architecture Reflection

> **Last reviewed:** 2026-06-09
> **Review trigger:** Major architectural change, new phase of Founder's Playbook analysis, or product-market fit milestone.

A systematic reflection on TeaAgent's architecture through the lens of Anthropic's **The Founder's Playbook: Building an AI-Native Startup**. This directory contains concept documents that diagnose architectural tensions, identify misalignments with the Idea→MVP→Launch→Scale framework, and propose actionable remediations.

## Why This Exists

The Founder's Playbook argues that in the AI-native startup era, **the bottleneck is no longer what you can build, but what you choose to build**. TeaAgent—a governance-first agent harness built with agentic coding—is itself a case study of this dynamic. These documents make the implicit architectural choices explicit, test them against the playbook's framework, and derive concrete work plans.

## Document Map

| # | Document | Core Question | Priority |
|---|----------|---------------|----------|
| 01 | [Founder's Playbook Reflection](01-founder-playbook-reflection.md) | Where does TeaAgent stand across the 4 stages and 7 learnings? | Foundation |
| 02 | [Persistent Context Strategy](02-persistent-context-strategy.md) | How should AI-accessible project context be structured to prevent architectural drift? | P0 |
| 03 | [Scope Governance Framework](03-scope-governance-framework.md) | Which existing features are essential vs. premature for current PMF stage? | P0 |
| 04 | [Competitive Threat Model](04-competitive-threat-model.md) | What would a well-funded competitor's winning argument against TeaAgent look like? | P1 |
| 05 | [PMF Measurement Framework](05-pmf-measurement-framework.md) | What metrics separate genuine product-market fit from vanity signals? | P1 |
| 06 | [Founder Bottleneck Audit](06-founder-bottleneck-audit.md) | Which workflows stall when the founder is unavailable for a week? | P2 |
| 07 | [Defensibility & Moat Analysis](07-defensibility-moat-analysis.md) | What makes TeaAgent genuinely hard to replicate over a 2-3 year horizon? | P2 |

## Work Plans

Corresponding executable task plans exist in `docs/plans/`:

| Plan | Phase | Depends On |
|------|-------|------------|
| [Phase 01: Persistent Context](../plans/phase-01-persistent-context.md) | P0 | Concept doc 02 |
| [Phase 02: Scope Audit](../plans/phase-02-scope-audit.md) | P0 | Concept doc 03 |
| [Phase 03: Competitive Analysis](../plans/phase-03-competitive-analysis.md) | P1 | Concept doc 04 |
| [Phase 04: PMF Framework](../plans/phase-04-pmf-framework.md) | P1 | Concept doc 05 |
| [Phase 05: Founder Systematization](../plans/phase-05-founder-systematization.md) | P2 | Concept doc 06 |
| [Phase 06: Data Flywheel](../plans/phase-06-data-flywheel.md) | P2 | Concept doc 07 |

## Stage Assessment (as of 2026-06-09)

```
Idea [████████████████] 100% — Problem-solution fit established
MVP  [█████████████░░░]  85% — Product works, dogfooded internally
Launch [███████░░░░░░░░]  45% — CLI/TUI/docs ready, external PMF pending
Scale [████████░░░░░░░░]  35% — Enterprise infra pre-built, adoption early
```

TeaAgent's most distinctive architectural signature: **governance infrastructure scaled to enterprise readiness while product-market validation remains in early stages**. This is an intentional bet—trust infrastructure is genuinely hard to bolt on later for enterprise buyers—but it creates asymmetry that must be explicitly managed.

## Review Cadence

- **Full re-read**: Every 3 months or at each stage transition
- **Individual doc update**: When the relevant dimension materially changes
- **Work plan status**: Tracked via TODO in `docs/plans/`
