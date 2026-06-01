# mcp — Behavior Specification

## Purpose

Implements the Model Context Protocol (MCP) for bidirectional tool discovery and invocation. Acts as both MCP client (consuming external MCP servers) and MCP server (exposing TeaAgent tools to external clients).

## Behavior Contract

### MCP Client (`mcp_client.py`)
1. **Session lifecycle** — `initialize()` must be called first; returns server capabilities and stores `session_id`.
2. **Tool discovery** — `list_tools()` returns the server's available tools.
3. **Tool invocation** — `call_tool(name, arguments)` invokes a server tool; `isError: true` results raise `MCPClientError`.
4. **Session close** — `close()` sends DELETE to terminate the session; accepts 204 or 404 (already closed).
5. **Transport** — stdlib `http.client` only, no third-party HTTP libraries. Supports `http` and `https`.

### MCP Server (`mcp_server.py`)
1. **JSON-RPC 2.0** — all messages follow JSON-RPC protocol over Streamable HTTP.
2. **Session management** — each client gets a `Mcp-Session-Id` header; stateless requests include session in path or header.
3. **Tool registration** — TeaAgent's `ToolRegistry` tools are exposed as MCP tools; input_schema is forwarded as-is.
4. **OAuth** — `mcp_http/_oauth.py` handles OAuth 2.1 authorization for authenticated MCP servers.

### Trust (`mcp_trust.py`)
1. **Trust levels** — each MCP server has a trust level: `TRUSTED`, `VERIFIED`, `UNTRUSTED`.
2. **Tool filtering** — untrusted servers cannot register tools that match sensitive name patterns.
3. **Capability scope** — trusted servers get full tool access; others are scoped.

### Stateless MCP (`stateless_mcp.py`)
1. **Single-shot** — no session state; each request is self-contained.
2. **Use case** — CI/batch environments where session management overhead is not needed.

## Invariants

- `MCPHTTPClient.initialize()` must be called before `list_tools()` or `call_tool()`.
- `session_id` is set after `initialize()` and cleared after `close()`.
- `call_tool()` with `isError: true` always raises `MCPClientError`, never returns.
- MCP server tool names must match the TeaAgent `ToolDefinition.name`.
