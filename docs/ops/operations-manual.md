# Operations Manual

This manual covers running teaagent in production: startup, shutdown, monitoring, and day-to-day operations.

---

## Process Model

TeaAgent is a single-process, file-backed application. There are no mandatory background services. State lives in `.teaagent/` inside the workspace directory.

Modes of operation:

| Mode | Command | Use case |
|------|---------|----------|
| One-shot | `teaagent run "task"` | CI pipelines, scripted automation |
| Interactive TUI | `teaagent chat "task"` | Developer daily driver |
| MCP server | `teaagent mcp serve` | IDE / Claude Code integration |
| Automation server | `teaagent automation serve` | Webhook-driven execution |
| Gateway | `teaagent gateway start` | Multi-workspace routing |

---

## Startup

### Interactive TUI

```bash
cd /path/to/workspace
export ANTHROPIC_API_KEY="sk-ant-..."
teaagent chat
```

Pass an initial task directly:

```bash
teaagent chat "fix the failing tests in auth/"
```

### One-Shot (CI/Scripted)

```bash
TEAAGENT_INTERACTIVE=0 \
TEAAGENT_PERMISSION_MODE=workspace-write \
teaagent run "run pytest and fix any failures" \
  --root /path/to/workspace \
  --max-iterations 20
```

### MCP Server (systemd example)

```ini
[Unit]
Description=TeaAgent MCP Server
After=network.target

[Service]
Type=simple
User=teaagent
WorkingDirectory=/opt/workspace
EnvironmentFile=/etc/teaagent/env
ExecStart=/usr/local/bin/teaagent mcp serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/teaagent/env`:

```
ANTHROPIC_API_KEY=sk-ant-...
TEAAGENT_PERMISSION_MODE=prompt
TEAAGENT_DAILY_COST_CAP_CENTS=5000
```

### Automation Webhook Server

```bash
teaagent automation serve \
  --host 0.0.0.0 \
  --port 8080
```

Requires `TEAAGENT_AUTOMATION_WEBHOOK_URL` and `TEAAGENT_AUTOMATION_WEBHOOK_SECRET`.

---

## Shutdown

### TUI / Interactive

Press `Ctrl+C` or type `/exit` in the TUI. TeaAgent flushes audit logs before exiting.

### One-Shot

Exits naturally after completing (or exhausting iterations on) the task.

Send `SIGTERM` for graceful shutdown:

```bash
kill -TERM <pid>
```

TeaAgent handles `SIGTERM` and flushes in-progress audit events. Avoid `SIGKILL` unless the process is unresponsive — it may leave the current run's audit log incomplete.

---

## Preflight Check

Run before any production task:

```bash
teaagent preflight
```

This checks:
- Config file validity
- API key reachability
- Workspace `.teaagent/` directory permissions
- Audit log writability

---

## Daily Operations

### View Recent Runs

```bash
# List last 20 runs
teaagent agent runs --limit 20

# Show details of a specific run
teaagent agent show <run_id>
```

### Check Current Cost

```bash
teaagent cost cost_report --period today
```

### View Pending Approvals

```bash
teaagent approval pending
```

Approve or deny:

```bash
teaagent approval approve <approval_id>
teaagent approval deny <approval_id>
```

### Session Management

```bash
# List sessions
teaagent agent status

# Resume a suspended session
teaagent resume <session_id>

# Attach to a running session
teaagent agent attach <session_id>
```

### Audit Log Review

```bash
# List recent audit events
teaagent audit list --limit 50

# Export to file
teaagent audit export --output audit-$(date +%Y%m%d).jsonl

# Verify integrity (chain HMAC check)
teaagent audit verify
```

---

## Log Aggregation

TeaAgent writes two log streams:

| Stream | Location | Format | Purpose |
|--------|----------|--------|---------|
| Audit log | `.teaagent/audit.jsonl` | JSONL | Immutable audit trail; chain-signed |
| Per-run log | `.teaagent/runs/<run_id>.jsonl` | JSONL | Full run replay data |

### Shipping Logs to External Systems

**Option 1: Webhook audit sink**

Set `TEAAGENT_AUTOMATION_WEBHOOK_URL` to forward audit events to any HTTP endpoint in real time.

**Option 2: File tail (Filebeat/Fluentd)**

Point your log shipper at `.teaagent/audit.jsonl`. Each line is a complete JSON event.

Example Filebeat config:

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /opt/workspace/.teaagent/audit.jsonl
    json.keys_under_root: true
    json.add_error_key: true
    fields:
      service: teaagent
output.elasticsearch:
  hosts: ["https://elasticsearch:9200"]
```

**Option 3: OpenTelemetry**

Install the telemetry extra and configure the OTLP exporter:

```bash
pip install "teaagent[telemetry]"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4317"
export OTEL_SERVICE_NAME="teaagent"
```

---

## Rotation and Maintenance

### Audit Log Pruning

Audit logs grow indefinitely. Prune old entries:

```bash
# Remove audit events older than 90 days
teaagent audit prune --older-than 90d
```

Prune individual run logs:

```bash
# Remove run logs older than 30 days
find .teaagent/runs/ -name "*.jsonl" -mtime +30 -delete
```

Schedule via cron:

```cron
0 2 * * * /usr/local/bin/teaagent audit prune --older-than 90d --root /opt/workspace
```

### Session Cleanup

```bash
# Remove completed sessions older than 7 days
find .teaagent/sessions/ -name "*.json" -mtime +7 -delete
```

---

## Emergency Pause

To immediately stop all in-flight agent operations:

```bash
teaagent automation pause --all
```

This prevents new runs from starting. Resume when safe:

```bash
teaagent automation resume --all
```

See [Runbooks](runbooks.md) for detailed emergency procedures.

---

## Upgrading in Place

```bash
pip install --upgrade teaagent

# Check for required migrations
teaagent doctor migration

# Run any required migrations
teaagent doctor migration --apply

# Verify health
teaagent doctor all
```

---

## Multi-Workspace Setup

For environments with multiple workspaces, each workspace has its own `.teaagent/` directory. The workspace registry at `~/.teaagent/workspace_registry.json` tracks known workspaces.

```bash
# Register a workspace
teaagent init --root /path/to/workspace

# List registered workspaces (via registry)
cat ~/.teaagent/workspace_registry.json
```

---

## See Also

- [Runbooks](runbooks.md)
- [Monitoring and Alerting](monitoring-and-alerting.md)
- [Backup and Recovery](backup-and-recovery.md)
- [Troubleshooting](troubleshooting.md)
