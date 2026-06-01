# audit — Risk Vectors & Known Issues

## AUD-R-001: L3 plaintext storage
**File**: `audit.py:163-196`
**Risk**: L3 audit level stores full tool arguments (including `content`, `command`, `new`, `old`) in plaintext. No encryption at rest.
**Failure mode**: Audit file leak exposes secret credentials, file contents, or user data.
**Mitigation**: Use L2 (default). Document L3 as "local trace only, never ship."

## AUD-R-002: Regex redaction is incomplete
**File**: `audit.py:48-67`
**Risk**: `SENSITIVE_STRING_PATTERNS` covers `Bearer`, `sk-*`, JWT, AKIA, GitHub PAT. It does NOT cover: Anthropic API keys (non-sk- prefixes), database connection strings, GCP service account JSON, SSH private keys.
**Failure mode**: A novel credential format passes through unredacted at L2.
**Mitigation**: Expand patterns; consider a pluggable `redaction_config` (the `RedactionConfig` hook already exists but defaults are thin).

## AUD-R-003: Disk error silently swallows events
**File**: `audit.py:298-306`
**Risk**: A 30-second cooldown after an `OSError` means all events during cooldown are in-memory only. In-memory events are lost on crash.
**Failure mode**: Audit record gaps after disk full / permission error.
**Mitigation**: Alert (currently logs) on first disk error; consider write-ahead buffer to secondary path.

## AUD-R-004: `hmac.new()` deprecated
**File**: `audit_chain.py:78`
**Risk**: Python 3.14 deprecates `hmac.new()`; will raise `DeprecationWarning` or eventually `AttributeError`.
**Failure mode**: Chain HMAC computation breaks on future Python versions.
**Fix**: Replace `hmac.new(...)` with `hmac.HMAC(...)`.

## AUD-R-005: `last_chain_hash` tail truncation
**File**: `audit_chain.py:172-200`
**Risk**: `last_chain_hash` reads only the last 4096 bytes of the file. If the last valid JSON line is >4096 bytes, it falls back to full-file scan. If full scan also fails, returns `"genesis"`, breaking the chain.
**Failure mode**: Hash chain reset (apparent tampering) for very large audit payloads.

## AUD-R-006: Thread-safety comment vs. reality
**File**: `audit.py:252`
**Risk**: The comment "SAFETY: self._lock and file_lock must never be held simultaneously" is advisory only — no runtime enforcement. A future developer could accidentally nest them.
**Failure mode**: Deadlock.

## AUD-R-007: Sink exceptions swallowed
**File**: `audit.py:308-318`
**Risk**: Sink failures (`except Exception`) are logged at `ERROR` but do not propagate. A broken OTel sink will silently lose telemetry.
**Failure mode**: Silent telemetry loss.

## Known TODO / Limitations
- `governance/audit_completeness.py` — not wired into the default runner; must be called explicitly.
- `audit_export.py` — export to CSV truncates payload JSON; long payloads truncated without warning.
