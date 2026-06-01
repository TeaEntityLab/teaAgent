# ADR 0006: OAuth Store and Key Ring Interfaces

## Status

Accepted and Implemented - 2026-05-09

## Decision

Introduce `OAuthStore` and `OAuthKeyRing` abstractions for the OAuth 2.1 / DPoP
implementation while preserving the current in-memory default behavior. Provide
`SQLiteOAuthStore` as the first durable implementation for single-host deployments.

## Implementation

**Git History:**
- **Created:** 2026-05-09 00:26:48 +0800
- **Commit:** `2cc6de343b1acf9af329ed4e2c1f5155c5c4bc6d`
- **Message:** "Add OAuthStore/OAuthKeyRing interfaces, CLI config auto-discovery and profiles, and e2e tests"

**Updated:** 2026-05-09 07:36:22 +0800
- **Commit:** `77213c936cecdf406ff551635e7de6bf5317c445`
- **Message:** "Add SQLiteOAuthStore for durable OAuth 2.1 persistence"

**Updated:** 2026-05-09 08:22:43 +0800
- **Commit:** `392f8b5b5f56e6625152dc35d5da8f44d5178752`
- **Message:** "Hash OAuth client secrets with PBKDF2-SHA256 in SQLiteOAuthStore"

**Updated:** 2026-05-09 08:47:45 +0800
- **Commit:** `6bd92246702cc366773deb8f1bb87ab03adfa799`
- **Message:** "Make DPoP nonce validation one-time with atomic consume semantics"

**Updated:** 2026-05-09 08:49:47 +0800
- **Commit:** `919fee211321071966900d9d807498efd42cd7ad`
- **Message:** "Add DPoP proof jti replay cache to authorization and resource servers"

**Updated:** 2026-05-10 14:11:18 +0800
- **Commit:** `091b27189d0c84102745828cccc6cda923067680`
- **Message:** "Update ADRs, CHANGELOG, and replace stale scope files with backlog-priority"

**Files Added:**
- `teaagent/oauth21/_store.py` - OAuthStore and OAuthKeyRing interfaces
- `teaagent/oauth21/_sqlite_store.py` - SQLiteOAuthStore implementation
- `teaagent/oauth21/_keyring.py` - Key ring implementation

**Key Components:**
- **OAuthStore**: Persistence boundary for clients, codes, nonces, TTL
- **OAuthKeyRing**: Key-rotation boundary with active kid mapping
- **SQLiteOAuthStore**: Durable implementation for single-host deployments
- **PBKDF2-SHA256**: Client secret hashing
- **Atomic nonce consume**: One-time DPoP nonce validation
- **JTI replay cache**: DPoP proof replay prevention

**Tests:**
- Unit tests for OAuthStore and OAuthKeyRing
- E2E tests for SQLiteOAuthStore
- All tests passing

## Rationale

The initial OAuth server stored clients, authorization codes, and DPoP nonces in
private in-memory dictionaries. That is adequate for local MCP HTTP use, but it
prevents production deployments from sharing state across processes or rotating
signing keys.

`OAuthStore` defines the persistence boundary:

- registered clients
- one-time authorization codes
- DPoP nonce replay cache
- TTL pruning

`OAuthKeyRing` defines the key-rotation boundary:

- active `kid`
- mapping of key IDs to HMAC keys
- lookup by `kid` for future token verification paths

`SQLiteOAuthStore` stores clients, one-time authorization codes, and DPoP nonces
in a local SQLite database. It uses one transaction per operation, `BEGIN IMMEDIATE`
for authorization-code consume/delete, WAL journal mode, SQLite's busy timeout
for local concurrent access, and a schema-version metadata row for future migrations.
Client secrets are stored as PBKDF2-SHA256 hashes with per-client random salts rather
than plaintext. DPoP nonces are consumed through a store-level read/delete operation
so nonce validation has one-time replay semantics. DPoP proof `jti` values are
cached in memory by the authorization and resource servers for the proof freshness
window to reject repeated proofs.

## Consequences

- Existing callers keep using `OAuth21AuthorizationServer(signing_key=..., issuer=...)`.
- Single-host deployments can use `SQLiteOAuthStore` without changing MCP HTTP
  handlers or authorization-server call sites.
- Production deployments that need cross-host or horizontally scaled OAuth state
  can use `PostgreSQLOAuthStore` or `RedisOAuthStore`, implemented post-ADR in P0-r3.
- Key rotation verification uses `OAuthKeyRing` and JWT `kid` lookup, but key-ring
  distribution and rotation-window management remain deployment responsibilities.

## Deferred

- Key-ring distribution remains a deployment concern — `OAuthKeyRing` can generate and look up keys by `kid`, but distributing key material securely across hosts is outside the library's scope.

## Post-Implementation (2026-05-10)

Both items originally listed in this section have been implemented:
- **PostgreSQL/Redis OAuthStore**: `PostgreSQLOAuthStore` with `DELETE…RETURNING` atomic consume and `RedisOAuthStore` with Lua-script atomic consume, NX nonce/code saves, and configurable key prefix (`teaagent/oauth21/_pg_store.py`, `teaagent/oauth21/_redis_store.py`).
- **CLI key-ring support**: `--oauth-key-ring-file`, `--oauth-active-kid` with fail-closed validation, and `--oauth-rotation-window` (`cli/_mcp_parsers.py`, `cli/_handlers/_mcp.py`).
