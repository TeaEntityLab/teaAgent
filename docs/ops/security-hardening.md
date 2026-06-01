# Security Hardening

## Deployment Checklist

Work through this checklist before exposing teaagent to production workloads or multi-user environments.

### API Keys and Secrets

- [ ] API keys are set via environment variables, never hardcoded in config files
- [ ] Config files (`.teaagent/config.json`) contain no secrets
- [ ] API keys are stored in a secrets manager (Vault, AWS Secrets Manager, 1Password) and injected at runtime
- [ ] `TEAAGENT_ALLOW_DEV_SIGNATURES` is **not set** (or set to `0`) in production
- [ ] `TEAAGENT_MCP_TRUST_KEY` is set to a strong random value if MCP is used
- [ ] `TEAAGENT_APPROVAL_HMAC_KEY` is set to a strong random value if automation webhooks are used
- [ ] `.teaagent/` directory is not committed to git (add to `.gitignore`)
- [ ] `relay-tokens.json` is not committed to git

### File System Permissions

- [ ] `.teaagent/` directory permissions are `0o700` (owner only)
- [ ] All files in `.teaagent/` have permissions `0o600`
- [ ] teaagent process runs as a dedicated non-root user
- [ ] The workspace directory is not world-readable

```bash
# Verify and fix permissions
chmod 700 .teaagent/
find .teaagent/ -type f -exec chmod 600 {} \;
```

### Permission Mode

- [ ] Permission mode is set to the least-privilege level for the use case:
  - CI pipelines that only write files: `workspace-write`
  - Review / audit tasks: `read-only`
  - Interactive developer sessions: `prompt`
  - Fully trusted automation only: `allow` or `danger-full-access`
- [ ] `danger-full-access` is never used unless the environment is fully air-gapped or the risk is explicitly accepted

### Network Isolation

- [ ] Outbound connections are limited to required LLM provider endpoints
- [ ] If using an AI Gateway or proxy, all traffic routes through it (set `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`)
- [ ] The teaagent process does not have access to internal network resources it doesn't need
- [ ] Ingress to the automation webhook server is restricted to known senders

### Audit Log Protection

- [ ] Audit log (`audit.jsonl`) is backed up to an immutable store (S3 with object lock, write-once storage)
- [ ] Audit log integrity is verified on a schedule: `teaagent audit verify`
- [ ] The audit log file is not writable by any process other than teaagent
- [ ] HMAC chain signing is enabled (enabled by default)

---

## Secret Management

### Environment variable injection (recommended)

Never store secrets in `.teaagent/config.json`. Inject at process start:

```bash
# From a secrets manager
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/teaagent/anthropic)
export TEAAGENT_MCP_TRUST_KEY=$(vault kv get -field=trust_key secret/teaagent/mcp)
teaagent run "task"
```

### Systemd credential injection

```ini
[Service]
LoadCredential=anthropic_key:/run/secrets/anthropic_key
ExecStart=/bin/bash -c 'export ANTHROPIC_API_KEY=$(cat $CREDENTIALS_DIRECTORY/anthropic_key) && teaagent mcp serve'
```

### Key rotation

Rotate API keys without downtime:

1. Generate new key at provider
2. Update secrets manager
3. Restart teaagent process (it reads env vars at startup)
4. Revoke old key at provider

For `TEAAGENT_MCP_TRUST_KEY` rotation:

```bash
# 1. Set new key
export TEAAGENT_MCP_TRUST_KEY=<new-key>

# 2. Re-encrypt trust policies
teaagent mcp trust_list  # triggers re-encryption with new key

# 3. Verify
teaagent mcp trust_inspect <server_id>
```

---

## Audit Log Protection

### Immutable backup

Use object storage with versioning and object lock for tamper-evident audit storage:

```bash
# AWS S3 with object lock (WORM)
aws s3api create-bucket --bucket teaagent-audit-logs
aws s3api put-object-lock-configuration \
  --bucket teaagent-audit-logs \
  --object-lock-configuration '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":365}}}'

# Sync audit log
aws s3 sync .teaagent/ s3://teaagent-audit-logs/$(hostname)/ \
  --exclude "*.db" \
  --sse AES256
```

### File integrity monitoring

Add the audit log to your file integrity monitoring tool (AIDE, Tripwire, OSquery):

```bash
# AIDE config
/opt/workspace/.teaagent/audit.jsonl   GROWING

# osquery (alert on unexpected size decrease — truncation attack)
SELECT * FROM file WHERE path = '/opt/workspace/.teaagent/audit.jsonl'
  AND size < (SELECT size FROM file WHERE path = '/opt/workspace/.teaagent/audit.jsonl');
```

### Chain HMAC verification

Verify the audit chain daily:

```bash
teaagent audit verify && echo "OK" || alert "AUDIT INTEGRITY FAILURE"
```

---

## Network Isolation

### Allowlist outbound connections

For corporate or air-gapped environments, allowlist only the endpoints teaagent needs:

