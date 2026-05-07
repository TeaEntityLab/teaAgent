# P2 Implementation Scope

## Included

- In-memory Graph RAG primitives for entity/relation traversal and document retrieval.
- Restricted Code Mode for deterministic local data manipulation with AST allow-list validation.
- Stateless MCP request/response envelopes that carry capabilities and shared state per request.
- Managed-agent readiness checks for tool metadata, audit, budget, external state, and HITL gaps.
- Provider portability checks for tool calling, structured output, system prompt support, prompt caching, and context limits.

## Still Deferred

- Real graph database integration such as Neo4j.
- Production sandboxing for Code Mode using containers, V8 isolates, or a managed execution service.
- Live MCP Streamable HTTP transport and OAuth 2.1 / DPoP enforcement.
- Actual managed runtime integration with Anthropic, OpenAI, Google ADK, or Vertex Agent Engine.
- Cross-provider live conformance tests.

## P2 Extension Rules

- Keep Graph RAG storage replaceable; `KnowledgeGraph` is a contract sketch, not the production store.
- Keep Code Mode limited to safe transformations and never expose filesystem, imports, attributes, or arbitrary function calls.
- Route future stateless MCP transport through `handle_stateless_tool_request()` so schema validation remains centralized in `ToolRegistry`.
- Run provider portability checks before adopting a new model/provider for production workflows.
