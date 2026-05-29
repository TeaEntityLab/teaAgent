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
