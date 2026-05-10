# ADR 0004: OAuth 2.1 + DPoP with Optional Dependencies

## Status

Accepted for P2 implementation.

## Decision

Implement OAuth 2.1 Authorization Server and Resource Server with DPoP
proof-of-possession directly in TeaAgent, using a zero-dependency HMAC-SHA256
core with optional `cryptography` library for asymmetric DPoP signature
verification (ES256/RS256).

## Rationale

- MCP Streamable HTTP requires authentication for non-loopback binds.
  The minimal viable option is a bearer token, but bearer tokens are
  replayable by any network observer.
- DPoP (RFC 9449) binds access tokens to a client-generated asymmetric key pair,
  preventing token replay. This is the only OAuth extension that materially
  improves MCP transport security without requiring TLS.
- HS256 is the only JWT algorithm available without `cryptography`. When DPoP
  is disabled, HS256 access tokens are sufficient for the bearer token use case.
- The optional-dependency design (`pip install teaagent[oauth]`) keeps the
  P0 zero-dependency posture intact while making DPoP available on demand.

## Consequences

- The module was split into `oauth21/` submodules (`_jwt.py`, `_dpop.py`,
  `_types.py`, `_server.py`, `_resource.py`, `_pkce.py`) at 851 lines for
  maintainability.
- Internal state (clients, codes, nonces) is in-memory dicts. Multi-process
  or persistent deployments require an external store.
- Key rotation, refresh tokens, and external client storage are deferred to
  a future production-hardening ADR.
- The `cryptography` import is conditional (`HAS_CRYPTOGRAPHY` flag);

## Post-Implementation (2026-05-10)

Key rotation and external client storage have been implemented:
- `OAuthKeyRing.rotate` with configurable rotation overlap window, `key_for_validation` JWT `kid`-based lookup, and `--oauth-rotation-window` CLI (`teaagent/oauth21/_store.py`).
- Cross-host persistence via `PostgreSQLOAuthStore` and `RedisOAuthStore` with atomic consume semantics (`teaagent/oauth21/_pg_store.py`, `teaagent/oauth21/_redis_store.py`).

Refresh tokens remain deferred — the current OAuth flow uses access tokens with configurable duration only.

## Alternatives Considered

- **Authlib**: Adds 10+ dependencies; overkill for a single JWT sign/verify
  plus DPoP validation.
- **PyJWT**: HMAC-only JWT is 20 lines; adding a dependency for it is waste.
- **TLS-only (no DPoP)**: Rejected because the MCP server is designed to run
  behind a reverse proxy and DPoP protects against replay even after TLS
  termination.
