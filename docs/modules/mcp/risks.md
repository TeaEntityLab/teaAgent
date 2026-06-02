# mcp — Risk Vectors & Known Issues

## MCP-R-001: MCP tool injection (untrusted server)
**File**: `mcp_trust.py`
**Risk**: An untrusted MCP server can advertise tools with misleading names/descriptions. If trust filtering is bypassed or incomplete, the LLM may invoke a malicious tool.
**Failure mode**: Arbitrary code execution via crafted tool call.
**Mitigation**: Default to `UNTRUSTED` for new servers; require explicit trust grant.

## MCP-R-002: `initialize()` not called guard
**File**: `mcp_client.py:30-34`
**Risk**: `initialize()` raises `MCPClientError` if the response lacks a session ID, but if the server returns a session ID and the client skips `initialize()`, `list_tools()` and `call_tool()` will fail with HTTP 400/401 from the server.
**Failure mode**: Confusing errors; no client-side guard for "not initialized" state.

## MCP-R-003: No connection timeout on MCP calls
**File**: `mcp_client.py:68-79`
**Risk**: `http.client` connections default to no timeout. A slow or hung MCP server blocks the agent indefinitely.
**Failure mode**: Agent hangs; no timeout enforcement.

## MCP-R-004: MCP server does not validate tool output
**File**: `mcp_server.py`
**Risk**: Tool handlers may return arbitrary dicts. The MCP server forwards them without output schema validation. A malformed response may cause the client's JSON parser to fail.

## MCP-R-005: OAuth token not refreshed
**File**: `mcp_http/_oauth.py`
**Risk**: OAuth 2.1 access tokens have a TTL. If a long-running session exceeds the token lifetime, MCP calls fail with 401 but the client does not automatically refresh.
**Failure mode**: MCP calls fail mid-session with no retry.

## MCP-R-006: `MCPToolAdapter` copies input_schema verbatim
**File**: `mcp_tool_adapter.py`
**Risk**: The MCP server's `input_schema` may not be valid JSON Schema (could be a Zod schema string or other format). Copying verbatim causes schema validation failures.

## MCP-R-007: `call_tool` HTTP error details truncated
**File**: `mcp_client.py:80`
**Risk**: MCPClientError messages may be truncated by the server's error body. Full debugging context is lost.
