# Decision Index

All Architecture Decision Records for TeaAgent, in sequence.  
Canonical ADR source: `docs/adr/` (ADRs 0001–0025) and `docs/decisions/` (ADRs 0026–0030).

| # | Title | Status | Date | Theme |
|---|-------|--------|------|-------|
| [0001](../adr/0001-p0-framework.md) | P0 Agent Harness Framework | Accepted | 2026-05-08 | Core |
| [0002](../adr/0002-p1-primitives.md) | P1 Trace, Eval, In-Memory RAG Primitives | Accepted | 2026-05-08 | Core |
| [0003](../adr/0003-p2-code-mode-sandbox.md) | Code Mode Child-Process Sandbox | Accepted | 2026-05-08 | Security |
| [0004](../adr/0004-oauth-dpop.md) | OAuth 2.1 + DPoP with Optional Crypto | Accepted | 2026-05-08 | Auth |
| [0005](../adr/0005-mcp-streamable-http.md) | MCP Streamable HTTP Transport | Accepted | 2026-05-08 | Protocol |
| [0006](../adr/0006-oauth-store-keyring.md) | OAuth Store and Key Ring Interfaces | Accepted | 2026-05-09 | Auth |
| [0007](../adr/0007-anp-adapter-boundary.md) | ANP Adapter Boundary for External Federation | Accepted | 2026-05-22 | Protocol |
| [0008](../adr/0008-p4-strategic-posture.md) | P4 Strategic Posture (Storage, TLS, P2P Auth) | Accepted | 2026-05-29 | Ops |
| [0009](../adr/0009-5-loop-governance-system.md) | 5-Loop Governance System | Accepted | 2026-05-27 | Governance |
| [0010](../adr/0010-circular-dependencies.md) | Resolve Circular Dependency: ApprovalManager / Policy | Proposed | — | Refactor |
| [0011](../adr/0011-approval-manager-refactoring.md) | ApprovalManager Single-Responsibility Split | Proposed | — | Refactor |
| [0012](../adr/0012-tight-coupling.md) | ChatAgentConfig Coupling Reduction | Proposed | — | Refactor |
| [0013](../adr/0013-backend-abstraction.md) | BackendRegistry Abstraction | Proposed | — | Refactor |
| [0014](../adr/0014-error-handling.md) | Standardised Error Handling | Proposed | — | Refactor |
| [0015](../adr/0015-configuration-plugin.md) | Plugin-Based Configuration Schema | Proposed | — | Refactor |
| [0016](../adr/0016-tool-dependency-injection.md) | Tool Dependency Injection (replace lambda closures) | Proposed | — | Refactor |
| [0017](../adr/0017-backend-adapter-interfaces.md) | Unified Backend Adapter Interfaces | Proposed | — | Refactor |
| [0018](../adr/0018-async-from-sync-pattern.md) | Async-from-Sync Bridge Pattern | Proposed | — | Refactor |
| [0019](../adr/0019-phase-4-federated-swarm-consensus.md) | Phase 4 — Federated Swarm Consensus | Accepted (Beta) | 2026-05-28 | Multi-Agent |
| [0020](../adr/0020-phase-5-hardened-sandbox-virtualization.md) | Phase 5 — Hardened Sandbox Virtualization | Accepted (Beta) | 2026-05-28 | Security |
| [0021](../adr/0021-phase-6-skill-writer-docker-monitor-control-plane.md) | Phase 6 — Skill Writer, Docker Monitor, Control Plane | Accepted (Beta) | 2026-05-28 | Ops |
| [0022](../adr/0022-centralized-approval-queue-subagents.md) | Centralized Approval Queue for Subagents | Accepted | 2026-05-29 | Governance |
| [0023](../adr/0023-strict-plan-before-write-enforcement.md) | Strict Plan-Before-Write Enforcement | Accepted | 2026-05-29 | Governance |
| [0024](../adr/0024-automated-memory-invalidation.md) | Automated Memory Invalidation | Accepted | 2026-05-29 | Memory |
| [0025](../adr/0025-chat-session-controller-unification.md) | ChatSessionController Unification | Accepted (Partial) | 2026-06-01 | Core |
| [0026](adr-0026-jsonl-persistence.md) | JSONL as Canonical Persistent Storage | Accepted | 2026-06-02 | Storage |
| [0027](adr-0027-stdlib-llm-adapter.md) | stdlib-only LLM Provider Adapter via urllib | Accepted | 2026-06-02 | Core |
| [0028](adr-0028-prompt-toolkit-tui.md) | prompt-toolkit as TUI Framework | Accepted | 2026-06-02 | UX |
| [0029](adr-0029-fcntl-single-node-concurrency.md) | fcntl File Locking for Single-Node Concurrency | Accepted | 2026-06-02 | Storage |
| [0030](adr-0030-hash-chained-audit-integrity.md) | SHA-256 HMAC Hash Chain for Audit Integrity | Accepted | 2026-06-02 | Security |

---

## Status Definitions

| Status | Meaning |
|--------|---------|
| **Accepted** | Implemented and in production |
| **Accepted (Beta)** | Implemented, gated behind feature flag or documented as beta |
| **Accepted (Partial)** | Partially implemented — remaining work tracked in a companion spec |
| **Proposed** | Decision recorded but implementation not yet started |
| **Deprecated** | Superseded; kept for historical context |
| **Rejected** | Evaluated and explicitly not adopted |

---

## Themes

| Theme | ADRs | Summary |
|-------|------|---------|
| **Core** | 0001, 0002, 0025, 0027 | Agent harness, primitives, execution unification, LLM adapter |
| **Security** | 0003, 0020, 0030 | Code sandbox, virtualization, audit integrity |
| **Auth** | 0004, 0006 | OAuth 2.1 + DPoP, token storage |
| **Protocol** | 0005, 0007 | MCP HTTP transport, ANP federation boundary |
| **Governance** | 0009, 0022, 0023 | 5-loop system, approval queue, plan enforcement |
| **Multi-Agent** | 0019 | Federated swarm consensus |
| **Storage** | 0026, 0029 | JSONL format, file locking |
| **Memory** | 0024 | Automated invalidation |
| **Ops** | 0008, 0021 | Deployment posture, skill pipeline, control plane |
| **UX** | 0028 | TUI framework |
| **Refactor** | 0010–0018 | Architecture debt reduction (proposed) |

---

## How to Write a New ADR

```
docs/decisions/adr-NNNN-short-title.md
```

Required sections: **Context**, **Decision**, **Consequences**, **Alternatives Considered**, **Rationale**, **Conditions to Reconsider**.  
Add a row to this index. Update [trade-offs.md](trade-offs.md), [technical-debt.md](technical-debt.md), or [upgrade-paths.md](upgrade-paths.md) as appropriate.
