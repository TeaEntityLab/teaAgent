[README.md#A828]
# Architecture Decision Records (ADR)

This directory contains all Architecture Decision Records (ADRs) for the TeaAgent project. ADRs document significant architectural decisions, their rationale, and consequences.

## ADR Index

| Number | Title | Status | Created | Last Updated |
|--------|-------|--------|---------|--------------|
| [0001](0001-p0-framework.md) | P0 Agent Harness Framework | Accepted and Implemented | 2026-05-08 00:31:33 +0800 | 2026-05-22 00:27:39 +0800 |
| [0002](0002-p1-primitives.md) | P1 Primitives | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | - |
| [0003](0003-p2-code-mode-sandbox.md) | Code Mode Child-Process Sandbox | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | 2026-05-14 18:40:37 +0800 |
| [0004](0004-oauth-dpop.md) | OAuth 2.1 + DPoP with Optional Dependencies | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | 2026-05-22 01:03:20 +0800 |
| [0005](0005-mcp-streamable-http.md) | MCP Streamable HTTP Transport | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | - |
| [0006](0006-oauth-store-keyring.md) | OAuth Store and Key Ring Interfaces | Accepted and Implemented | 2026-05-09 00:26:48 +0800 | 2026-05-10 14:11:18 +0800 |
| [0007](0007-anp-adapter-boundary.md) | ANP Adapter Boundary | Accepted and Implemented | 2026-05-18 08:38:37 +0800 | 2026-05-22 00:27:39 +0800 |
| [0008](0008-p4-strategic-posture.md) | P4 Strategic Posture (Storage, TLS, P2P Auth) | Accepted and Implemented | 2026-05-29 21:05:06 +0800 | - |
| [0009](0009-5-loop-governance-system.md) | 5-Loop Governance System | Accepted and Implemented | 2026-05-27 to 2026-05-29 | - |
| [0010](0010-circular-dependencies.md) | Resolve Circular Dependencies Between approval_manager.py and policy.py | Superseded | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| [0011](0011-approval-manager-refactoring.md) | Refactor ApprovalManager to Follow Single Responsibility Principle | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| [0012](0012-tight-coupling.md) | Reduce Tight Coupling in chat_agent.py | Superseded | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| [0013](0013-backend-abstraction.md) | Add Abstraction Layer for Backend Systems | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| [0014](0014-error-handling.md) | Standardize Error Handling Across Modules | Archived | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| [0015](0015-configuration-plugin.md) | Replace Hard-coded Configuration with Plugin System | Rejected | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| [0016](0016-tool-dependency-injection.md) | Add Dependency Injection for Tool Registration | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| [0017](0017-backend-adapter-interfaces.md) | Standardize Backend Adapter Interfaces | Archived | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| [0018](0018-async-from-sync-pattern.md) | Async from Sync Pattern | Accepted and Implemented | 2026-05-31 18:53:13 +0800 | 2026-06-04 13:18:00 +0800 |
| [0019](0019-phase-4-federated-swarm-consensus.md) | Phase 4 - Federated Swarm Consensus & Peer Attestations | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| [0020](0020-phase-5-hardened-sandbox-virtualization.md) | Phase 5 - Hardened Sandbox Virtualization | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| [0021](0021-phase-6-skill-writer-docker-monitor-control-plane.md) | Phase 6 - Skill Writer, Docker Monitor, Control Plane | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| [0022](0022-centralized-approval-queue-subagents.md) | Centralized Approval Queue for Subagents | Accepted and Implemented | 2026-05-29 | - |
| [0023](0023-strict-plan-before-write-enforcement.md) | Strict Plan-Before-Write Enforcement | Accepted and Implemented | 2026-05-29 | - |
| [0024](0024-automated-memory-invalidation.md) | Automated Memory Invalidation | Accepted and Implemented | 2026-05-29 | - |
| [0025](0025-chat-session-controller-unification.md) | Shared ChatSessionController for Chat Surfaces | Accepted and Implemented | 2026-06-01 | 2026-06-04 13:18:00 +0800 |
| [0026](0026-cli-execution-abstraction-layer.md) | CLI Execution Abstraction Layer | Accepted | - | - |
| [0027](0027-context-bus-architecture.md) | Context Bus Architecture | Accepted | - | - |
| [0028](0028-tournament-swarm-architecture.md) | Tournament and Swarm Execution | Accepted | - | - |
| [0029](0029-consensus-validation-deferred.md) | Consensus Validation Deferred Behind Approval Queue | Closed — Option D executed | 2026-06-10 | 2026-07-22 |
| [0030](0030-root-module-freeze.md) | Root Module Freeze and Canonical Package Homes | Accepted | 2026-06-10 | - |
| [0031](0031-shadow-mode-exit-criteria.md) | Shadow Mode Exit Criteria | Proposed | 2026-06-12 | 2026-09-29 (expiry review; extended 2026-09-15 conditioned on G1–G5) |
| [0032](0032-run-event-taxonomy.md) | Run Event Taxonomy and Event Spine | Accepted and Implemented | 2026-06-13 | 2026-06-17 |
| [0040](0040-second-framework-invariants.md) | Reconcile the Second Execution Framework with the Primary Runner | Accepted | 2026-06-20 | - |
| [0041](0041-execution-surface-unification-and-harness-thinning.md) | Execution Surface Unification and Harness Thinning | Accepted | 2026-06-30 | 2026-06-30 |
| [0042](0042-shell-mutation-reversibility-boundary.md) | Shell-Mutation Reversibility Boundary (SEC-11) | Accepted | 2026-07-01 | 2027-01-01 (expiry review) |
| [0043](0043-legacy-competitive-surface-quarantine.md) | Legacy-Competitive Surface Quarantine (Non-Goal Retention) | Accepted — quarantine declared 2026-09-09 | 2026-09-09 | 2026-12-09 (expiry review) |

## ADR Categories

### Core Framework (0001-0003)
- **0001**: P0 Agent Harness Framework - Foundation governance primitives
- **0002**: P1 Primitives - Trace recording, context compaction, eval framework, RAG
- **0003**: Code Mode Child-Process Sandbox - AST-validated code execution

### Authentication & Security (0004-0008)
- **0004**: OAuth 2.1 + DPoP with Optional Dependencies - Authentication for MCP
- **0005**: MCP Streamable HTTP Transport - MCP server implementation
- **0006**: OAuth Store and Key Ring Interfaces - Durable OAuth persistence
- **0007**: ANP Adapter Boundary - External federation boundary
- **0008**: P4 Strategic Posture - Storage, TLS, P2P auth posture

### Execution Architecture (0040-0041)
- **0040**: Reconcile the Second Execution Framework with the Primary Runner - Shared-invariant contract and CI gates
- **0041**: Execution Surface Unification and Harness Thinning - Shared governed-execution layer; domain migration to skills/model

### Governance Hardening (0009, 0022-0024, 0029, 0031-0032, 0042)
- **0009**: 5-Loop Governance System - Comprehensive governance loops
- **0022**: Centralized Approval Queue for Subagents - Batch approval management
- **0023**: Strict Plan-Before-Write Enforcement - Plan validation
- **0024**: Automated Memory Invalidation - Memory hygiene
- **0029**: Consensus Validation Deferred Behind Approval Queue - deleted/quarantined unwired validation module; recovery record retained
- **0031**: Shadow Mode Exit Criteria - Policy/RBAC shadow→enforce promotion path
- **0032**: Run Event Taxonomy and Event Spine - Unified run-lifecycle event contract
- **0042**: Shell-Mutation Reversibility Boundary (SEC-11) - Two-tier undo (git-sandbox transactional rollback + disclosed journal fallback); external effects out of scope by design

### Multi-Agent & Swarm (0019)
- **0019**: Phase 4 - Federated Swarm Consensus & Peer Attestations - Swarm coordination

### Sandbox Virtualization (0020)
- **0020**: Phase 5 - Hardened Sandbox Virtualization - Docker/WASM isolation

### Operational Tooling (0021)
- **0021**: Phase 6 - Skill Writer, Docker Monitor, Control Plane - Operational tooling

### Refactoring Decisions (0010-0018)
- **0011, 0013, 0016, 0018**: Implemented or accepted refactoring decisions (see individual ADRs for details)
- **0010, 0012, 0014, 0015, 0017**: Closed decisions (Superseded, Archived, or Rejected)

### Chat Surfaces (0025)
- **0025**: Shared ChatSessionController for Chat Surfaces - REPL and TUI
  execution, cost, result display, and undo behavior share one controller.

## ADR Status Legend

- **Accepted and Implemented**: Decision accepted and fully implemented
- **Accepted and Implemented (Beta)**: Decision accepted and implemented in Beta (optional hardening remaining)
- **Superseded / Archived / Rejected**: Closed decisions with details in respective files
- **Proposed**: Decision recorded; implementation not yet started or incomplete (see ADR-0031).

## Git History

All ADRs include detailed git history with:
- Creation timestamp and commit hash
- Implementation timeline with key commits
- File changes and test coverage
- Verification commands

## References

- [Architecture Documentation](../architecture.md)
- [Governance Hardening Plan](../plans/governance-hardening.md)
- [Backlog Priority](../backlog-priority.md)
- [Threat Model](../threat-model.md)

## ADR Template

When creating new ADRs, use the following template:

```markdown
# ADR XXXX: [Title]

## Status

[Accepted/Proposed/Rejected/Deprecated]

## Context

[Describe the context and problem statement]

## Decision

[Describe the decision made]

## Rationale

[Explain why this decision was made]

## Implementation

[Describe the implementation details with git history]

## Consequences

[Describe the positive and negative consequences]

## Alternatives Considered

[List alternatives and why they were rejected]

## References

[Link to related ADRs, documentation, or external resources]
```
