# Backup and Recovery

## What Needs Backing Up

All persistent teaagent state lives under `.teaagent/` in the workspace root and `~/.teaagent/` in the user's home directory.

| Path | Content | Criticality | Frequency |
|------|---------|-------------|-----------|
| `.teaagent/config.json` | Workspace config | High | On every change |
| `.teaagent/audit.jsonl` | Global audit trail | Critical | Continuous / daily |
| `.teaagent/runs/` | Per-run replay logs | High | Daily |
| `.teaagent/sessions/` | Session focus stacks | Medium | Daily |
| `.teaagent/undo/` | Undo checkpoint data | Medium | Daily |
| `.teaagent/plans/` | Stored plans | Low | Weekly |
| `.teaagent/mcp-trust.json` | MCP trust policies | High | On every change |
| `.teaagent/pending_approvals/` | Approval queue | Medium | Daily |
| `~/.teaagent/workspace_registry.json` | Workspace index | Low | Weekly |
| `~/.teaagent/tui_state.json` | TUI layout/history | Low | Weekly |
| `~/.teaagent/relay-tokens.json` | Auth tokens | High | On every change |
| `~/.teaagent/run-keys/` | Per-run HMAC signing keys | **Critical** | On every change |

**Do not** back up `.teaagent/*.db` (graphqlite databases) — they are derived from source code and can be rebuilt with `teaagent agent card --rebuild-index`.

---

## Backup Strategy

### Minimum viable backup (daily rsync)

```bash
#!/bin/bash
# /usr/local/bin/teaagent-backup.sh
set -euo pipefail

WORKSPACE=/opt/workspace
BACKUP_ROOT=/backup/teaagent
DATE=$(date +%Y%m%d)
DEST="$BACKUP_ROOT/$DATE"

mkdir -p "$DEST"

rsync -av --exclude='*.db' \
  "$WORKSPACE/.teaagent/" \
  "$DEST/teaagent-workspace/"

rsync -av \
  "$HOME/.teaagent/" \
  "$DEST/teaagent-user/"

# Keep 30 days of backups
find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "Backup complete: $DEST"
```

Add to crontab:

```cron
0 3 * * * /usr/local/bin/teaagent-backup.sh >> /var/log/teaagent-backup.log 2>&1
```

### Continuous audit log shipping

For audit logs, prefer real-time shipping over periodic backup. This gives a second copy that survives local disk failure:

**Option A: Webhook sink (built-in)**

```bash
export TEAAGENT_AUTOMATION_WEBHOOK_URL="https://audit-store.example.com/ingest"
export TEAAGENT_AUTOMATION_WEBHOOK_SECRET="..."
```

**Option B: Filebeat / Fluentd tail**

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    paths:
      - /opt/workspace/.teaagent/audit.jsonl
    json.keys_under_root: true
output.elasticsearch:
  hosts: ["https://elasticsearch:9200"]
  index: "teaagent-audit-%{+yyyy.MM}"
```

**Option C: S3 sync (AWS)**

```bash
# Continuous sync of audit log
aws s3 sync .teaagent/ s3://my-bucket/teaagent-$(hostname)/ \
  --exclude "*.db" \
  --sse AES256
```

### Git-based config backup

Config and trust policies are best version-controlled:

```bash
# Track config and trust policies in a private git repo
cd .teaagent
git init
git add config.json mcp-trust.json
git commit -m "teaagent workspace config"
git remote add origin git@github.com:yourorg/teaagent-config.git
git push -u origin main
```

Add `.teaagent/.gitignore`:

```gitignore
# Exclude runtime state — only track config
*.jsonl
*.db
sessions/
runs/
undo/
plans/
pending_approvals/
```

---

## Backup Verification

Never trust a backup you haven't restored. Run monthly:

```bash
#!/bin/bash
# teaagent-backup-verify.sh
set -euo pipefail

BACKUP=/backup/teaagent/$(date +%Y%m%d)/teaagent-workspace
RESTORE_TARGET=/tmp/teaagent-restore-test-$(date +%s)

mkdir -p "$RESTORE_TARGET"
cp -r "$BACKUP/." "$RESTORE_TARGET/.teaagent/"
chmod 700 "$RESTORE_TARGET/.teaagent"

# Verify audit log reads without error
LINES=$(grep -c '^{' "$RESTORE_TARGET/.teaagent/audit.jsonl" 2>/dev/null || echo 0)
echo "Audit log: $LINES events restored"

# Verify config is valid JSON
python3 -m json.tool "$RESTORE_TARGET/.teaagent/config.json" > /dev/null && \
  echo "Config: valid JSON" || echo "FAIL: config.json is invalid"

# Verify run logs
RUN_COUNT=$(ls "$RESTORE_TARGET/.teaagent/runs/" 2>/dev/null | wc -l)
echo "Run logs: $RUN_COUNT files restored"

