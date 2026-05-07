# P0 Agent Harness Reference

## Extension Rules

- Add new tools by defining schemas, annotations, and a handler, then registering them with `ToolRegistry.register`.
- Do not bypass `ToolRegistry.execute`; that is where P0 schema validation happens.
- Add new high-risk operations as destructive tools and require approval by exact `call_id`.
- Keep model-provider integrations outside `AgentRunner`; inject decisions through the `decide` callable.

## Deferred Integrations

- MCP transport should expose `ToolRegistry.mcp_metadata()` and route calls back through `ToolRegistry.execute()`.
- OpenTelemetry should subscribe to `AuditLogger` events or replace the logger with a compatible sink.
- External state should persist `context`, observations, and checkpoints between iterations.
