# ADR 0006: OAuth Store and Key Ring Interfaces

## Status

Accepted for P1 hardening.

## Decision

Introduce `OAuthStore` and `OAuthKeyRing` abstractions for the OAuth 2.1 / DPoP
implementation while preserving the current in-memory default behavior.

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

## Consequences

- Existing callers keep using `OAuth21AuthorizationServer(signing_key=..., issuer=...)`.
- Production deployments can implement a SQL/Redis-backed `OAuthStore` without
  changing the MCP HTTP handler.
- Key rotation is not fully automated yet; the key ring is the interface needed
  before adding multi-key resource-server verification.

## Deferred

- Persistent SQLite/PostgreSQL implementation of `OAuthStore`.
- Full resource-server multi-key verification by JWT `kid`.
- CLI support for key-ring files and rotation windows.
