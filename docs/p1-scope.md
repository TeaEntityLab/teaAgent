# P1 Implementation Scope

## Included

- Local trace recorder wired through `AuditLogger.add_sink()` as the replacement point for OpenTelemetry.
- Context compaction with `memory_keys` pinning for critical IDs.
- AI-BOM manifest generation for model, skills, and MCP server cards.
- Skill review checks for frontmatter, excessive SKILL.md size, and network-risk signals.
- Offline eval runner with deterministic `expected_contains` checks.
- Minimal Agentic RAG primitives: query decomposition, source routing, lexical retrieval, and RRF fusion.

## Still Deferred

- Real OpenTelemetry exporter.
- Real vector database, SQL MCP, or web search MCP integrations.
- LLM-as-Judge scoring.
- A2A runtime and AgentCard registry.
- OAuth 2.1 / DPoP enforcement.

## Extension Points

- Replace `TraceRecorder` with an OpenTelemetry sink without changing `AgentRunner`.
- Replace `InMemoryRetriever` with source-specific MCP tools while preserving `agentic_retrieve` behavior.
- Run `review_skill` and `build_aibom` in CI before accepting new skills or MCP server cards.
