# P0 Implementation Scope

## Included

- Single-agent orchestration loop with iteration and tool-call budgets.
- Tool registry with input/output schema validation.
- MCP-aligned tool annotations: `read_only`, `destructive`, and `idempotent`.
- Audit logging for run lifecycle, tool calls, blocked calls, errors, and final answers.
- Approval policy for destructive tools.
- Portable `AGENTS.md` and starter Skill structure.

## Deferred

- Real MCP transport and OAuth 2.1 / DPoP.
- External state store such as Postgres or Redis.
- OpenTelemetry trace export.
- Agentic RAG, A2A, and multi-agent orchestration.
- LLM-as-Judge and offline eval automation.

## Pilot Assumption

The first pilot should be a low-risk internal workflow with 3-5 tools. Destructive operations must be simulated or gated until HITL is fully integrated.
