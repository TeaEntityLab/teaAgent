# Top-level API Migration Note

This release narrows `teaagent` top-level exports (`teaagent.__all__`) to a stable core surface.

## What changed

- `from teaagent import *` now exports only core runtime symbols.
- Advanced utilities and subsystem-specific symbols remain importable from their module paths.

## Recommended migration

- Replace star imports with explicit imports.
- Import non-core symbols from submodules, for example:

```python
from teaagent.graph_rag import KnowledgeGraph
from teaagent.oauth21 import OAuth21AuthorizationServer
from teaagent.telemetry import TelemetryConfig
```

## Removed from `teaagent.__all__`

- AIBOM/skill/eval: `AIBOMManifest`, `EvalCase`, `EvalReport`, `SkillReviewResult`, `build_aibom`, `review_skill`, `run_eval`
- Retrieval and graph: `Document`, `GraphEdge`, `InMemoryRetriever`, `KnowledgeGraph`, `agentic_retrieve`, `graph_retrieve`
- LLM internals: `LLMMessage`, `LLMRequest`, `LLMResponse`, `ProviderConfig`, `check_llm_configuration`, `create_llm_adapter`, `route_model`
- OAuth/DPoP: `OAuth21AuthorizationServer`, `OAuth21ResourceServer`, `OAuthStore`, `SQLiteOAuthStore`, `create_jwt`, `verify_jwt`
- Telemetry: `TelemetryConfig`, `OTelAuditSink`, `OTelMetricsSink`, `configure_telemetry`, `configure_metrics`
- MCP/transport extras: `build_mcp_http_server`, `serve_mcp_http`, `serve_mcp_stdio`, `handle_mcp_request`, `handle_stateless_tool_request`

This change only affects top-level export convenience. Module-level imports continue to work.
