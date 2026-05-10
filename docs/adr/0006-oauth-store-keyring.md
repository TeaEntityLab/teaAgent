# ADR 0006: OAuth Store and Key Ring Interfaces

## Status

Accepted for P1 hardening.

## Decision

Introduce `OAuthStore` and `OAuthKeyRing` abstractions for the OAuth 2.1 / DPoP
implementation while preserving the current in-memory default behavior. Provide
`SQLiteOAuthStore` as the first durable implementation for single-host deployments.

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
