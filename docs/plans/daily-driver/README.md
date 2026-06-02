# Daily-Driver Plan Index
# 2026-06-02

This directory is the proposed front door for future daily-driver execution planning.
The older [../ticket-plans](../ticket-plans) directory remains the active ticket-plan
location today.

## Document governance

Use the governance docs before adding another dated risk, issue, or roadmap file:

- [Document State Model](../../governance/document-state-model.md)
- [Risk Issue Roadmap Workflow](../../governance/risk-issue-roadmap-workflow.md)
- [Documentation Taxonomy And Ownership](../../governance/doc-taxonomy-and-ownership.md)
- [Markdown Status Review](../../analysis/markdown-status-review-2026-06-02.md)

## Critical path

1. TUI root state.
2. Chat task execution verification.
3. TUI cost ledger and controller migration.
4. Approval path scope.
5. Git sandbox lifecycle.
6. Lifecycle wording.
7. Stale chat cleanup.
8. Read-only/dry-run side-effect contract.
9. Memory and run-state integrity warnings.

## Current source files

| Purpose | File |
|---------|------|
| Implementation sequence | [../daily-driver-implementation-sequencing-board-2026-06-02.md](../daily-driver-implementation-sequencing-board-2026-06-02.md) |
| Regression matrix | [../daily-driver-regression-test-matrix-2026-06-02.md](../daily-driver-regression-test-matrix-2026-06-02.md) |
| Ticket plans | [../ticket-plans/index.md](../ticket-plans/index.md) |
| Operational runbook | [../daily-driver-operational-runbook-2026-06-02.md](../daily-driver-operational-runbook-2026-06-02.md) |
| Human review gates | [../../analysis/daily-driver-human-review-gates-2026-06-02.md](../../analysis/daily-driver-human-review-gates-2026-06-02.md) |
| Guide index | [../../guides/daily-driver-guide-index-2026-06-02.md](../../guides/daily-driver-guide-index-2026-06-02.md) |
| Module map | [../../modules/daily-driver-module-map-2026-06-02.md](../../modules/daily-driver-module-map-2026-06-02.md) |
| Verification backlog | [../daily-driver-verification-backlog-2026-06-02.md](../daily-driver-verification-backlog-2026-06-02.md) |
| More-docs log | [../../analysis/daily-driver-more-docs-log-2026-06-02.md](../../analysis/daily-driver-more-docs-log-2026-06-02.md) |

## Ticket shape

Each ticket should include:

- Problem.
- Scope.
- Affected files.
- Acceptance criteria.
- Verification.
- Risks.
- Dependencies.
- Human review gate, if any.

## Status policy

Use the canonical states from
[Document State Model](../../governance/document-state-model.md). This plan index
keeps the shorter labels below for readability:

| Label | Meaning |
|-------|---------|
| Proposed | Observed but not triaged or owned yet. |
| Active | Behavior is still known broken. |
| Partially fixed | Code changed but proof is incomplete. |
| Verify/close | Implementation appears present; tests/docs need closure. |
| Fixed | Active path tests and docs agree. |
| Superseded | Replaced by a newer ticket or design. |
| Archived | Historical context retained without an active execution claim. |

## Operating doc layers

| Layer | Use |
|-------|-----|
| Guides | Help daily users choose commands and recover. |
| Debugging | Reproduce and isolate failures. |
| Reliability/security/governance | Review readiness and trust boundaries. |
| Design/specs | Define cross-ticket behavior. |
| Module docs | Assign ownership and inspection paths. |
| Ticket plans | Execute fixes. |
