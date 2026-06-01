# mcp — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/mcp_client.py` | `MCPHTTPClient` — stdlib HTTP client for MCP servers |
| `teaagent/mcp_server.py` | MCP server exposing TeaAgent tools via Streamable HTTP |
| `teaagent/mcp_tool_adapter.py` | `MCPToolAdapter` — wraps MCP server tools as `ToolDefinition` |
| `teaagent/mcp_trust.py` | `MCPTrustManager`, trust levels, tool filtering |
| `teaagent/mcp_http/__init__.py` | Constants: `MCP_PATH = '/mcp'`, `SESSION_HEADER = 'Mcp-Session-Id'` |
| `teaagent/mcp_http/_oauth.py` | OAuth 2.1 flow for authenticated MCP endpoints |
| `teaagent/stateless_mcp.py` | `StatelessMCPHandler` — no-session MCP request handler |

## Key Exports

### `mcp_client.py`
- `MCPClientError(RuntimeError)` — all MCP client errors
- `MCPHTTPClient` — `initialize()`, `list_tools()`, `call_tool()`, `close()`

### `mcp_server.py`
- `MCPServer` — `register_tool_registry(registry)`, `handle_request(body)`, `start(host, port)`

### `mcp_tool_adapter.py`
- `MCPToolAdapter` — `adapt(server_url, tool_list) -> list[ToolDefinition]`

### `mcp_trust.py`
- `MCPTrustLevel` — enum: `TRUSTED`, `VERIFIED`, `UNTRUSTED`
- `MCPTrustManager` — `set_trust(server_url, level)`, `get_trust(server_url)`, `filter_tools(tools, server_url)`

## Dependencies

```
mcp_client.py
  ├── stdlib: http.client, json, urllib.parse
  └── teaagent.mcp_http (MCP_PATH, SESSION_HEADER)

mcp_server.py
  ├── teaagent.tools.ToolRegistry
  └── teaagent.mcp_http._oauth (optional)

mcp_tool_adapter.py
  └── teaagent.tools (ToolDefinition, ToolAnnotations)
```

## Entry Points

1. `cli/_handlers/_mcp.py` — `mcp_add_command`, `mcp_list_command`, `mcp_serve_command`
2. `runner/_core.py` — loads MCP server URLs from config, adapts their tools into the registry
3. `chat_session_controller.py` — may load MCP tools for chat sessions

## Call Graph (client side)

```
runner._core startup
  MCPHTTPClient(endpoint).initialize()
  MCPHTTPClient.list_tools()
  MCPToolAdapter.adapt(server_url, tool_list)
    └── ToolRegistry.register(ToolDefinition(...))

runner._core per-tool-call
  ToolRegistry.call('mcp_tool_name', arguments)
    └── MCPHTTPClient.call_tool(name, arguments)
          └── http.client POST /mcp
```