| Provider | Endpoint | Port |
|----------|----------|------|
| Anthropic | `api.anthropic.com` | 443 |
| OpenAI | `api.openai.com` | 443 |
| Gemini | `generativelanguage.googleapis.com` | 443 |
| OpenRouter | `openrouter.ai` | 443 |
| Ollama (local) | `localhost:11434` | 11434 |

### Route through AI Gateway (Cloudflare)

Proxy all provider traffic through a managed gateway for rate limiting, logging, and key abstraction:

```bash
export ANTHROPIC_BASE_URL="https://gateway.ai.cloudflare.com/v1/<account>/<gateway>/anthropic"
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID="..."
export CLOUDFLARE_GATEWAY_ID="..."
```

### mTLS for internal endpoints

If connecting to internal LLM endpoints:

```bash
export TEAAGENT_TLS_CLIENT_CERT="/etc/teaagent/client.crt"
export TEAAGENT_TLS_CLIENT_KEY="/etc/teaagent/client.key"
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/internal-ca.pem"
```

---

## Multi-Signature Quorum for High-Risk Operations

Require multiple agent approvals for operations matching high-risk patterns (e.g., writes to `/prod`):

```json
{
  "multi_sig": {
    "enabled": true,
    "required_approvals": 2,
    "peer_agent_ids": ["agent-b", "agent-c"],
    "peer_public_keys": {
      "agent-b": "ssh-ed25519 AAAA...",
      "agent-c": "ssh-ed25519 AAAA..."
    },
    "peer_relay_urls": {
      "agent-b": "https://relay-b.example.com",
      "agent-c": "https://relay-c.example.com"
    },
    "timeout_seconds": 300,
    "high_risk_patterns": ["/prod", "/production", "*.env.production"],
    "allow_dev_signatures": false
  }
}
```

**Never set `allow_dev_signatures: true` in production** — dev signatures bypass cryptographic verification.

---

## Secrets Redaction in Audit Logs

TeaAgent automatically redacts the following patterns from audit logs:

- Keys matching: `api_key`, `authorization`, `credential`, `password`, `secret`, `token`
- Value patterns: JWTs (`eyJ...`), AWS keys (`AKIA...`), GitHub tokens (`ghp_...`, `ghs_...`), Bearer tokens

Verify redaction is working:

```bash
# Should return no unredacted tokens
grep -E '"(api_key|password|secret)"\s*:\s*"[^*]' .teaagent/audit.jsonl | head -5
```

---

## Process Isolation

### Dedicated user account

```bash
# Create dedicated service account
useradd -r -s /bin/bash -d /opt/teaagent teaagent
chown -R teaagent:teaagent /opt/workspace/.teaagent
```

### systemd sandboxing

Add to the systemd unit file:

```ini
[Service]
User=teaagent
Group=teaagent
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/workspace/.teaagent
CapabilityBoundingSet=
AmbientCapabilities=
```

### Docker isolation

```dockerfile
FROM python:3.12-slim
RUN useradd -r -s /bin/bash teaagent
RUN pip install "teaagent[tui,code-analysis]"
USER teaagent
WORKDIR /workspace
ENV TEAAGENT_INTERACTIVE=0
ENV TEAAGENT_PERMISSION_MODE=workspace-write
ENTRYPOINT ["teaagent"]
```

```bash
docker run \
  --read-only \
  --tmpfs /tmp \
  --volume /opt/workspace:/workspace \
  --env-file /run/secrets/teaagent.env \
  --network restricted-net \
  teaagent run "task"
```

---

## Webhook Security

If using `teaagent automation serve`, verify incoming webhook signatures:

```python
import hmac, hashlib

def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

The signature is in the `X-TeaAgent-Signature` request header.

---

## GitHub Token Scoping

If `GITHUB_TOKEN` or `GH_TOKEN` is set, use the minimum required scopes:

| Use case | Minimum scopes |
|----------|---------------|
| Read-only code review | `repo:read` (private repos) or none (public) |
| Commit and push | `repo:write` |
| PR creation | `repo:write`, `pull_requests:write` |

Use fine-grained personal access tokens (PAT) scoped to specific repositories rather than classic tokens with broad `repo` scope.

---

## Security Incident Response

If you suspect the teaagent process was compromised:

1. **Isolate** — kill the process, block network egress from the host
2. **Preserve** — copy `.teaagent/` to a forensic location before any cleanup
3. **Audit** — run `teaagent audit verify` on the forensic copy; review all tool calls since the suspected compromise time
4. **Rotate** — rotate all API keys that were accessible to the process
5. **Restore** — reinstall from a known-good backup; do not reuse the compromised `.teaagent/` state
6. **Report** — if LLM provider keys were exposed, notify the provider and your security team

---

## See Also

- [Deployment Guide](deployment-guide.md)
- [Configuration Reference](configuration-reference.md)
- [Backup and Recovery](backup-and-recovery.md)
- [Runbooks](runbooks.md)
