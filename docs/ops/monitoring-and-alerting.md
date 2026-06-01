# Monitoring and Alerting

## What to Monitor

TeaAgent has no built-in metrics server. Observability is built from three sources:

| Source | Format | Location |
|--------|--------|----------|
| Audit log | JSONL (append-only) | `.teaagent/audit.jsonl` |
| Per-run logs | JSONL | `.teaagent/runs/<run_id>.jsonl` |
| OpenTelemetry traces/metrics | OTLP | Configurable exporter endpoint |
| Webhook events | JSON HTTP POST | `TEAAGENT_AUTOMATION_WEBHOOK_URL` |

---

## Key Metrics

### Cost

| Metric | How to extract | Alert threshold |
|--------|---------------|-----------------|
| Daily spend (USD) | `teaagent cost cost_report --period today` | > 80% of daily cap |
| Per-run cost | `grep '"cost_usd"' .teaagent/runs/<id>.jsonl` | > $1.00 per run |
| Session cost | `grep '"session_cost"' .teaagent/audit.jsonl` | Sudden 10× spike |

### Reliability

| Metric | How to extract | Alert threshold |
|--------|---------------|-----------------|
| Run success rate | `teaagent agent runs --status failed` | > 5% failure rate |
| Run duration | Compare `start_ts` / `end_ts` in run log | > 2× baseline p95 |
| Approval backlog | `teaagent approval pending \| wc -l` | > 10 pending |
| Agent timeouts | `grep '"status":"timeout"' .teaagent/audit.jsonl` | Any occurrence |

### Audit Integrity

| Metric | How to extract | Alert threshold |
|--------|---------------|-----------------|
| HMAC chain validity | `teaagent audit verify` exit code | Non-zero exit |
| Audit log growth | `du -sb .teaagent/audit.jsonl` | > 1 GB |
| Disk free space | `df -h .teaagent/` | < 20% free |

### Provider Health

| Metric | How to extract | Alert threshold |
|--------|---------------|-----------------|
| Provider reachable | `teaagent model smoke` exit code | Non-zero exit |
| API error rate | `grep '"api_error"' .teaagent/audit.jsonl` | > 1% of calls |
| Latency | `grep '"latency_ms"' .teaagent/audit.jsonl` | p95 > 10 s |

---

## Audit Log Event Schema

Each line in `.teaagent/audit.jsonl` is a JSON object. Common fields:

```json
{
  "ts": "2026-06-02T04:15:30.123Z",
  "type": "tool_call",
  "run_id": "run_abc123",
  "session_id": "sess_xyz",
  "tool": "write_file",
  "status": "ok",
  "cost_usd": 0.0012,
  "latency_ms": 842,
  "hmac": "sha256:..."
}
```

Key event types: `session_start`, `session_end`, `tool_call`, `tool_result`, `cost`, `approval_requested`, `approval_granted`, `approval_denied`, `run_start`, `run_end`, `error`.

---

## OpenTelemetry Setup

Install the telemetry extra:

```bash
pip install "teaagent[telemetry]"
```

Configure the exporter:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4317"
export OTEL_SERVICE_NAME="teaagent"
export OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production,service.version=1.0"
```

TeaAgent emits:
- **Traces:** one span per agent run, child spans per tool call
- **Metrics:** `teaagent.cost_usd` (counter), `teaagent.tool_call_duration_ms` (histogram), `teaagent.run_duration_ms` (histogram)

---

## Webhook Alerting

Configure a webhook to receive real-time audit events:

```bash
export TEAAGENT_AUTOMATION_WEBHOOK_URL="https://alerts.example.com/teaagent"
export TEAAGENT_AUTOMATION_WEBHOOK_SECRET="hmac-secret"
```

Payload format:

```json
{
  "event": "run_end",
  "run_id": "run_abc123",
  "status": "failed",
  "cost_usd": 0.45,
  "duration_ms": 12430,
  "ts": "2026-06-02T04:15:30.123Z"
}
```

HMAC-SHA256 signature is in the `X-TeaAgent-Signature` header for verification.

---

## Alerting Scripts

### Cost alert (shell script, run via cron)

```bash
#!/bin/bash
# /usr/local/bin/teaagent-cost-alert.sh
set -euo pipefail

