# mcp — Public API Reference

## `MCPClientError(RuntimeError)`
**Location**: `mcp_client.py:10`
Raised for all MCP protocol errors: HTTP failures, missing session, tool errors.

---

## `MCPHTTPClient`
**Location**: `mcp_client.py:15`

```python
class MCPHTTPClient:
    def __init__(
        self,
        endpoint: str,           # e.g. 'http://localhost:3000'
        *,
        auth_token: Optional[str] = None,
    ) -> None: ...

    session_id: Optional[str]    # set after initialize()
```

### `initialize() -> dict[str, Any]`
- **Pre**: Not yet initialized.
- **Post**: `session_id` is set. Returns server capabilities dict.
- **Raises**: `MCPClientError` if response lacks session ID or HTTP fails.

### `list_tools() -> list[dict[str, Any]]`
- **Pre**: `initialize()` called.
- **Returns**: List of tool dicts from `tools/list` response.

### `call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]`
- **Pre**: `initialize()` called.
- **Returns**: Tool result dict.
- **Raises**: `MCPClientError` if `isError: true` or HTTP fails.

### `close() -> None`
- Sends DELETE to session URL.
- Clears `session_id`.
- Accepts 204 (closed) or 404 (already gone).

---

## `MCPTrustLevel` (Enum)
**Location**: `mcp_trust.py`

```python
class MCPTrustLevel(str, Enum):
    TRUSTED = 'trusted'       # full tool access
    VERIFIED = 'verified'     # curated tool access
    UNTRUSTED = 'untrusted'   # filtered, no sensitive tool names
```

---

## `MCPTrustManager`
**Location**: `mcp_trust.py`

```python
class MCPTrustManager:
    def set_trust(self, server_url: str, level: MCPTrustLevel) -> None
    def get_trust(self, server_url: str) -> MCPTrustLevel  # default: UNTRUSTED
    def filter_tools(
        self, tools: list[dict], server_url: str
    ) -> list[dict]  # removes blocked tools for trust level
```

---

## MCP Protocol Constants
**Location**: `mcp_http/__init__.py`

```python
MCP_PATH = '/mcp'
SESSION_HEADER = 'Mcp-Session-Id'
```

---

## Wire Protocol (JSON-RPC 2.0)

### Initialize
```json
POST /mcp
{"jsonrpc": "2.0", "id": 1, "method": "initialize"}

Response header: Mcp-Session-Id: <session_id>
Response body: {"jsonrpc": "2.0", "id": 1, "result": {...capabilities}}
```

### List Tools
```json
POST /mcp (with Mcp-Session-Id header)
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

Response: {"result": {"tools": [{"name": "...", "description": "...", "inputSchema": {...}}]}}
```

### Call Tool
```json
POST /mcp
{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
 "params": {"name": "tool_name", "arguments": {...}}}

Response: {"result": {"content": [...], "isError": false}}
```
