# Evidence to Principle Policy

## Purpose

This policy explains how TeaAgent should turn repository evidence into durable principles, and how future documentation should preserve that chain of reasoning.

## Rules

### 1. Use a source hierarchy

Order of authority:

1. Current repository code and tests
2. Current repository docs that are clearly marked as active
3. Dated analysis and review artifacts
4. External official docs and release notes
5. Community feedback and forum posts

### 2. Separate evidence from inference

Every nontrivial claim in a strategy or analysis doc must be labeled as one of:

- Evidence
- Inference
- Unknown

If a reader cannot tell which is which, the document is not finished.

### 3. Preserve history instead of erasing it

Dated review files are evidence, not clutter. If a later doc supersedes an earlier one, the older file should remain in place and receive a supersession note when needed.

### 4. One new doc must earn its place

A new document is justified only if it does at least one of these:

- reduces ambiguity for a daily user or maintainer
- converts a risk into a task
- records a decision that would otherwise be lost
- captures external evidence that materially affects direction

### 5. Treat competitor surveys as intake, not default new docs

Competitor surveys and community feedback are evidence intake. They do not
automatically justify a new strategy document, roadmap claim, or public
positioning update.

Write or refresh competitor-facing documents only when one of these triggers
applies:

- quarterly refresh or publication-triggered re-verification
- release-blocking eval gate or official ecosystem change
- owner-validated ergonomics friction that converts a hypothesis into evidence
- a governance, audit, approval, rollback, cost, or validation gap that changes
  TeaAgent's harness-first direction

Otherwise, route the signal through the
[Signal-to-Acceptance-Gap Process](../processes/signal-to-acceptance-gap.md).
UX and ergonomics signals stay as `[hypothesis: source, date]` entries in the
[Operator Friction Log](../work-log/operator-friction-log.md) until validated in
real owner use.

### 6. Keep the entry points short

Long evidence exists so that short front doors can exist.

The current-status page, roadmap index, and top-level governance docs should stay easy to enter. Deep analysis belongs in dated evidence docs.

### 7. Turn principles back into work

Every principle document should point to the work that proves it. A principle without a follow-up task is just branding.

## Required Sections For New Evidence Documents

Every new evidence-driven markdown file should include:

1. Purpose
2. Source boundary or evidence scope
3. Evidence or findings
4. Inference or interpretation
5. Risks or unknowns
6. Follow-up work or implications

## When To Write A New Doc

Write a new document when:

- the current documents disagree
- a new competitor signal passes the harness-first routing gate and changes the
  strategic picture
- a trust failure needs a formal rationale
- a review pass has created enough evidence that it deserves a durable artifact

Do not write a new document when:

- a short note would be enough
- the same point already exists in a current status or ledger doc
- the change is purely cosmetic
- a competitor signal is only an unvalidated UX hypothesis

## Sources

- [docs/governance/README.md](/Users/teee/dev/teaagent/docs/governance/README.md)
- [docs/analysis/markdown-status-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/analysis/markdown-status-review-2026-06-02.md)
- [docs/reviews/daily-driver-docs-package-review-2026-06-02.md](/Users/teee/dev/teaagent/docs/reviews/daily-driver-docs-package-review-2026-06-02.md)
- [docs/analysis/teaagent-evidence-ledger-2026-06-04.md](/Users/teee/dev/teaagent/docs/analysis/teaagent-evidence-ledger-2026-06-04.md)
