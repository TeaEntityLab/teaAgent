# audit — Public API Reference

## `AuditEvent` (frozen dataclass)
**Location**: `audit.py:75`

```python
@dataclass(frozen=True)
class AuditEvent:
    event_type: str          # e.g. "run_started", "tool_call_completed"
    run_id: str              # UUID of the run
    payload: dict[str, Any]  # redacted event data
    event_id: str            # UUID hex (auto-generated)
    created_at: str          # ISO 8601 UTC timestamp
```

**Method**: `to_json(*, prev_hash, event_hash, chain_hmac) -> str` — JSON-serialized with chain fields.

---

## `AuditLogger`
**Location**: `audit.py:104`

### `__init__`
```python
AuditLogger(
    path: Optional[Path] = None,
    *,
    redaction_config: Optional[Any] = None,
    audit_level: AuditLevel = 'L2',
)
```
- **Pre**: If `path` is set, its parent directory must be creatable.
- **Post**: Audit directory secured to `0o700`. `_chain_key` = 32 random bytes.

### `record`
```python
def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent
```
- **Pre**: none
- **Post**: Event appended to `self.events`. If `path` set and disk healthy: event appended to JSONL file, fsync'd, file secured.
- **Returns**: The recorded `AuditEvent`.
- **Side effects**: Calls all registered sinks. Records `_disk_write_error` on `OSError`.

### `add_sink`
```python
def add_sink(self, sink: Callable[[AuditEvent], None]) -> None
```
Registers a callable to receive every event after recording. Thread-safe (copy-on-read pattern).

### `enable_opentelemetry`
```python
def enable_opentelemetry(
    self,
    *,
    endpoint: Optional[str] = None,
    service_name: str = 'teaagent',
    service_version: str = '1.0.0',
) -> None
```
Adds an OTel OTLP sink. No-op if `opentelemetry` not installed.

### `verify_chain_integrity`
```python
def verify_chain_integrity(self) -> dict[str, Any]
```
Returns `{'valid': bool, 'total_events': int, 'errors': list[str]}`.

### `disk_error` (property)
Returns the most recent `OSError` if within 30-second cooldown, else `None`.

### `get_chain_key`
```python
def get_chain_key(self) -> bytes
```
Returns the 32-byte HMAC secret for external chain verification.

---

## Free Functions (`audit.py`)

### `redact_audit_payload(payload, *, string_patterns) -> dict`
Recursively redacts `arguments` and `result` sub-dicts, then applies string patterns to remaining fields.

### `redact_sensitive_string(value, *, patterns) -> str`
Applies all regex patterns to a string value.

### `is_sensitive_key(key: str) -> bool`
Returns `True` if `key` (lowercased, `-`→`_`) contains any of: `api_key`, `authorization`, `credential`, `password`, `secret`, `token`.

### `secure_audit_dir(path: Path) -> None`
`path.chmod(0o700)`.

### `secure_audit_file(path: Path) -> None`
`path.chmod(0o600)`.

---

## `ChainVerificationResult` (frozen dataclass)
**Location**: `audit_chain.py:43`

```python
@dataclass(frozen=True)
class ChainVerificationResult:
    valid: bool
    event_count: int
    error: Optional[str] = None  # first failure description
```

---

## Free Functions (`audit_chain.py`)

### `verify_audit_chain(log_path, secret_key?) -> ChainVerificationResult`
Reads JSONL file, verifies SHA-256 chain continuity and (if `secret_key` provided) HMAC per event. Legacy events without chain fields are skipped. Returns on first error.

### `compute_event_hash(obj: dict) -> str`
SHA-256 of canonical JSON over 6 fields: `event_id`, `event_type`, `run_id`, `created_at`, `payload`, `prev_hash`.

### `compute_chain_hmac(event_hash: str, secret_key: bytes) -> str`
HMAC-SHA256 of `event_hash` keyed with `secret_key`.

### `last_chain_hash(log_path: Path) -> str`
Returns the `hash` field of the last chained event, or `"genesis"`. Tails 4096 bytes; falls back to full scan for large files.

---

## Data Model

```
AuditEvent persisted as JSONL:
{
  "event_id":   "hex UUID",
  "event_type": "tool_call_started",
  "run_id":     "hex UUID",
  "created_at": "2026-06-02T12:00:00.000000+00:00",
  "payload":    { ... redacted ... },
  "prev_hash":  "sha256hex | genesis",
  "hash":       "sha256hex",
  "chain_hmac": "hmac-sha256-hex"
}
```

## Standard Event Types

| `event_type` | Emitted by |
|---|---|
| `run_started` | `runner._core` |
| `iteration_started` | `runner._core` |
| `tool_call_started` | `runner._core` |
| `tool_call_completed` | `runner._core` |
| `tool_call_failed` | `runner._core` |
| `approval_required` | `approval_manager` |
| `approval_granted` | `approval_manager` |
| `approval_denied` | `approval_manager` |
| `run_completed` | `runner._core` |
| `run_failed` | `runner._core` |
| `_disk_write_error` | `AuditLogger` internal |
