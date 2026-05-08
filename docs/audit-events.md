# Audit Event Reference

TeaAgent audit logs are JSONL records emitted by `AuditLogger.record()`.

Machine-readable schema: [`docs/audit-event.schema.json`](audit-event.schema.json).

Each line has this envelope:

```json
{
  "event_id": "uuid-hex",
  "event_type": "tool_call_completed",
  "run_id": "run-id",
  "created_at": "2026-05-08T00:00:00+00:00",
  "payload": {}
}
```

## Schema

| Field | Type | Description |
|---|---|---|
| `event_id` | string | Unique event identifier. |
| `event_type` | string | Event name listed below. |
| `run_id` | string | Agent run identifier. |
| `created_at` | RFC3339 string | UTC creation timestamp. |
| `payload` | object | Event-specific payload after redaction. |

## Redaction

- Keys containing `api_key`, `authorization`, `credential`, `password`, `secret`, or `token` are redacted.
- Tool argument keys `command`, `content`, `new`, and `old` are redacted.
- Tool result keys `content`, `stderr`, `stdout`, and `text` are redacted.
- Long strings are truncated at 20,000 characters.

## Event Types

| Event | Producer | Payload |
|---|---|---|
| `run_started` | `AgentRunner.run` | `task`, `replayed_observations` |
| `iteration_started` | `AgentRunner.run` | `iteration` |
| `tool_call_pending_approval` | `AgentRunner.run` | `call_id`, `tool_name`, redacted `arguments`, `reason`, `annotations` |
| `tool_call_approved` | `AgentRunner.run` | `call_id`, `tool_name` |
| `tool_call_denied` | `AgentRunner.run` | `call_id`, `tool_name` |
| `tool_call_blocked` | `AgentRunner.run` | `call_id`, `tool_name`, redacted `arguments`, `reason`, `annotations` |
| `tool_call_started` | `AgentRunner.run` | `call_id`, `tool_name`, redacted `arguments`, `annotations` |
| `tool_call_completed` | `AgentRunner.run` | `call_id`, `tool_name`, redacted `result` |
| `context_compacted` | `AgentRunner.run` | `summary` |
| `run_paused` | `AgentRunner.run` | `status`, `approval`, `cost_cents` |
| `run_completed` | `AgentRunner.run` | `answer`, `metadata`, `cost_cents` |
| `run_failed` | `AgentRunner.run` | `category`, `message`, `cost_cents` |
| `heartbeat` | `Heartbeat.tick` | `tick`, `interval_seconds` |

## Compatibility

Audit events are append-only and versionless in the current format. Consumers should ignore unknown event types and unknown payload fields.
