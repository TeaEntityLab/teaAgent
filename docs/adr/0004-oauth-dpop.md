# ADR 0004: OAuth 2.1 + DPoP with Optional Dependencies

## Status

Accepted and Implemented - 2026-05-08

## Decision

Implement OAuth 2.1 Authorization Server and Resource Server with DPoP
proof-of-possession directly in TeaAgent, using a zero-dependency HMAC-SHA256
core with optional `cryptography` library for asymmetric DPoP signature
verification (ES256/RS256).

## Implementation

**Git History:**
- **Created:** 2026-05-08 23:54:34 +0800
- **Commit:** `2ab09cd8f87dbfcaf7fb9eeb4dc34be613179baa`
- **Message:** "Modularize oauth21, add gitignore-aware listing with pagination, enforce mypy strict mode"

**Updated:** 2026-05-10 14:11:18 +0800
- **Commit:** `091b27189d0c84102745828cccc6cda923067680`
- **Message:** "Update ADRs, CHANGELOG, and replace stale scope files with backlog-priority"

**Updated:** 2026-05-22 01:03:20 +0800
- **Commit:** `d4ac38d3c0890ac907886501e2cd9aa3102afab4`
- **Message:** "Implement OAuth refresh-token rotation deferred in ADR 0004"

**Files Added:**
- `teaagent/oauth21/_jwt.py` - JWT implementation
- `teaagent/oauth21/_dpop.py` - DPoP proof-of-possession
- `teaagent/oauth21/_types.py` - OAuth types
- `teaagent/oauth21/_server.py` - Authorization server
- `teaagent/oauth21/_resource.py` - Resource server
- `teaagent/oauth21/_pkce.py` - PKCE implementation

**Key Components:**
- **HMAC-SHA256 core**: Zero-dependency JWT signing
- **Optional cryptography**: Asymmetric DPoP signature verification (ES256/RS256)
- **DPoP proof-of-possession**: Binds access tokens to client key pair
- **Refresh-token rotation**: Deferred in original ADR, implemented 2026-05-22

**Tests:**
- Unit tests for OAuth 2.1 and DPoP
- E2E tests for refresh-token rotation
- All tests passing

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
- Key rotation and external client storage were deferred to ADR 0006 (now
  implemented). Refresh-token rotation was deferred here and implemented
  2026-05-22.
- The `cryptography` import is conditional (`HAS_CRYPTOGRAPHY` flag);

## Post-Implementation (2026-05-10)

Key rotation and external client storage have been implemented:
- `OAuthKeyRing.rotate` with configurable rotation overlap window, `key_for_validation` JWT `kid`-based lookup, and `--oauth-rotation-window` CLI (`teaagent/oauth21/_store.py`).
- Cross-host persistence via `PostgreSQLOAuthStore` and `RedisOAuthStore` with atomic consume semantics (`teaagent/oauth21/_pg_store.py`, `teaagent/oauth21/_redis_store.py`).

Refresh-token rotation is implemented (2026-05-22):
- Rotating refresh tokens issued on authorization-code exchange when `refresh_token_ttl > 0` (default 30 days; `--oauth-refresh-token-ttl` / `refresh_token_ttl=0` disables).
- `refresh_token` grant at `/token` with one-time consume, new refresh token on each use, and family revocation on reuse detection.
- Persisted in `OAuthStore` implementations (`InMemoryOAuthStore`, `SQLiteOAuthStore`, `PostgreSQLOAuthStore`, `RedisOAuthStore`).

## Alternatives Considered

- **Authlib**: Adds 10+ dependencies; overkill for a single JWT sign/verify
  plus DPoP validation.
- **PyJWT**: HMAC-only JWT is 20 lines; adding a dependency for it is waste.
- **TLS-only (no DPoP)**: Rejected because the MCP server is designed to run
  behind a reverse proxy and DPoP protects against replay even after TLS
  termination.
