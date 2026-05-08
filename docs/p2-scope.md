# P2 Implementation Scope

## Included

- In-memory Graph RAG primitives for entity/relation traversal and document retrieval.
- Restricted Code Mode for deterministic local data manipulation with AST allow-list validation and child-process timeout/resource guardrails.
- Stateless MCP request/response envelopes that carry capabilities and shared state per request.
- Streamable HTTP transport for the MCP server with `Mcp-Session-Id` sessions, bearer-token/OAuth guardrails for non-loopback binds, and Origin allowlist (POST/GET/DELETE on `/mcp`).
- Managed-agent readiness checks for tool metadata, audit, budget, external state, and HITL gaps.
- Provider portability checks for tool calling, structured output, system prompt support, prompt caching, and context limits.
- Cross-provider live model conformance smoke checks with per-provider pass/fail/skip reporting.

## Still Deferred

- Production GraphQLite deployment, migrations, and Cypher query tuning.
- Strong production sandboxing for Code Mode using containers, V8 isolates, or a managed execution service.
- Production hardening for OAuth 2.1 / DPoP deployments, including key rotation and external client storage.
- Actual managed runtime integration with Anthropic, OpenAI, Google ADK, or Vertex Agent Engine.
- Deeper cross-provider conformance for streaming, structured output, tool calling, and provider-specific safety blocks.

## P2 Extension Rules

- Keep Graph RAG storage replaceable; `KnowledgeGraph` is a contract sketch and `GraphQLiteGraphStore` is the SQLite-backed implementation path.
- Keep Code Mode limited to safe transformations and never expose filesystem, imports, attributes, or arbitrary function calls.
- Route future stateless MCP transport through `handle_stateless_tool_request()` so schema validation remains centralized in `ToolRegistry`.
- Run provider portability checks before adopting a new model/provider for production workflows.
