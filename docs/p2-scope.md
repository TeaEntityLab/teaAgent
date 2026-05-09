# P2 Implementation Scope

## Included

- In-memory Graph RAG primitives for entity/relation traversal and document retrieval.
- Restricted Code Mode with AST allow-list validation and a replaceable backend interface. The default backend runs in a child-process sandbox with CPU-time, wall-clock timeout, and best-effort memory limits (RLIMIT_AS/RLIMIT_CPU via `resource`); `ContainerCodeModeBackend` can route execution through Docker/Podman-style runtimes with disabled networking, read-only rootfs, dropped capabilities, no-new-privileges, non-root user, tmpfs `/tmp`, memory/swap limits, CPU ulimit, and PID limit.
- Stateless MCP request/response envelopes that carry capabilities and shared state per request.
- Streamable HTTP transport for the MCP server with `Mcp-Session-Id` sessions, bearer-token/OAuth guardrails for non-loopback binds enforced at both the CLI and library level (`build_mcp_http_server` raises `ValueError` when bound to a non-loopback host without auth), and Origin allowlist (POST/GET/DELETE on `/mcp`).
- Managed-agent readiness checks for tool metadata, audit, budget, external state, and HITL gaps.
- Provider portability checks for tool calling, structured output, system prompt support, prompt caching, and context limits.
- Cross-provider live model conformance with layered `smoke` (non-empty response) and `contract` (exact content match, system-prompt adherence, token-budget reporting) tiers via `run_tiered_conformance`.

## Still Deferred

- Production GraphQLite deployment, migrations, and Cypher query tuning.
- Strong production sandboxing for Code Mode beyond the current container command boundary: image digest pinning, seccomp/AppArmor/SELinux profiles, V8 isolates, VM sandboxes, or a managed execution service.
- Production hardening for OAuth 2.1 / DPoP deployments, including key rotation and external client storage.
- Actual managed runtime integration with Anthropic, OpenAI, Google ADK, or Vertex Agent Engine.
- Extended cross-provider conformance tiers for streaming, structured output, tool calling, latency budgets, and provider-specific safety/block taxonomy.

## P2 Extension Rules

- Keep Graph RAG storage replaceable; `KnowledgeGraph` is a contract sketch and `GraphQLiteGraphStore` is the SQLite-backed implementation path.
- Keep Code Mode limited to safe transformations and never expose filesystem, imports, attributes, or arbitrary function calls.
- Treat Code Mode backends as a policy boundary: production deployments should prefer an external runtime backend over the default child process backend.
- Route future stateless MCP transport through `handle_stateless_tool_request()` so schema validation remains centralized in `ToolRegistry`.
- Run provider portability checks before adopting a new model/provider for production workflows.
