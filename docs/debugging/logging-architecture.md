# Logging Architecture
# teaagent — 2026-06-02

How teaagent logs, what it logs, where it goes, and how to read it.

---

## 1. Logging Stack Overview

```
teaagent process
│
├── Python logging (stdlib)          ← per-module logger.{debug,info,warning,error}
│   └── No built-in basicConfig()   ← caller/wrapper must configure handler
│
└── Audit system (teaagent.audit)   ← structured AuditEvent objects
    ├── InMemoryMetricsSink         ← in-process counters (metrics)
    ├── TraceRecorder               ← in-process span list (tracing)
    ├── OTelAuditSink               ← OTLP HTTP export (optional)
    └── audit.jsonl                 ← append-only event log (on disk)
```

teaagent has **two independent logging channels**. Python `logging` carries developer-facing text messages. The `audit` system carries structured, machine-readable governance events. Both are needed for full observability.

---

## 2. Python Logging

### Logger naming

Every module declares: `logger = logging.getLogger(__name__)`

Logger names follow the Python package hierarchy:

| Logger name | Module |
|-------------|--------|
| `teaagent.tui` | `teaagent/tui/__init__.py` |
| `teaagent.approval_manager` | `teaagent/approval_manager.py` |
| `teaagent.budget_monitor` | `teaagent/budget_monitor.py` |
| `teaagent.context_bus` | `teaagent/context_bus.py` |
| `teaagent.coordinator` | `teaagent/coordinator.py` |
| `teaagent.audit` | `teaagent/audit.py` |
| `teaagent.cli._handlers._agent` | `teaagent/cli/_handlers/_agent.py` |
| `teaagent.cli._handlers._chat` | `teaagent/cli/_handlers/_chat.py` |

Parent `teaagent` covers all child loggers; set it to DEBUG to capture everything.

### Log levels used

| Level | Used for |
|-------|----------|
| `DEBUG` | Failure branches in code paths that are expected to succeed (e.g., SSH verification failure, LSP hydration miss, graph query failure, WAL checkpoint) |
| `INFO` | Significant operational milestones: agent generation, agent persistence, hot-reload, RAG delta archiving, OTel sink added |
| `WARNING` | Degradation or fallback activation: ANP routing fallback, federated-sync unavailable, approval using relaxed scope, cost threshold crossed |
| `ERROR` | Failures requiring human intervention: OTel enablement failure, DB critical errors, workflow validation failures |

### Log message format (recommended configuration)

```
2026-06-02T14:23:01.412Z WARNING  teaagent.budget_monitor  cost threshold 80% reached: 800/1000 cents
```

Format string: `"%(asctime)s %(levelname)-8s %(name)s  %(message)s"`

---

## 3. Audit Event System

Audit events are the primary observability surface for **runs, tools, and governance**. They are structured `AuditEvent` objects defined in `teaagent/audit.py`.

### AuditEvent schema

```json
{
  "event_id":   "uuid4",
  "event_type": "run_started | run_completed | run_failed | tool_call_started | tool_call_completed | session_suspended | ...",
  "run_id":     "uuid4",
  "created_at": "ISO-8601 UTC",
  "payload":    { ... event-specific fields ... }
}
```

Full schema: [`docs/audit-event.schema.json`](../audit-event.schema.json).
Narrative reference: [`docs/audit-events.md`](../audit-events.md).

### Event taxonomy

| Event type | Payload fields | Emitted by |
|-----------|---------------|-----------|
| `run_started` | `task`, `model`, `permission_mode`, `max_cost_cents` | `coordinator.py` |
| `run_completed` | `iterations`, `cost_cents`, `result_summary` | `coordinator.py` |
| `run_failed` | `error`, `cost_cents` | `coordinator.py` |
| `tool_call_started` | `call_id`, `tool_name`, `annotations`, `args_digest` | `tools.py` |
| `tool_call_completed` | `call_id`, `tool_name`, `duration_ms`, `status` | `tools.py` |
| `approval_requested` | `call_id`, `tool_name`, `path_scope`, `permission_mode` | `approval_manager.py` |
| `approval_granted` | `call_id`, `scope`, `rule_id` | `approval_manager.py` |
| `approval_denied` | `call_id`, `reason` | `approval_manager.py` |
| `session_suspended` | `run_id`, `observations_count`, `suspension_file` | `chat_repl.py` |
| `budget_warning` | `threshold_pct`, `current_cents`, `max_cents` | `budget_monitor.py` |

