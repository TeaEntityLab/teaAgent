# P0 Implementation Scope

## Included

- Single-agent orchestration loop with iteration and tool-call budgets.
- Tool registry with input/output schema validation.
- MCP-aligned tool annotations: `read_only`, `destructive`, and `idempotent`.
- Audit logging for run lifecycle, tool calls, blocked calls, errors, and final answers.
- Approval policy for destructive tools.
- Portable `AGENTS.md` and starter Skill structure.

## Deferred

- External state store such as Postgres or Redis.
- A2A runtime and cross-agent registry/runtime orchestration.
- LLM-as-Judge and offline eval automation.

## Implemented Since P0 Baseline

- MCP transport is available (stdio plus Streamable HTTP).
- OAuth 2.1 / DPoP primitives are implemented for authorization/resource server flows.
- OpenTelemetry integration is available through telemetry sinks.
- Agentic RAG primitives are implemented (lexical + fusion path), with advanced retrieval still iterative.

## Pilot Assumption

The first pilot should be a low-risk internal workflow with 3-5 tools. Destructive operations must be simulated or gated until HITL is fully integrated.
