# MCP Server API Specification

**Protocol version:** `2024-11-05`  
**Transport:** stdin/stdout JSON-RPC 2.0  
**Entry point:** `teaagent mcp serve`  
**Source:** `teaagent/mcp_server.py`, `teaagent/tools.py`

---

## Server Info

```json
{
  "name": "teaagent",
  "version": "0.1.0",
  "protocolVersion": "2024-11-05"
}
```

---

## Protocol Overview

The MCP server uses the [Model Context Protocol](https://modelcontextprotocol.io/) over stdin/stdout JSON-RPC 2.0. Clients (LLMs, orchestrators) send requests; the server responds with tool results or resource contents.

### Request Format

```json
{
  "jsonrpc": "2.0",
  "id": "string | number",
  "method": "string",
  "params": { ... }
}
```

### Response Format

```json
{
  "jsonrpc": "2.0",
  "id": "string | number",
  "result": { ... }
}
```

### Error Format

```json
{
  "jsonrpc": "2.0",
  "id": "string | number",
  "error": {
    "code": -32000,
    "message": "Human-readable error",
    "data": { "tool": "tool_name", "details": "..." }
  }
}
```

---

## Lifecycle Methods

### `initialize`

Negotiate protocol version and capabilities.

**Request:**
```json
{
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": { "name": "client", "version": "1.0.0" },
    "capabilities": {}
  }
}
```

**Response:**
```json
{
  "protocolVersion": "2024-11-05",
  "serverInfo": { "name": "teaagent", "version": "0.1.0" },
  "capabilities": {
    "tools": {},
    "resources": {}
  }
}
```

---

### `notifications/initialized`

Sent by the client after `initialize` completes. No response expected.

---

## Tool Methods

### `tools/list`

List all registered tools.

**Response:**
```json
{
  "tools": [
    {
      "name": "string",
      "description": "string",
      "inputSchema": {
        "type": "object",
        "properties": { ... },
        "required": [ ... ]
      },
      "annotations": {
        "readOnly": true,
        "destructive": false,
        "idempotent": true,
        "stateful": false,
        "securityTier": "Low | Medium | High | Critical"
      }
    }
  ]
}
```

---

### `tools/call`

Invoke a registered tool.

**Request:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": { ... }
  }
}
```

**Response (success):**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Tool output as a string"
    }
  ],
  "isError": false
}
```

**Response (tool error):**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error description"
    }
  ],
  "isError": true
}
```

**JSON-RPC error codes for tool/call:**

| Code | Meaning |
|------|---------|
| `-32601` | Method not found (unknown tool name) |
| `-32602` | Invalid params (schema validation failed) |
| `-32000` | Tool execution error |
| `-32001` | Approval denied |
| `-32002` | Rate limit exceeded |
| `-32003` | Workspace lock conflict |

---

## Resource Methods

### `resources/list`

List available resources.

**Response:**
```json
{
  "resources": [
    {
      "uri": "teaagent://workspace/<path>",
      "name": "string",
      "description": "string",
      "mimeType": "text/plain | application/json"
    }
  ]
}
```

---

### `resources/read`

Read a resource by URI.

**Request:**
```json
{
  "method": "resources/read",
  "params": {
    "uri": "teaagent://workspace/src/auth.py"
  }
}
```

**Response:**
```json
{
  "contents": [
    {
      "uri": "teaagent://workspace/src/auth.py",
      "mimeType": "text/plain",
      "text": "file contents..."
    }
  ]
}
```

---

## Tool Annotations Schema

Each registered tool carries annotations that control approval and display:

```json
{
  "readOnly": false,
  "destructive": true,
  "idempotent": false,
  "stateful": true,
  "securityTier": "High"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `readOnly` | bool | Tool never mutates state |
| `destructive` | bool | Tool may delete or overwrite data |
| `idempotent` | bool | Calling twice has the same effect as once |
| `stateful` | bool | Tool modifies persistent external state |
| `securityTier` | enum | `Low`, `Medium`, `High`, `Critical` |

**Security tier meanings:**

| Tier | Description |
|------|-------------|
| `Low` | Read-only, no external side-effects |
| `Medium` | Writes to workspace only |
| `High` | Writes to external systems or executes shell |
| `Critical` | Irreversible or affects production systems |

---

## Workspace Registry

The MCP server manages a global workspace registry to prevent concurrent access conflicts.

**Registry location:** `~/.teaagent/workspace_registry.json`

**Lock record:**
```json
{
  "workspace_path": "/abs/path/to/project",
  "owner_pid": 12345,
  "acquired_at": "2026-06-02T10:00:00Z"
}
```

**Acquisition:** `WorkspaceRegistry.acquire_lock(workspace_path)` — acquires with zombie-process cleanup (a lock held by a dead PID is automatically released).

**Release:** `WorkspaceRegistry.release_lock(workspace_path)` — releases on clean MCP server shutdown.

---

## Rate Limiting

Tools can declare a rate limit via `ToolRateLimit`:

```json
{
  "maxCalls": 10,
  "windowSeconds": 60.0
}
```

When the rate limit is exceeded, `tools/call` returns JSON-RPC error code `-32002`:

```json
{
  "code": -32002,
  "message": "Rate limit exceeded for tool 'shell_exec': 10 calls per 60s"
}
```

---

## Trust Model

The MCP server applies teaagent's approval policy to all `tools/call` requests. Tools marked `destructive: true` require one of:

1. `permission_mode` set to `allow` or `danger-full-access`, **or**
2. a live JIT/session approval, scoped approval grant, or payload-digest preapproval matching the exact tool call, **or**
3. an interactive approval prompt (if `permission_mode` is `prompt`). `--approve-call-id` preapproval is deprecated/inert and does not satisfy this boundary.

Denied calls return JSON-RPC error `-32001` with details on which rule blocked the call.

---

## Starting the MCP Server

```bash
teaagent mcp serve
```

The server reads from stdin and writes to stderr. Clients connect via stdio transport as per the MCP specification.

**With a specific workspace root:**
```bash
teaagent mcp serve --root /path/to/project
```

**With a permission mode:**
```bash
teaagent mcp serve --permission-mode workspace-write
```

All `teaagent run` flags apply when starting the server — they set defaults for tool calls made through MCP.

---

## Trust Management

```bash
# List trusted MCP server certificates
teaagent mcp trust list

# Allow an external MCP server
teaagent mcp trust allow my-custom-server

# Block an external MCP server
teaagent mcp trust deny suspicious-server

# Inspect trust configuration for a server
teaagent mcp trust inspect my-custom-server
```
