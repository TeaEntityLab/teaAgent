# OAuth → tenant mapping at the gateway

External identity providers (Google, GitHub, Okta) issue tokens with a **subject** claim. TeaAgent control plane expects:

- `Authorization: Bearer <tenant-scoped-token>`
- `X-TeaAgent-Tenant: <tenant-id>`

Gateways translate OAuth identity → tenant + injected bearer.

## Subject map file

Copy [`templates/reverse-proxy/oauth-tenant-map.json.example`](../templates/reverse-proxy/oauth-tenant-map.json.example):

```json
{
  "subject_tenants": {
    "alice@example.com": "team-a",
    "bob@example.com": "team-b"
  }
}
```

Validate and emit nginx snippet:

```bash
python3 -c "
from pathlib import Path
from teaagent.gateway_oauth import OAuthTenantMap
m = OAuthTenantMap.from_file(Path('oauth-tenant-map.json'))
print(m.to_nginx_map_snippet())
"
```

## nginx + oauth2-proxy

1. Run [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) in front of TeaAgent.
2. Configure `auth_request` to set `X-Auth-Request-Email` (or preferred claim).
3. Use the generated `map` block to set `$teaagent_tenant`.
4. Map tenant → bearer token (from `tokens.json` / env) and proxy to control plane.

See [`templates/reverse-proxy/nginx-oauth.conf.example`](../templates/reverse-proxy/nginx-oauth.conf.example).

## Caddy + OAuth

Use `caddy-security` or an external OAuth plugin to authenticate, then `header_up X-TeaAgent-Tenant` from a `map` table.

See [`templates/reverse-proxy/Caddyfile.oauth.example`](../templates/reverse-proxy/Caddyfile.oauth.example).

## In-app path routes (CDN-friendly)

Tenant-scoped SSE without relying on headers alone:

- `GET /api/tenants/{tenant_id}/workflow/stream`
- `GET /api/tenants/{tenant_id}/focus/stream`
- `GET /api/tenants/{tenant_id}/jit/diff`

Legacy header routes (`/api/workflow/stream` + `X-TeaAgent-Tenant`) remain supported.
