# TeaAgent Product Principles - 2026-06-04

## Purpose

This document explains why TeaAgent is shaped the way it is. It ties the current repository evidence to the product principles that should govern future work.

The intent is not to sound noble. The intent is to keep future changes aligned with the actual problems this repository is trying to solve.

## Core Principles

### 1. Governance first

TeaAgent is a governed harness before it is a chat surface or a feature platform.

**Why this exists**

- Agentic tools can do the wrong thing quickly.
- The repository already invests heavily in permission modes, approvals, audit logging, run storage, and plan gates.
- The highest-severity risks in the module index cluster around approval bypass, sandbox escape, and trust drift.

**What this means**

- New features must preserve approval, audit, undo, and budget semantics.
- Any new path that bypasses governance must be treated as a defect unless it is explicitly isolated and documented.

### 2. Receipts before rhetoric

Every meaningful action should leave a record that a maintainer or user can inspect later.

**Why this exists**

- The docs already treat run history, audit logs, and cost as core product objects.
- Daily-driver failures are only useful if they can be reproduced and understood.
- False certainty is more harmful than missing data.

**What this means**

- Run summaries, audit events, cost ledgers, and undo records are not optional metadata.
- If a feature cannot be explained with receipts, it is not ready to become a default path.

### 3. Community feedback is signal, not fact

Community feedback — GitHub issues, Reddit threads, Discord discussions, competitor
changelogs — is valuable directional input but is not a validated requirements
specification. Treat every external signal as a hypothesis to be tested against
TeaAgent's governance contract, not as a feature request to be executed.

**Why this exists**

- Competitor surveys and community pain-point analyses surface recurring themes,
  but loudness is not severity and frequency is not correctness.
- Building directly from community sentiment without verification produces
  reactive, incoherent roadmaps.
- The repository already invests in dated competitor surveys, gap-watch processes,
  and signal-to-acceptance-gap conversion (see `docs/processes/signal-to-acceptance-gap.md`).

**What this means**

- Every community signal must be dated, sourced, and assigned a confidence level
  before it influences a roadmap row or acceptance criterion.
- "The community wants X" is never sufficient justification for a feature.
- Signal-to-action conversion requires: signal capture → gap triage → acceptance
  gap filing → roadmap row with exit evidence.
- Prefer closing the loop: when a signal leads to a change, document the signal
  and the change together so future readers can trace the reasoning.

### 4. Trust-sensitive paths outrank breadth

The shortest path to product value is not "more features". It is "more dependable behavior in the paths people use every day".

**Why this exists**

- The repository has already found that the daily surfaces are where trust is won or lost.
- TUI/CLI mismatch is more damaging than the absence of another niche integration.
- Users forgive a missing nice-to-have more easily than a lying cost display or an ambiguous undo.

**What this means**

- Fix semantic drift before expanding the surface.
- Prioritize first-hour onboarding, root truth, cost truth, undo truth, and approval truth.

### 5. Docs are part of the control plane

TeaAgent's documentation is not a scrapbook. It is part of the operational system.

**Why this exists**

- The docs corpus already tracks current status, known issues, risks, reviews, plans, and governance.
- Several docs explicitly warn that stale status pages can mislead operators.
- A maintainable product needs a navigable truth surface.

**What this means**

- Dated evidence docs should be preserved.
- Supersession notes should be explicit.
- New docs should exist only when they reduce ambiguity, create a decision trail, or turn a risk into executable work.

### 6. Malleability with boundaries

TeaAgent should let users reshape workflows without letting the harness dissolve into unreviewable entropy.

**Why this exists**

- Pi.dev and other competitors show that users value self-extension and live customization.
- The repository already supports skills, MCP, plugins, hooks, and multiple surfaces.
- Unbounded extension ecosystems usually produce fragmented security and inconsistent UX.

**What this means**

- Skills and plugins should remain declarative where possible.
- Runtime extension must stay reviewable and traceable.
- The project should resist bolt-on escape hatches that weaken the governance contract.