CAP_CENTS=${TEAAGENT_DAILY_COST_CAP_CENTS:-5000}
ALERT_PCT=80
ALERT_THRESHOLD=$(( CAP_CENTS * ALERT_PCT / 100 ))

CURRENT=$(teaagent cost cost_report --period today --format json | \
  python3 -c "import json,sys; print(int(json.load(sys.stdin)['total_cents']))")

if [ "$CURRENT" -gt "$ALERT_THRESHOLD" ]; then
  echo "ALERT: teaagent daily cost ${CURRENT} cents > ${ALERT_THRESHOLD} cents (${ALERT_PCT}% of cap)"
  # Add your notification here: curl, mail, etc.
  curl -s -X POST "$SLACK_WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"TeaAgent cost alert: \$$(echo "scale=2; $CURRENT/100" | bc) spent today\"}"
fi
```

Add to crontab:

```cron
*/15 * * * * /usr/local/bin/teaagent-cost-alert.sh >> /var/log/teaagent-cost.log 2>&1
```

### Audit integrity check (cron, daily)

```bash
#!/bin/bash
teaagent audit verify --root /opt/workspace || \
  echo "CRITICAL: TeaAgent audit log integrity check failed at $(date)" | \
  mail -s "TeaAgent Audit Alert" ops@example.com
```

### Provider health check (cron, every 5 minutes)

```bash
#!/bin/bash
if ! teaagent model smoke --provider claude --timeout 30 2>/dev/null; then
  echo "TeaAgent provider claude unreachable at $(date)" >> /var/log/teaagent-health.log
  # Trigger PagerDuty / OpsGenie / etc.
fi
```

### Approval backlog alert

```bash
#!/bin/bash
PENDING=$(teaagent approval pending | wc -l)
if [ "$PENDING" -gt 10 ]; then
  echo "WARN: $PENDING approvals pending in teaagent"
fi
```

---

## Dashboards

### Grafana (log-based)

If shipping audit logs to Loki or Elasticsearch, use these queries:

**Cost over time (Loki):**

```logql
sum_over_time(
  {service="teaagent"} | json | unwrap cost_usd [1h]
)
```

**Run success rate:**

```logql
rate({service="teaagent"} | json | status="ok" [5m])
/
rate({service="teaagent"} | json | __error__="" [5m])
```

**Tool call latency p95:**

```logql
quantile_over_time(0.95,
  {service="teaagent"} | json | unwrap latency_ms [5m]
)
```

---

## SLOs / SLIs

Recommended service-level objectives for production teaagent deployments:

| SLI | Measurement | SLO |
|-----|-------------|-----|
| Run success rate | % of runs completing without error | ≥ 95% over 7 days |
| Approval response time | Time from request to approval decision | ≤ 5 min p95 |
| Provider availability | % of API calls succeeding | ≥ 99% over 24 h |
| Audit log integrity | HMAC chain verification | 100% (zero tolerance) |
| Cost within cap | Daily spend vs. configured cap | 100% compliance |

---

## Alert Severity Levels

| Severity | Condition | Response |
|----------|-----------|----------|
| **CRITICAL** | Audit log integrity failure; cost cap breach > 100% | Immediate — page on-call |
| **HIGH** | Provider unreachable; disk < 10% free; run failure rate > 10% | Respond within 30 min |
| **MEDIUM** | Cost > 80% of cap; approval backlog > 10; agent timeout | Respond within 2 hours |
| **LOW** | Run failure rate > 5%; audit log > 500 MB; slow p95 latency | Respond same business day |

---

## See Also

- [Operations Manual](operations-manual.md)
- [Runbooks](runbooks.md)
- [Backup and Recovery](backup-and-recovery.md)
