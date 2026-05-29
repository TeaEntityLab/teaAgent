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

## Reverse proxy templates

See [`templates/reverse-proxy/`](../templates/reverse-proxy/) for Caddy and nginx examples that:

- Terminate TLS
- Inject per-tenant `Authorization` and `X-TeaAgent-Tenant`
- Optionally enforce mTLS on the relay listener
