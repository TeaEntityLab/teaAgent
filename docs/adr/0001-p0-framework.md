# ADR 0001: P0 Agent Harness Framework

## Status

Accepted for P0 implementation.

## Decision

Use a small Python standard-library harness as the P0 foundation. The implementation defines portable boundaries for tools, budget enforcement, approval policy, and audit records without adopting Claude Agent SDK, OpenAI Agents SDK, Google ADK, or LangGraph yet.

## Rationale

- The repository had no existing application stack, so adding a vendor SDK would prematurely lock the architecture.
- The P0 requirements are mostly governance primitives: registry, schema validation, budget limits, destructive-tool approval, and audit trail.
- A thin harness keeps the later migration path open for MCP, ADK, Agents SDK, or Managed Agents.

## Consequences

- The runner is deliberately model-agnostic and uses an injected decision function.
- MCP server transport is not implemented in P0; tool metadata is structured so it can be exposed through MCP later.
- Multi-agent orchestration is explicitly deferred until a domain boundary or tool-count threshold justifies it.

## Post-Implementation (2026-05-10)

Multi-agent orchestration has been implemented across P1-r2 and P1-r3: `ManagedRuntimeAdapter` protocol and `ManagedAgentRunner` (`teaagent/managed_runtime.py`), `A2ADispatcher` for in-process routing, `A2ADiscoveryServer` for `/.well-known/agent.json` discovery, `A2AClient` for HTTP task delegation, and `FederatedAgentRegistry` for TTL-cached remote registry pulls (`teaagent/agentcard.py`).
