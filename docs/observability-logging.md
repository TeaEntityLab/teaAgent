# Observability: Structured Logging

TeaAgent supports structured JSON-line logging for machine-readable observability, compatible with log aggregation tools (Loki, Datadog, ELK).

## Enabling JSON Logging

Use the `--log-format=json` CLI flag:

```bash
teaagent --log-format=json agent run gpt "summarize tests"
```

This configures all root log handlers to use `JsonLogFormatter` which emits one JSON object per line (NDJSON).

During an agent run, `AgentRunner` injects the current `run_id` into every log record via `setup_run_logging()`.

## Standard Log Keys

Every JSON log line includes these top-level keys:

| Key | Type | Description |
|------|------|-------------|
| `timestamp` | string | ISO 8601 UTC timestamp |
| `level` | string | Log level (DEBUG, INFO, WARNING, ERROR) |
| `logger` | string | Logger name (e.g. `teaagent.runner.core`) |
| `module` | string | Short module name (last component of logger) |
| `message` | string | Human-readable log message |
| `run_id` | string | Current agent run ID (when inside a run) |

### Event-Specific Keys

The following keys appear on events that provide them via `extra` dict:

| Key | Type | Example | Used By |
|------|------|---------|---------|
| `event` | string | `tool_executed`, `rate_limit_exceeded` | All modules |
| `duration_ms` | float | `12.34` | Tool execution, LLM calls |
| `error_code` | string | `RATE_LIMIT`, `AUDIT_DISK_WRITE` | Error/warning events |
| `tool_name` | string | `workspace_read_file` | Tool execution events |
| `provider` | string | `gpt`, `claude` | LLM adapter events |
| `call_id` | string | `abc123` | Tool call approval events |

Any additional keys from the `extra` dict are included in the JSON output.

## Example Output

```json
{"timestamp": "2026-06-08T00:00:00.000000+00:00", "level": "INFO", "logger": "teaagent.runner._core", "module": "_core", "message": "workspace_read_file completed", "run_id": "abc123", "event": "tool_executed", "duration_ms": 1.5, "tool_name": "workspace_read_file"}
{"timestamp": "2026-06-08T00:00:01.000000+00:00", "level": "WARNING", "logger": "teaagent.llm._adapters", "module": "_adapters", "message": "rate_limit_exceeded: ...", "run_id": "abc123", "event": "rate_limit_exceeded", "provider": "gpt", "error_code": "RATE_LIMIT"}
```

## Instrumented Modules

The following modules emit structured log events with standard keys:

| Module | Events |
|--------|--------|
| `teaagent/runner/_core.py` | `tool_executed` (with `duration_ms`) |
| `teaagent/audit.py` | `audit_sink_failed`, `audit_disk_write_failed` |
| `teaagent/approval/manager.py` | `tool_permission_denied` (with `error_code`) |
| `teaagent/tools.py` | `tool_executed` (with `duration_ms`) |
| `teaagent/llm/_adapters.py` | `rate_limit_exceeded` (with `error_code`) |

## Integration

To ship structured logs to an observability backend:

```bash
teaagent --log-format=json agent run gpt "..." 2>&1 | your-log-shipper
```

Or redirect to a file:

```bash
teaagent --log-format=json agent run gpt "..." 2> audit.jsonl
```
