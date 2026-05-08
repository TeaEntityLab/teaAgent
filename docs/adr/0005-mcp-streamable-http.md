# ADR 0005: MCP Streamable HTTP Transport

## Status

Accepted for P2 implementation.

## Decision

Expose the TeaAgent workspace tool pack to MCP clients over stdio JSON-RPC
and Streamable HTTP (POST/GET/DELETE on `/mcp`) with `Mcp-Session-Id` session
management, bearer-token/OAuth 2.1 guardrails, and Origin allowlisting.

## Rationale

- stdio JSON-RPC (`serve_mcp_stdio`) provides zero-config integration with
  MCP clients that launch the server as a subprocess (Claude Desktop, Zed, etc.).
- Streamable HTTP (`serve_mcp_http`) enables remote IDE agents, web-based
  clients, and multi-session scenarios. It follows the MCP Streamable HTTP
  draft with SSE-based streaming on GET and JSON-RPC on POST.
- Session management via `Mcp-Session-Id` header prevents cross-session
  confusion and supports session termination via DELETE.
- Authentication is enforced at two layers:
  1. CLI layer: refuses non-loopback binds without `--auth-token` or OAuth.
  2. Library layer: `build_mcp_http_server()` raises `ValueError` on
     non-loopback binds without `auth_token` or `oauth_server`.

## Consequences

- The server uses `ThreadingHTTPServer` from stdlib with a simple in-memory
  `MCPSessionStore`. This is sufficient for single-machine use but not for
  high-concurrency production deployments.
- TLS is not implemented natively; a reverse proxy (nginx, Caddy) must
  terminate TLS for external access.
- DPoP nonce negotiation and OAuth metadata endpoints are served under the
  same HTTP handler, enabling fully featured MCP authorization.
- Batch JSON-RPC requests are supported; notifications (no `id`) return HTTP 202.

## Alternatives Considered

- **WebSocket transport**: MCP specification favors Streamable HTTP over
  WebSocket for simpler HTTP semantics. SSE provides server-to-client push
  without the WebSocket upgrade handshake.
- **gRPC**: Rejected — MCP is JSON-RPC-based; gRPC would require a separate
  protocol definition and client SDK.
- **aiohttp/FastAPI**: Rejected — adds framework dependencies for what is
  a single-path HTTP handler. `ThreadingHTTPServer` is sufficient for the
  target scale (single-digit concurrent MCP clients).