### 7. Narrow core, broad composability

The core harness should stay thin even when the ecosystem grows.

**Why this exists**

- The repository already distinguishes core harness behavior from extension points and userland workflows.
- Extra agent frameworks tend to create duplicate state, duplicate policies, and duplicate recovery paths.

**What this means**

- Prefer reuse and boundary repair over new abstraction layers.
- If a capability can live as a skill, a policy, or a doc workflow, keep it out of core.

## Evidence Behind the Principles

| Principle | Evidence anchors | What it supports |
|---|---|---|
| Governance first | `README.md`, `docs/modules/INDEX.md`, `docs/governance/README.md` | Core mission, risk priorities |
| Receipts before rhetoric | `docs/analysis/daily-driver-advice-and-recommendation-ledger-2026-06-02.md`, `docs/analysis/daily-driver-current-truth-audit-2026-06-01.md` | Run evidence, auditability |
| Community feedback is signal, not fact | `docs/analysis/community-agent-pain-points-survey-2026-06-05.md`, `docs/processes/opencode-gap-watch.md`, `docs/processes/signal-to-acceptance-gap.md` | Signal-to-gap discipline, roadmap hygiene |
| Trust-sensitive paths outrank breadth | `docs/reviews/daily-driver-red-team-review-2026-06-02.md`, `docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md` | TUI/CLI parity, root/cost/undo honesty |
| Docs are control plane | `docs/reviews/daily-driver-docs-package-review-2026-06-02.md`, `docs/analysis/markdown-status-review-2026-06-02.md` | Supersession, status discipline |
| Malleability with boundaries | `docs/analysis/pi-agent-ecosystem-review-2026-06-03.md`, `docs/strategy/malleable-governed-agent-harness-2026-06-03.md` | Extensibility with governance |
| Narrow core, broad composability | `docs/governance/README.md`, `docs/modules/INDEX.md` | Keep harness thin |

## Anti-Principles

These are explicitly rejected:

- More docs as a substitute for a missing runtime guarantee.
- Surface-specific semantics that make the same action mean different things in different UIs.
- Extension ecosystems without trust review.
- Recovery paths whose wording is clearer than their actual behavior.
- Roadmaps that optimize for breadth at the expense of trust.

## What Should Happen When a New Feature Appears

Before shipping, ask:

1. Does this preserve or improve the governance contract?
2. Does this leave a receipt?
3. Does this reduce or increase daily-driver trust?
4. Can it be explained clearly in the docs without overclaiming?
5. Is this core behavior or userland composition?

If the answer is "no" to the first three questions, the feature should not become a default path.

## Sources

- [README.md](/Users/teee/dev/teaagent/README.md)
- [docs/modules/INDEX.md](/Users/teee/dev/teaagent/docs/modules/INDEX.md)
- [docs/governance/README.md](/Users/teee/dev/teaagent/docs/governance/README.md)
- [docs/analysis/daily-driver-advice-and-recommendation-ledger-2026-06-02.md](/Users/teee/dev/teaagent/docs/analysis/daily-driver-advice-and-recommendation-ledger-2026-06-02.md)
- [docs/analysis/daily-driver-current-truth-audit-2026-06-01.md](/Users/teee/dev/teaagent/docs/analysis/daily-driver-current-truth-audit-2026-06-01.md)
- [docs/reviews/daily-driver-red-team-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-red-team-review-2026-06-02.md)
- [docs/reviews/daily-driver-docs-package-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-docs-package-review-2026-06-02.md)
- [docs/analysis/markdown-status-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/analysis/markdown-status-review-2026-06-02.md)
- [docs/analysis/pi-agent-ecosystem-review-2026-06-03.md](/Users/teee/dev/teaagent/docs/analysis/pi-agent-ecosystem-review-2026-06-03.md)
- [docs/strategy/malleable-governed-agent-harness-2026-06-03.md](/Users/teee/dev/teaagent/docs/strategy/malleable-governed-agent-harness-2026-06-03.md)
