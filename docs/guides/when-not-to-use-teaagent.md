# When Not to Use TeaAgent

> **Last reviewed:** 2026-06-10
> **Purpose:** Honest non-fit guidance (WS6-005 / WDH-003)

TeaAgent is a **local-first governed harness**. Choosing the wrong tool wastes
everyone's time. Prefer another product when your primary need matches one of
these scenarios.

## IDE-first teams

**You want:** Inline completions, diff-in-editor UX, minimal terminal friction.

**Better fit:** Cursor, GitHub Copilot, Windsurf, Cline-in-IDE.

**Why not TeaAgent:** The primary surface is CLI/TUI. A VS Code extension exists
but IDE-native agents optimize for a different daily loop.

## Hosted cloud delegation

**You want:** Fire-and-forget cloud agents, mobile status, vendor-managed sandboxes.

**Better fit:** OpenAI Codex cloud tasks, Devin-style hosted agents, Copilot Workspace.

**Why not TeaAgent:** No multi-tenant SaaS offering today. You operate the runner,
storage, and keys locally or in your CI.

## Zero-config beginners

**You want:** Install one app and start coding with no permission vocabulary.

**Better fit:** Consumer IDE agents with simplified defaults.

**Why not TeaAgent:** Permission modes, audit paths, and approval queues are
features for **governance**, not simplicity. Setup expects deliberate choices
(`teaagent setup`, provider env, mode selection).

## Instant autocomplete only

**You want:** Tab-complete the next line while typing.

**Better fit:** Copilot inline, Codeium, etc.

**Why not TeaAgent:** TeaAgent orchestrates multi-step tool loops, not keystroke completion.

## "Set issue and forget" product management

**You want:** Assign a ticket to an autonomous product that ships without operator review.

**Better fit:** Fully managed autonomous dev products (with their tradeoffs).

**Why not TeaAgent:** Human approval, budgets, and audit are intentional brakes —
not bugs to bypass.

## Enterprise procurement without engineering evaluation

**You want:** SOC 2 certificate, vendor MSA, and a sales-led deployment this quarter.

**Better fit:** Established vendors with completed compliance programs (Anthropic,
Microsoft, AWS-backed products).

**Why not TeaAgent today:** Architecture supports evidence collection; certification
and hosted enterprise packaging are organizational/roadmap items, not shipped OSS defaults.

## When TeaAgent *is* the right choice

- Regulated or security-conscious teams needing **hash-chained audit** and export
- Operators who want **hard cost caps** and permission matrices
- Multi-provider or local-model workflows under one harness
- Teams building **custom tools/plugins** with registry governance

## Related

- [Trust and Audit Whitepaper](../governance/trust-and-audit-whitepaper.md)
- [Competitive landscape (2026-06-06)](../analysis/competitive-landscape-and-positioning-2026-06-06.md)
- [Solo CLI getting started](getting-started-solo-cli.md)
