# TeaAgent Evidence Ledger - 2026-06-04

## Purpose

This document records the current evidence behind TeaAgent's direction: why the project is governance-first, why daily-driver UX matters, why the docs corpus is part of the product, and why trust-sensitive paths must be repaired before broader feature growth.

It is intentionally conservative. Claims are split into evidence, inference, and unknowns so later maintainers can tell what is grounded in the repository and what is a reasoned conclusion.

## Evidence Map

### 1. Governance is already the project's primary identity

- `README.md` frames TeaAgent as a "Governance-first agent harness" with permission gates, audit trails, undo, and budget caps.
- `docs/governance/README.md` defines governance as the authoritative standards layer and includes document-state, workflow, and ownership rules.
- `docs/modules/INDEX.md` places `runner`, `governance`, `approval_manager`, `audit`, and `budget` in the core layer and lists multiple high-severity risks around approval bypass, sandbox escape, and audit weakness.

**Inference:** the repository is not experimenting with governance as a side feature. Governance is the central product contract.

### 2. Daily-driver trust is more important than broad feature count

- `docs/daily-driver-current-status.md` and `docs/daily-driver-known-issues-2026-06-01.md` exist because user-facing trust gaps were visible enough to warrant a dedicated front door.
- `docs/reviews/daily-driver-red-team-review-2026-06-02.md` attacks the happy path directly and treats stale root, fake zero cost, and ambiguous approvals as trust failures.
- `docs/reviews/daily-driver-docs-package-review-2026-06-02.md` explicitly warns that docs can become a substitute for code.

**Inference:** the project is optimizing for operators who need to trust the agent in repeated daily use, not for one-off demo success.

### 3. The current core bottleneck is trust-path coherence

- `teaagent/chat_session_controller.py` centralizes result handling, undo journaling, and cost accumulation for the chat path.
- `teaagent/tui/__init__.py` still retains local TUI state, local checkpoint undo fallback, and a separate chat execution path, which means the TUI can drift from controller semantics.
- `docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md` records that the TUI lagged behind the controller fix batch and that a test could pass while live cost accumulation remained wrong.

**Inference:** the hardest remaining work is not isolated bug fixing. It is consolidating the trust path so the same command means the same thing across surfaces.

### 4. Acceptance coverage is strong, but docs and runtime behavior can still drift

- `docs/acceptance.md` tracks a very large acceptance corpus.
- `docs/analysis/daily-driver-docs-package-review-2026-06-02.md` warns that historical findings can appear contradictory after fixes land and that docs should only continue when they reduce ambiguity or convert risk into executable work.
- `docs/analysis/markdown-status-review-2026-06-02.md` recommends a governance layer for status, supersession, and roadmap updates instead of aggressive history deletion.

**Inference:** the docs corpus is now a control plane. Its job is to keep state truthful, not merely detailed.

### 5. Competitor pressure is mostly about UX shape, not raw novelty

- Pi.dev emphasizes malleability, session branching, and self-extension.
- OpenCode emphasizes multi-session work, LSP, desktop/IDE surfaces, and large provider coverage.
- Claude Code emphasizes skills, plugins, connectors, and enterprise tasking.
- Codex emphasizes multi-agent workflows, worktrees, automations, and review depth.
- Aider and OpenHands continue to show demand for surgical editing and open, self-hostable agent surfaces.

**Inference:** TeaAgent does not need to copy any one competitor. It needs to preserve the useful shape of each pattern while keeping governance stronger than the community default.

## Current Truth Statements

1. TeaAgent already has a credible governance backbone.
2. TeaAgent still has surface-level trust drift between CLI, TUI, and controller-backed behavior.
3. Documentation is part of the product and must be kept truthful.
4. The daily-driver experience is the best place to judge whether the project is useful.
5. The strongest competitive edge is not "more agent features". It is "usable agent behavior with receipts".

## What This Means For Direction

- Prioritize root truth, cost truth, undo truth, approval truth, and run evidence before expanding surface area.
- Keep dated analysis documents immutable except for supersession notes.
- Treat docs, acceptance, and roadmap records as one system.
- Prefer consolidating semantics over adding another surface-specific workaround.

## Unknowns

- Which upcoming feature will create the next daily-driver trust gap.
- Whether the remaining TUI/controller parity issues are limited to cost and undo or extend into session resume and background workflows.
- How much of the current docs corpus is still actively read by maintainers versus only archived for evidence.

## Sources

- [README.md](/Users/teee/dev/teaagent/README.md)
- [docs/governance/README.md](/Users/teee/dev/teaagent/docs/governance/README.md)
- [docs/modules/INDEX.md](/Users/teee/dev/teaagent/docs/modules/INDEX.md)
- [docs/daily-driver-current-status.md](/Users/teee/dev/teaagent/docs/daily-driver-current-status.md)
- [docs/daily-driver-known-issues-2026-06-01.md](/Users/teee/dev/teaagent/docs/daily-driver-known-issues-2026-06-01.md)
- [docs/reviews/daily-driver-red-team-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-red-team-review-2026-06-02.md)
- [docs/reviews/daily-driver-docs-package-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-docs-package-review-2026-06-02.md)
- [docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md](/Users/teee/dev/teaagent/docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md)