rm -rf "$RESTORE_TARGET"
echo "Verification complete"
```

---

## Disaster Recovery

### Scenario: Workspace `.teaagent/` lost (disk failure)

1. Restore from backup:

```bash
rsync -av /backup/teaagent/latest/teaagent-workspace/ /opt/workspace/.teaagent/
chmod 700 /opt/workspace/.teaagent
chmod 600 /opt/workspace/.teaagent/*.jsonl
chmod 600 /opt/workspace/.teaagent/*.json
```

2. Rebuild derived state:

```bash
cd /opt/workspace

# Rebuild graphqlite code index (derived from source)
teaagent agent card --rebuild-index

# Verify integrity
teaagent doctor all
teaagent audit verify
```

3. Re-enter API keys if they were only in the environment (not in a secrets manager):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

4. Validate smoke test:

```bash
teaagent model smoke
```

### Scenario: Audit log only is corrupt/lost

Restore only the audit log from backup:

```bash
cp /backup/teaagent/latest/teaagent-workspace/audit.jsonl .teaagent/audit.jsonl
chmod 600 .teaagent/audit.jsonl
teaagent audit verify
```

If the backup is older than the last run, append any newer events from the shipped copy (webhook sink / Elasticsearch):

```bash
# Export missing events from Elasticsearch
curl -s "https://elasticsearch:9200/teaagent-audit-*/_search" \
  -H "Content-Type: application/json" \
  -d '{"query": {"range": {"ts": {"gt": "2026-06-01T00:00:00Z"}}}}' | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for hit in data['hits']['hits']:
    print(json.dumps(hit['_source']))
" >> .teaagent/audit.jsonl
```

### Scenario: Full host failure (replace machine)

1. Provision new host, install teaagent
2. Restore from backup or object storage:

```bash
mkdir -p /opt/workspace
rsync -av /backup/teaagent/latest/teaagent-workspace/ /opt/workspace/.teaagent/
rsync -av /backup/teaagent/latest/teaagent-user/ ~/.teaagent/
chmod 700 /opt/workspace/.teaagent ~/.teaagent
```

3. Restore secrets from secrets manager (Vault, AWS Secrets Manager, etc.):

```bash
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/teaagent/anthropic)
```

4. Re-initialize MCP trust if the key was host-local:

```bash
export TEAAGENT_MCP_TRUST_KEY=$(vault kv get -field=trust_key secret/teaagent/mcp)
teaagent mcp trust_list  # verify policies loaded
```

5. Run doctor:

```bash
teaagent doctor all
```

---

## RTO / RPO Targets

| Scenario | RPO (data loss) | RTO (downtime) |
|----------|----------------|----------------|
| Config corruption | Last git commit (~minutes) | 15 min |
| Audit log partial loss | Last webhook event (~seconds) | 30 min |
| Full workspace loss | Last daily backup (≤24 h) | 1 hour |
| Full host failure | Last daily backup (≤24 h) | 2 hours |

Reduce RPO to seconds by enabling real-time audit log shipping (webhook or Filebeat).

---

---

## Audit HMAC Key Management (SEC-01)

### Key file location

Each run writes a 32-byte random HMAC-SHA256 signing key to:

```
~/.teaagent/run-keys/<run_id>.key   (mode 0o600, dir mode 0o700)
```

The key is created on first write and reloaded on subsequent `AuditLogger` instances for the same run.  Without the key, `teaagent audit verify` can still check the SHA-256 hash chain for structural integrity but cannot verify HMAC signatures.

### Why these keys are Critical

If the key files are lost, audit entries can still be read, but HMAC verification will fail for any run whose key is missing.  An attacker who gains write access to the audit log but not the key file cannot forge a valid HMAC-signed chain.  Back up `~/.teaagent/run-keys/` with at least the same frequency as the audit logs themselves.

### Backup

Include `~/.teaagent/run-keys/` in your regular backup:

```bash
rsync -av --chmod=D700,F600 \
  "$HOME/.teaagent/run-keys/" \
  "$DEST/teaagent-user/run-keys/"
```

Keep backups of this directory in a location separate from the audit log files. An attacker who has both the key file and write access to the audit log can forge the HMAC chain.

### Rotation

HMAC keys are per-run and never reused across runs.  To rotate a compromised key:

1. Delete the key file for the affected run: `rm ~/.teaagent/run-keys/<run_id>.key`
2. The run's HMAC signatures become unverifiable (the chain hash integrity is unaffected).
3. Note the rotation in your incident log with the run ID and timestamp.
4. Future runs automatically generate new keys.

There is no cross-run key; rotation of one run's key does not affect any other run.

---

## See Also

- [Operations Manual](operations-manual.md)
- [Runbooks](runbooks.md)
- [Security Hardening](security-hardening.md)
