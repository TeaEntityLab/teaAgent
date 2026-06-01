# audit — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/audit.py` | `AuditLogger`, redaction helpers, `AuditEvent` dataclass |
| `teaagent/audit_chain.py` | Hash-chain verification, `ChainVerificationResult`, `last_chain_hash` |
| `teaagent/audit_export.py` | Export helpers (JSON, CSV formats) |
| `teaagent/audit_viewer.py` | CLI-facing viewer, filtering, display |
| `teaagent/governance/audit_completeness.py` | Checks that required event types are present |
| `teaagent/telemetry/_audit.py` | OpenTelemetry sink adapter |

## Key Exports

### `teaagent/audit.py`
- `AuditEvent` — frozen dataclass: `event_type`, `run_id`, `payload`, `event_id`, `created_at`
- `AuditLogger` — primary class: `record()`, `add_sink()`, `enable_opentelemetry()`, `verify_chain_integrity()`
- `redact_audit_payload()` — recursively redacts sensitive fields
- `redact_sensitive_string()` — applies regex patterns
- `is_sensitive_key()` — key-name sensitivity check
- `secure_audit_dir()`, `secure_audit_file()` — chmod helpers
- Constants: `AuditLevel`, `MAX_AUDIT_STRING_LENGTH=20_000`, `AUDIT_REDACTED`, `AUDIT_TRUNCATED`

### `teaagent/audit_chain.py`
- `ChainVerificationResult` — frozen dataclass: `valid`, `event_count`, `error`
- `verify_audit_chain(log_path, secret_key?)` — reads JSONL, verifies SHA-256 chain + optional HMAC
- `compute_event_hash(obj)` — canonical SHA-256 over 6 chain fields
- `compute_chain_hmac(event_hash, secret_key)` — HMAC-SHA256 binding
- `last_chain_hash(log_path)` — tails the file to find `prev_hash` for next append

## Dependencies

```
audit.py
  ├── teaagent.storage.file_lock
  ├── teaagent.telemetry (optional, ImportError-guarded)
  └── teaagent.audit_chain (lazy import inside record())

audit_chain.py
  └── stdlib only (hashlib, hmac, json, pathlib)
```

## Entry Points

1. `runner/_core.py` — creates `AuditLogger(path=run_dir/"audit.jsonl")`, passes to agent loop
2. `cli/_handlers/_audit.py` — `audit_verify_command`, `audit_list_command`, `audit_show_command`
3. `chat_session_controller.py` — creates audit logger for chat sessions

## Call Graph

```
runner._core.AgentRunner.run()
  └── AuditLogger.record("run_started", ...)
      └── AuditLogger.record("tool_call_started", ...)
          └── [tool execution]
      └── AuditLogger.record("tool_call_completed" | "tool_call_failed", ...)
  └── AuditLogger.record("run_completed" | "run_failed", ...)

cli._handlers._audit.audit_verify_command()
  └── verify_audit_chain(path)
      └── compute_event_hash(obj) × N
```
