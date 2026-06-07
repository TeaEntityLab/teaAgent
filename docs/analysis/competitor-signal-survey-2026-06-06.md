# Competitor Signal Survey - 2026-06-06

> **Supersession note, 2026-06-07:** This file contains volatile facts
> (star counts, pricing, model availability, adoption claims, or status claims)
> that may be stale. For current competitive positioning and claim hygiene, see
> [competitive-claim-audit-2026-06-06.md](./competitive-claim-audit-2026-06-06.md).
> For current roadmap status, see [roadmap-status.md](../roadmap-status.md).

> **Claim class:** Dated evidence snapshot (quarterly refresh).
>
> **Supersedes:** [Competitor Signal Survey (2026-06-04)](competitor-signal-survey-2026-06-04.md)
> for positioning claims after 2026-06-06.
>
> **Companion:** [Competitor Self-Comparison Matrix (2026-06-06)](competitor-self-comparison-matrix-2026-06-06.md)
> for source-backed row-by-row comparison.

## Purpose

Refresh competitor signals from official documentation checked on 2026-06-06.
This pass emphasizes remote async agents, IDE-native UX, plan/spec separation,
and audit/compliance lanes — the patterns TeaAgent must either match in UX or
win on with provable governance.

## Method

- Official docs and upstream pages are primary evidence.
- Community posts remain secondary signals.
- Volatile metrics (stars, pricing tiers) are omitted unless sourced on the
  review date.

## Market shifts since June 4

1. **Remote async agents** are now table stakes for Codex, Copilot cloud agent,
   Cursor background agents, Kiro autonomous mode, Devin, and Jules — not
   optional premium features.
2. **IDE-native entry** (Cursor, Windsurf/Cascade, Cline, Copilot) sets the
   daily-driver bar higher than terminal-only onboarding.
3. **Plan/spec before write** (Cline Plan/Act, Kiro specs, Claude subagents,
   OpenCode permissioned agents) is the expected mental model.
4. **Audit/compliance** (Codex Compliance API, Devin enterprise audit logs,
   GitHub PR/session logs) is becoming a purchase criterion — TeaAgent's
   hash-chained audit is a strategic lane if made visible.

## Core competitor lessons (unchanged thesis)

| Project | TeaAgent lesson |
| --- | --- |
| Pi.dev | Adopt malleability; reject YOLO-default security. |
| OpenCode | Closest terminal threat — governance must be visible, not buried. |
| Claude Code | Full engineering loop expected; fake success is punished quickly. |
| Codex | Benchmark async handoff, review UX, and compliance surfaces. |
| Aider | Borrow git-native clarity for file targets and undo. |
| OpenHands | Safety language must match sandbox reality. |
| GitHub Copilot cloud agent | Do not compete on GitHub distribution; build adapters with TeaAgent audit exports. |
| Cursor / Cline / Kiro | IDE and plan/act receipts are UX targets, not reasons to abandon local-first governance. |

## TeaAgent implications (2026-06-06)

1. Keep local-first and provider-agnostic positioning — but stop implying remote
   readiness until WS2 safety gates pass.
2. Make run receipts, approval selectors, and cost taxonomy user-visible (WS1).
3. Treat audit/compliance as the primary public story once durability gates pass.
4. Refresh competitor docs quarterly or before release planning claims.

## Risks

- Official docs overstate maturity (especially cloud/enterprise surfaces).
- Competitor shutdowns (for example Roo Code product wind-down) can invalidate
  prior comparisons quickly.
- Remote-agent UX moves faster than governance hardening.

## Sources (checked 2026-06-06)

See the full source map in
[competitor-self-comparison-matrix-2026-06-06.md](competitor-self-comparison-matrix-2026-06-06.md).

Landscape survey artifact for matrix generation:
[scripts/refresh_agent_readme_survey.md](../../scripts/refresh_agent_readme_survey.md)
