# audit — Behavior Specification

## Purpose

Provides tamper-evident, append-only audit logging with SHA-256 hash chaining, HMAC signing, and tiered redaction. Every agent tool call, approval decision, and run lifecycle event is recorded here.

## Behavior Contract

1. **Append-only** — `AuditLogger.record()` only appends; no existing event is ever modified.
2. **Tiered redaction** — Before any event is persisted, payload is filtered through the configured `AuditLevel` and then pattern-redacted.
3. **Hash chain** — Each persisted line carries `prev_hash` (SHA-256 of the prior line's canonical JSON) and `hash` (SHA-256 of the current canonical JSON). The first line uses the sentinel `"genesis"`.
4. **HMAC integrity** — Each event also carries `chain_hmac` (HMAC-SHA256 of `hash` keyed with `_chain_key`, a 32-byte random per-run secret). This prevents forgery even if the file is writable.
5. **Disk error isolation** — If a disk write fails, the error is recorded in-memory as a `_disk_write_error` synthetic event. A 30-second cooldown prevents log spam; writes are retried after cooldown.
6. **Sink fan-out** — After write, all registered sinks (OpenTelemetry, custom callables) receive the raw `AuditEvent`. Sink failures are logged but do not abort the run.
7. **Thread safety** — `self._lock` protects in-memory state. File writes use `file_lock(path)` from `teaagent.storage`. **These two locks are never held simultaneously** (deadlock prevention invariant).
8. **Secure permissions** — Audit directory: mode `0o700`. Audit file: mode `0o600`.

## Audit Levels

| Level | What is kept |
|-------|-------------|
| L0 | `event_type`, `timestamp` only — metrics |
| L1 | All metadata fields; strips `arguments`, `result`, `content`, `output`, `input`, `reasoning` |
| L2 | Full payload with pattern-based redaction applied (default) |
| L3 | Full payload, no redaction — encrypted at rest using Fernet (AES-128 in CBC mode) |

## State Machine

```
[AuditLogger created]
  → prev_hash = "genesis"
  → path set, dir secured (0o700)

record(event_type, run_id, **payload)
  ├── apply_audit_level(payload)
  ├── redact_audit_payload(...)
  ├── [lock] append to self.events
  └── [file_lock(path)]
        ├── last_chain_hash(path) → prev
        ├── compute SHA-256 → current_hash
        ├── compute HMAC → chain_hmac
        ├── append JSON line to file
        ├── fsync()
        └── secure_audit_file(path)
  └── fan-out to sinks
```

## Invariants

- `events[i].prev_hash == sha256(canonical(events[i-1]))` for all i > 0
- `events[0].prev_hash == "genesis"`
- Audit file permissions never exceed `0o600`
- `self._lock` and `file_lock` are never held simultaneously
- Redaction runs before persistence at all non-L3 audit levels (L0-L2); L3 skips redaction

## Known Caveats

- L3 encryption key is stored on the same host (~/.teaagent/audit-encryption/), so encryption protects against log file copying but not host/user compromise.
- L3 logs can be decrypted using `AuditLogger.decrypt_audit_log()` or the `teaagent audit decrypt` CLI command for post-mortem analysis.
- Redaction is best-effort for structured data; a novel credential format may escape patterns.
- `chain_hmac` uses `hmac.new()` (Python 3.14+ deprecates `hmac.new`; see `audit_chain.py:78`).

## L3 Decryption

L3 audit logs are encrypted at rest using Fernet (AES-128 in CBC mode). To decrypt L3 logs for post-mortem analysis:

### Programmatic Decryption

```python
from teaagent.audit import AuditLogger
from pathlib import Path

# Decrypt with automatic key loading from ~/.teaagent/audit-encryption/<run_id>.enc
result = AuditLogger.decrypt_audit_log(Path('.teaagent/audit.jsonl'))
events = result['events']
chain_valid = result['chain_valid']
chain_errors = result['chain_errors']

# Decrypt with explicit key
from cryptography.fernet import Fernet
key = Fernet.generate_key()
result = AuditLogger.decrypt_audit_log(Path('.teaagent/audit.jsonl'), encryption_key=key)
```

### CLI Decryption

```bash
# Decrypt with automatic key loading
teaagent audit decrypt .teaagent/audit.jsonl

# Decrypt with explicit key file
teaagent audit decrypt .teaagent/audit.jsonl --key ~/.teaagent/audit-encryption/custom-key.enc
```

### Chain Integrity Verification

The `decrypt_audit_log` method and CLI command automatically verify the hash chain integrity during decryption. The output includes:
- `chain_valid`: Boolean indicating whether the chain is intact
- `chain_errors`: List of any hash chain validation errors
- `total_events`: Total number of events in the log
- `events`: The decrypted event list

If `chain_valid` is `false`, the audit log may have been tampered with. Run `teaagent audit verify` for detailed verification.

### Key Storage

- Encryption keys are stored in `~/.teaagent/audit-encryption/<run_id>.enc`
- Keys are 44 bytes (Fernet key length)
- Key directory permissions: `0o700`
- Key file permissions: `0o600`