### Audit sinks

Sinks are registered via `audit.add_sink(sink)` at startup.

| Sink class | Where output goes | When active |
|-----------|-------------------|-------------|
| `InMemoryMetricsSink` | In-process dict (queryable) | Always |
| `TraceRecorder` | In-process `spans` list | Always |
| `OTelAuditSink` | OTLP HTTP endpoint | Only if `teaagent[telemetry]` installed and configured |
| File sink (built-in) | `~/.teaagent/audit.jsonl` | Always |

---

## 4. Correlation IDs

teaagent uses multiple correlation identifiers at different scopes:

| ID | Scope | Format | How to get it |
|----|-------|--------|---------------|
| `run_id` | A single agent run | UUID4 | Printed at run start; `teaagent agent list` |
| `event_id` | A single audit event | UUID4 | In `audit.jsonl` |
| `call_id` | A single tool call | UUID4 | In `tool_call_started` payload |
| `session_id` | An ACP protocol session | str | In ACP progress notifications |
| `correlation_id` | An ANP request | str | In ANP adapter payloads |
| W3C `traceparent` | An A2A delegation chain | `00-{32hex}-{16hex}-{2hex}` | `teaagent.a2a_trace.generate_traceparent()` |

### Tracing a run across all logs

1. Find the `run_id` from CLI output or `teaagent agent list`.
2. Filter `audit.jsonl`:
   ```bash
   grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl | python -m json.tool
   ```
3. For a tool call, find its `call_id` from `tool_call_started`, then grep for that `call_id`.
4. For A2A delegations, extract the `traceparent` from the run's attributes and search across sub-agent logs.

---

## 5. Metrics Available In-Process

`InMemoryMetricsSink` accumulates these counters and histograms during a process lifetime:

| Metric name | Type | Description |
|-------------|------|-------------|
| `agent.runs.started` | counter | Total runs initiated |
| `agent.runs.completed` | counter | Runs that completed normally |
| `agent.runs.failed` | counter | Runs that errored |
| `agent.tool_calls.started` | counter | Total tool invocations |
| `agent.tool_calls.started.<tool_name>` | counter | Per-tool invocation count |
| `agent.tool_calls.completed` | counter | Tool calls that returned |
| `agent.tool_calls.completed.<tool_name>` | counter | Per-tool completion count |
| `agent.run.iterations` | histogram | Turn count per run |
| `agent.run.cost_cents` | histogram | Cost in cents per run |

Query in code:

```python
from teaagent.telemetry import get_metrics_sink
snap = get_metrics_sink().snapshot()
print(snap.counters)
print(snap.histograms)
```

For OpenTelemetry export, install `teaagent[telemetry]` and set:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=teaagent
```

---

## 6. Known Logging Gaps

| Gap | Impact | Workaround |
|-----|--------|-----------|
| No `basicConfig()` at CLI entry — silent if no handler configured | DEBUG output invisible without a wrapper | Use `debug_runner.py` (see [Debug Mode](debug-mode.md)) |
| `chat_session_controller.py:143-159` swallows `AttributeError`/`TypeError` silently | Save errors are invisible in logs (DS-03) | Add `logger.warning` around the bare except |
| TUI `_session_cost_cents` never increments — no log warning (DS-01) | Cost accumulation bug is completely silent | Check audit `run_completed.cost_cents` instead |
| Suspension JSON audit field is stale after CG-10 (DS-04) | Two audit records per suspension with divergent timestamps | Treat `audit.jsonl` as authoritative, not `suspension-*.json` |
