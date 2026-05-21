# P0 Agent Harness Reference

## Extension Rules

- Add new tools by defining schemas, annotations, and a handler, then registering them with `ToolRegistry.register`.
- Do not bypass `ToolRegistry.execute`; that is where P0 schema validation happens.
- Add new high-risk operations as destructive tools and require approval by exact `call_id`.
- Keep model-provider integrations outside `AgentRunner`; inject decisions through the `decide` callable.

## Implemented Integrations

- MCP stdio and streamable HTTP transports expose `ToolRegistry.mcp_metadata()` and route calls through `ToolRegistry.execute()` (`teaagent/mcp_server.py`, `teaagent/mcp_http`).
- OpenTelemetry hooks subscribe to audit events when the `telemetry` extra is installed (`teaagent/telemetry`).
- External checkpoints persist `context`, observations, and run state via `CheckpointStore` (`teaagent/checkpoint.py`, `--checkpoint-store` CLI).
- ANP federation uses `ANPGovernedService` so inbound tool calls still pass approval, audit, and budget enforcement (`teaagent/anp_adapter.py`).
