# HTTP surface authentication

TeaAgent vote relay and control plane support **Bearer tokens**, optional **mTLS**, and **per-tenant authorization**.

## Token file format

`--api-token-file` expects JSON:

```json
{
  "tokens": [
    {"token": "relay-secret"},
    {"token": "team-a-dashboard", "tenants": ["team-a"]},
    {"token": "ops-admin", "tenants": ["*"]}
  ]
}
```

| Field | Meaning |
|-------|---------|
| `token` | Raw secret (hashed at load; not stored in memory as plaintext) |
| `tenants` | Allowed tenant IDs; omit or `["*"]` for admin (all tenants + list tenants API) |

Relay mode ignores `tenants` (any valid relay token may submit votes).

### Auto-discovered relay token file (loopback)

When `--api-token-file` is omitted, relay serve loads the first existing file:

1. `TEAAGENT_RELAY_TOKEN_FILE` (path)
2. `.teaagent/relay-tokens.json` (workspace)
3. `~/.teaagent/relay-tokens.json`

## Environment flags

| Variable | Effect |
|----------|--------|
| `TEAAGENT_STRICT_LOCAL=1` | MCP HTTP on loopback requires `auth_token` or OAuth |
| `TEAAGENT_ALLOW_DEV_SIGNATURES=1` | Allow dev-hash signatures (multi-sig / relay dev mode only) |
| `TEAAGENT_PLUGINS_STRICT=1` | Block unverified plugin entry points (site-packages / unknown source) |
| `TEAAGENT_PRECOMMIT_FULL=1` | Run full pytest in pre-commit (default: smoke subset) |
| `TEAAGENT_FEDERATED_SIGNATURE_TOKEN` | Require matching `auth_token` on file-based P2P approval signatures |

## Headers

| Header | Use |
|--------|-----|
| `Authorization: Bearer <token>` | Primary |
| `X-TeaAgent-Relay-Token` | Vote relay alternative |
| `X-TeaAgent-Token` | Control plane alternative |
| `X-TeaAgent-Tenant` | Tenant scope for control plane APIs |

## Fail-closed bind rules

| Surface | Non-loopback without tokens |
|---------|----------------------------|
| `teaagent consensus relay serve` | **Rejected** at startup |
| `teaagent control-plane serve` | **Rejected** at startup |

Bind to `127.0.0.1` for local dev without tokens.

## Vote relay rate limits

`teaagent consensus relay serve` applies a per-token sliding window (default **120** POSTs per **60** seconds):

```bash
teaagent consensus relay serve --api-token-file relay-tokens.json \
  --rate-limit-calls 60 --rate-limit-window 60
```

Set `--rate-limit-calls 0` to disable. Exceeded quotas return HTTP **429**.

## mTLS (vote relay)

```bash
teaagent consensus relay serve \
  --tls-cert server.pem --tls-key server.key \
  --tls-client-ca client-ca.pem \
  --api-token-file relay-tokens.json
```

Requires client certificates signed by `client-ca.pem`.

## MCP HTTP TLS (native TLS not supported)

`teaagent mcp serve --http` does **not** terminate TLS in-process (see
[ADR 0005](adr/0005-mcp-streamable-http.md) and [ADR 0008](adr/0008-p4-strategic-posture.md)).
For remote clients:

1. Bind MCP to loopback (`127.0.0.1`) or a private interface.
2. Terminate TLS at Caddy/nginx using [`templates/reverse-proxy/`](../templates/reverse-proxy/).
3. Set `TEAAGENT_STRICT_LOCAL=1` when the proxy forwards to loopback so bearer/OAuth
   is still required on the upstream hop.

## Federated multi-sig file transport

| Variable | Effect |
|----------|--------|
| `TEAAGENT_FEDERATED_SIGNATURE_TOKEN` | When set, P2P signature files under `.teaagent/pending_approvals/` must include matching `auth_token` |

### Signature relay (WAN multi-sig)

```bash
# Collector (requester workspace)
teaagent sync signature-relay serve --api-token-file .teaagent/relay-tokens.json --port 8791

# Peer submits signature (after receiving approval request)
export TEAAGENT_SIGNATURE_RELAY_TOKEN=...
teaagent sync signature-relay submit \
  --relay-url https://requester.example:8791 \
  --request-id <id> --peer-id peer-1 --signature "<ssh-blob>"
```

Configure `MultiSigQuorumConfig.local_relay_base_url` and `peer_relay_urls` in policy,
or set `TEAAGENT_SIGNATURE_RELAY_TOKEN` / `TEAAGENT_RELAY_TOKEN` for HTTP client auth.

API:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/approval-requests` | Peer receives approval request |
| POST | `/api/v1/approval-signatures` | Peer submits signature to collector |
| GET | `/api/v1/approval-signatures?request_id=` | Collector polls signatures |

File-based multi-sig remains available for local dev; production WAN should use the
HTTP relay behind TLS termination (ADR 0008).

## Reverse proxy templates

See [`templates/reverse-proxy/`](../templates/reverse-proxy/) for Caddy and nginx examples that:

- Terminate TLS
- Inject per-tenant `Authorization` and `X-TeaAgent-Tenant`
- Optionally enforce mTLS on the relay listener
