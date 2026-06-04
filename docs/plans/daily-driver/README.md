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
- [Documentation Operating Model](../../governance/documentation-operating-model-2026-06-04.md)
- [Documentation State Review](../../analysis/documentation-state-review-2026-06-04.md)
- [Documentation Optimization Master Plan](../documentation-optimization-master-plan-2026-06-04.md)

## Critical path

1. Cost and budget truth.
2. TUI / CLI semantic parity.
3. Undo and recovery honesty.
4. Root and approval-scope truth.
5. Resume/background lifecycle repair.
6. Run evidence and audit completeness.
7. Controller persistence error handling.
8. First-hour onboarding and recovery copy.
9. MCP, skills, and subagent trust hardening.
10. Docs as control plane.

## Current source files

| Purpose | File |
|---------|------|
| Complete risk/ROI work plan | [../daily-driver-complete-work-plan-risk-roi-2026-06-04.md](../daily-driver-complete-work-plan-risk-roi-2026-06-04.md) |
| Implementation sequence | [../daily-driver-implementation-sequencing-board-2026-06-02.md](../daily-driver-implementation-sequencing-board-2026-06-02.md) |
| Regression matrix | [../daily-driver-regression-test-matrix-2026-06-02.md](../daily-driver-regression-test-matrix-2026-06-02.md) |
| Ticket plans | [../ticket-plans/index.md](../ticket-plans/index.md) |
| Operational runbook | [../daily-driver-operational-runbook-2026-06-02.md](../daily-driver-operational-runbook-2026-06-02.md) |
| Human review gates | [../../analysis/daily-driver-human-review-gates-2026-06-02.md](../../analysis/daily-driver-human-review-gates-2026-06-02.md) |
| Guide index | [../../guides/daily-driver-guide-index-2026-06-02.md](../../guides/daily-driver-guide-index-2026-06-02.md) |
| Module map | [../../modules/daily-driver-module-map-2026-06-02.md](../../modules/daily-driver-module-map-2026-06-02.md) |
| Verification backlog | [../daily-driver-verification-backlog-2026-06-02.md](../daily-driver-verification-backlog-2026-06-02.md) |
| More-docs log | [../../analysis/daily-driver-more-docs-log-2026-06-02.md](../../analysis/daily-driver-more-docs-log-2026-06-02.md) |
| Documentation optimization work items | [../../work-log/documentation-optimization-work-items-2026-06-04.md](../../work-log/documentation-optimization-work-items-2026-06-04.md) |

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
