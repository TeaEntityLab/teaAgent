[README.md#A828]
# Architecture Decision Records (ADR)

This directory contains all Architecture Decision Records (ADRs) for the TeaAgent project. ADRs document significant architectural decisions, their rationale, and consequences.

## ADR Index

| Number | Title | Status | Created | Last Updated |
|--------|-------|--------|---------|--------------|
| 0001 | P0 Agent Harness Framework | Accepted and Implemented | 2026-05-08 00:31:33 +0800 | 2026-05-22 00:27:39 +0800 |
| 0002 | P1 Primitives | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | - |
| 0003 | Code Mode Child-Process Sandbox | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | 2026-05-14 18:40:37 +0800 |
| 0004 | OAuth 2.1 + DPoP with Optional Dependencies | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | 2026-05-22 01:03:20 +0800 |
| 0005 | MCP Streamable HTTP Transport | Accepted and Implemented | 2026-05-08 23:54:34 +0800 | - |
| 0006 | OAuth Store and Key Ring Interfaces | Accepted and Implemented | 2026-05-09 00:26:48 +0800 | 2026-05-10 14:11:18 +0800 |
| 0007 | ANP Adapter Boundary | Accepted and Implemented | 2026-05-18 08:38:37 +0800 | 2026-05-22 00:27:39 +0800 |
| 0008 | P4 Strategic Posture (Storage, TLS, P2P Auth) | Accepted and Implemented | 2026-05-29 21:05:06 +0800 | - |
| 0009 | 5-Loop Governance System | Accepted and Implemented | 2026-05-27 to 2026-05-29 | - |
| 0010 | Resolve Circular Dependencies Between approval_manager.py and policy.py | Superseded | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| 0011 | Refactor ApprovalManager to Follow Single Responsibility Principle | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| 0012 | Reduce Tight Coupling in chat_agent.py | Superseded | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| 0013 | Add Abstraction Layer for Backend Systems | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| 0014 | Standardize Error Handling Across Modules | Archived | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| 0015 | Replace Hard-coded Configuration with Plugin System | Rejected | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| 0016 | Add Dependency Injection for Tool Registration | Accepted and Implemented | 2026-05-30 20:00:08 +0800 | 2026-06-01 16:01:28 +0800 |
| 0017 | Standardize Backend Adapter Interfaces | Archived | 2026-05-30 20:00:08 +0800 | 2026-06-04 13:18:00 +0800 |
| 0018 | Async from Sync Pattern | Accepted and Implemented | 2026-05-31 18:53:13 +0800 | 2026-06-04 13:18:00 +0800 |
| 0019 | Phase 4 - Federated Swarm Consensus & Peer Attestations | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| 0020 | Phase 5 - Hardened Sandbox Virtualization | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| 0021 | Phase 6 - Skill Writer, Docker Monitor, Control Plane | Accepted and Implemented (Beta) | 2026-05-27 to 2026-05-29 | - |
| 0022 | Centralized Approval Queue for Subagents | Accepted and Implemented | 2026-05-29 | - |
| 0023 | Strict Plan-Before-Write Enforcement | Accepted and Implemented | 2026-05-29 | - |
| 0024 | Automated Memory Invalidation | Accepted and Implemented | 2026-05-29 | - |
| 0025 | Shared ChatSessionController for Chat Surfaces | Accepted and Implemented | 2026-06-01 | 2026-06-04 13:18:00 +0800 |
| 0029 | Consensus Validation Deferred Behind Approval Queue | Accepted | 2026-06-10 | 2026-12-10 (expiry review) |
| 0031 | Shadow Mode Exit Criteria | Proposed | 2026-06-12 | 2026-09-12 (expiry review) |
| 0032 | Run Event Taxonomy and Event Spine | Accepted and Implemented | 2026-06-13 | 2026-06-17 |
| 0040 | Reconcile the Second Execution Framework with the Primary Runner | Accepted | 2026-06-20 | - |
| 0041 | Execution Surface Unification and Harness Thinning | Proposed | 2026-06-30 | - |

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

### Governance Hardening (0009, 0022-0024, 0029, 0031-0032)
- **0009**: 5-Loop Governance System - Comprehensive governance loops
- **0022**: Centralized Approval Queue for Subagents - Batch approval management
- **0023**: Strict Plan-Before-Write Enforcement - Plan validation
- **0024**: Automated Memory Invalidation - Memory hygiene
- **0029**: Consensus Validation Deferred Behind Approval Queue - Consensus gate deferral
- **0031**: Shadow Mode Exit Criteria - Policy/RBAC shadow→enforce promotion path
- **0032**: Run Event Taxonomy and Event Spine - Unified run-lifecycle event contract

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
- **Proposed**: Decision recorded; implementation not yet started or incomplete (see ADR-0031, ADR-0041).

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
