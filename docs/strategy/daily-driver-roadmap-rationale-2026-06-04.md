# Daily-Driver Roadmap Rationale - 2026-06-04

> **Last strategy refresh:** 2026-06-06 — competitor signals updated in
> [Competitor Signal Survey (2026-06-06)](../analysis/competitor-signal-survey-2026-06-06.md).
> Priority ordering below remains valid: trust repair before surface expansion.

## Purpose

This document explains why the roadmap should favor trust repair and daily-driver usability before broader expansion.

## Priority Ordering

### Tier 1: Restore trust in the core surfaces

1. TUI and CLI semantic parity
2. Undo behavior honesty and consistency
3. Cost and budget truth
4. Root selection truth
5. Approval scope clarity

**Why first**

- These are the surfaces a daily user sees immediately.
- If these are wrong, every other feature feels suspicious.
- A feature-rich agent that lies about cost, undo, or root is not daily-driver ready.

### Tier 2: Make the first hour safe and understandable

1. First-run onboarding
2. Error recovery that tells the user what to do next
3. Current-status front door
4. Surface guides that tell the user what is real today

**Why second**

- The project already has deep docs, but not every user enters through the deep end.
- Onboarding and recovery are where user trust is either accelerated or lost.

### Tier 3: Strengthen the evidence chain

1. Run evidence bundles
2. Audit completeness
3. Status ledgers and supersession notes
4. Docs/status drift controls

**Why third**

- The system already produces a lot of evidence.
- The next step is to make that evidence easy to consume and hard to misread.

### Tier 4: Harden the extension and ecosystem boundary

1. MCP trust boundaries
2. Skill installation governance
3. Subagent lineage and isolation
4. Sandbox defaults and recovery guarantees

**Why fourth**

- These are high-risk paths with wide blast radius.
- They should not be expanded until the trust path is coherent.

### Tier 5: Expand only after the trust path is boring

1. Larger surface parity
2. More ecosystem packaging
3. More competitive feature matching
4. More convenience automation

**Why last**

- Competitive breadth matters, but only after the user can trust the core.
- Adding features before repairing semantics creates more docs and more confusion, not more usefulness.

## Concrete Work Themes

### Theme A: TUI / CLI parity

- Migrate remaining TUI chat behavior to shared controller logic.
- Make `/cost`, `/undo`, resume, suspend, and root selection resolve the same way across surfaces.
- Keep fallback behavior explicit instead of implicit.

### Theme B: Recovery and evidence honesty

- Make undo scope visible before and after the action.
- Separate journal-based undo from checkpoint-based rollback in wording and behavior.
- Ensure run evidence states what is verified, what is inferred, and what is not tested.

### Theme C: First-hour experience

- Make setup and daily entry routes obvious.
- Keep the current-status page ahead of the historical corpus.
- Ensure common errors point to recovery actions, not internal taxonomy.

### Theme D: Trust boundary hardening

- Enforce MCP trust expiry at call time.
- Keep skill and subagent execution isolated by default.
- Ensure destructive actions remain gated by explicit policy.

### Theme E: Documentation governance

- Keep dated evidence immutable except for supersession notes.
- Add one new doc only when it reduces ambiguity or converts risk into work.
- Use the status ledger as the truth surface, not as a story archive.

## Suggested Execution Sequence

1. Close parity and trust drift in the daily surfaces.
2. Update acceptance and evidence docs to match the actual behavior.
3. Harden the highest-risk trust boundaries.
4. Refresh the current-status and roadmap docs.
5. Only then add breadth features or ecosystem expansion.

## How To Tell If The Priority Order Is Wrong

The current order is likely wrong if:

- Users repeatedly ask "what did it actually do?" after every run.
- Docs become more detailed while test coverage of live paths stays flat.
- New features ship faster than parity gaps close.
- Roadmap items look exciting but do not reduce trust failures.

## Sources

- [docs/analysis/daily-driver-advice-and-recommendation-ledger-2026-06-02.md](/Users/teee/dev/teaagent/docs/analysis/daily-driver-advice-and-recommendation-ledger-2026-06-02.md)
- [docs/reviews/daily-driver-red-team-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-red-team-review-2026-06-02.md)
- [docs/reviews/daily-driver-docs-package-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-docs-package-review-2026-06-02.md)
- [docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md](/Users/teee/dev/teaagent/docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md)
- [docs/analysis/markdown-status-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/analysis/markdown-status-review-2026-06-02.md)
- [docs/analysis/pi-agent-ecosystem-review-2026-06-03.md](/Users/teee/dev/teaagent/docs/analysis/pi-agent-ecosystem-review-2026-06-03.md)
