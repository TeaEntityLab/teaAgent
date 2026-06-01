# ADR 0001: P0 Agent Harness Framework

## Status

Accepted and Implemented - 2026-05-08

## Decision

Use a small Python standard-library harness as the P0 foundation. The implementation defines portable boundaries for tools, budget enforcement, approval policy, and audit records without adopting Claude Agent SDK, OpenAI Agents SDK, Google ADK, or LangGraph yet.

## Rationale

- The repository had no existing application stack, so adding a vendor SDK would prematurely lock the architecture.
- The P0 requirements are mostly governance primitives: registry, schema validation, budget limits, destructive-tool approval, and audit trail.
- A thin harness keeps the later migration path open for MCP, ADK, Agents SDK, or Managed Agents.

## Implementation

**Git History:**
- **Created:** 2026-05-08 00:31:33 +0800
- **Commit:** `3244321ea0cac5ebace2d481ba9b7caac583a26b`
- **Message:** "Establish governance-first P0 agent harness"

**Files Added:**
- `teaagent/__init__.py` - Package initialization (19 lines)
- `teaagent/audit.py` - Audit logging (51 lines)
- `teaagent/budget.py` - Budget enforcement (18 lines)
- `teaagent/errors.py` - Error definitions (30 lines)
- `teaagent/policy.py` - Approval policy (18 lines)
- `teaagent/runner/_core.py` - Core runner (154 lines)
- `teaagent/schema.py` - Schema validation (45 lines)
- `teaagent/tools.py` - Tool registry (90 lines)
- `tests/test_p0_harness.py` - Unit tests (133 lines)

**Key Components:**
- **ToolRegistry**: Centralized tool registration with schema validation
- **BudgetEnforcer**: Iteration and tool-call limits
- **ApprovalPolicy**: 5 permission modes (READ_ONLY, WORKSPACE_WRITE, PROMPT, ALLOW, DANGER_FULL_ACCESS)
- **AuditLogger**: Per-run event logging
- **AgentRunner**: Core execution loop with injected decision function

**Tests:**
- 133 unit tests covering runner, budgets, approvals, and schemas
- All tests passing

## Consequences

- The runner is deliberately model-agnostic and uses an injected decision function.
- MCP server transport was deferred in the original P0 draft; tool metadata was structured for later MCP exposure.
- Multi-agent orchestration was explicitly deferred until a domain boundary or tool-count threshold justifies it.

## Post-Implementation (2026-05-10)

Multi-agent orchestration has been implemented across P1-r2 and P1-r3: `ManagedRuntimeAdapter` protocol and `ManagedAgentRunner` (`teaagent/managed_runtime.py`), `A2ADispatcher` for in-process routing, `A2ADiscoveryServer` for `/.well-known/agent.json` discovery, `A2AClient` for HTTP task delegation, and `FederatedAgentRegistry` for TTL-cached remote registry pulls (`teaagent/agentcard.py`).

MCP streamable HTTP transport is implemented in `teaagent/mcp_http` (see ADR 0005) with stdio transport in `teaagent/mcp_server.py`.

## Updates

**2026-05-22 00:27:39 +0800** - Harden ANP federation and opencodezen-go extraction
- Commit: `1d8d7b3555d6914e6e6a0afdcc2db747bbe63aef`
- Updated ADR to reflect ANP adapter boundary (ADR 0007)

**2026-05-10 14:11:18 +0800** - Update ADRs, CHANGELOG, and replace stale scope files with backlog-priority
- Commit: `091b27189d0c84102745828cccc6cda923067680`
- Updated ADR to reflect MCP streamable HTTP implementation
