# Audit Log Tampering Detection & Response (SEC-005)

> **Last updated:** 2026-06-07
> **Related:** `teaagent audit verify` command, `audit_chain.py`

---

## Overview

TeaAgent audit logs are append-only JSONL files with a cryptographic hash chain.
Each event contains a `hash` (SHA-256 of its canonical content) and a `prev_hash`
(pointer to the previous event's hash, or `"genesis"` for the first event).

The `teaagent audit verify` command checks the entire chain for tampering
indicators. It scans **all** events and reports every detected issue — it does
not stop at the first failure.

---

## Quick Start

### Running Verification

```bash
# Verify the default audit log
teaagent audit verify --root /path/to/repo

# Verify a specific run's log
teaagent audit verify --root /path/to/repo --run-id <run_id>

# Generate a detached signature after verification
teaagent audit verify --root /path/to/repo --signature ~/.ssh/id_ed25519
```

### Success Output

```
[Verifying...] Scanning audit events for tampering indicators...

[✓] Cryptographic Hash Chain: VALID (zero gaps, zero modifications, zero insertions).
[✓] Timestamp ordering: VERIFIED (no regressions).
[✓] Verified 142 audit events.
```

### Failure Output

```
[Verifying...] Scanning audit events for tampering indicators...

[✗] AUDIT CHAIN VERIFICATION FAILED — TAMPERING DETECTED
[✗] 3 integrity violation(s) found in 142 events.

Failure summary by category:
  Events inserted/deleted/reordered: 1
  Event content modified: 1
  Out-of-order timestamps: 1

Detailed failures:
  ✗ Event #73 (line 73): [prev_hash_mismatch] expected 'abc123...', got 'def456...'
  ✗ Event #74 (line 74): [hash_mismatch] hash mismatch — content may have been tampered
  ⚠ Event #120 (line 120): [timestamp_regression] 2026-06-01T12:00:00Z is earlier than previous event (2026-06-01T12:05:00Z)
```

---

## Tampering Indicators

The verifier detects five categories of integrity violations:

### 1. Hash Mismatch (`hash_mismatch`) — Severity: Error

**What it means:** The event's stored hash does not match the hash computed
from its current content. This indicates the event body was modified after it
was originally recorded.

**Response:**
- The event has been tampered with. Its contents cannot be trusted.
- Events **before** this one in the chain may still be valid (check the
  `prev_hash_mismatch` indicator for chain breakage).
- Review the event payload for unexpected changes.
- If the modification was authorized (e.g., redaction), re-issue the
  verification after the change to re-establish the chain.

### 2. Previous Hash Mismatch (`prev_hash_mismatch`) — Severity: Error

**What it means:** The event's `prev_hash` does not match the expected hash
of the preceding event. This indicates one of:
- An event was **inserted** into the chain (the next event still points to the old prev)
- An event was **deleted** from the chain (the next event points to a missing hash)
- Events were **reordered** (the prev_hash pointer is wrong)

**Response:**
- Examine the surrounding events for signs of insertion/deletion.
- Compare with backup copies of the log if available.
- If events were legitimately removed (e.g., retention policy), document
  the reason and note that chain integrity is broken from that point forward.

### 3. Timestamp Regression (`timestamp_regression`) — Severity: Warning

**What it means:** An event's `created_at` timestamp is earlier than the
previous event's timestamp. This indicates:
- Events may have been **reordered** in the file
- The system clock was **adjusted** between events
- Events were **backfilled** after the fact

**Response:**
- Check if the system experienced clock adjustments (NTP sync, manual changes).
- If paired with a `prev_hash_mismatch`, this strongly suggests reordering.
- If isolated, it may be benign (e.g., clock skew, batched writes).
- For compliance purposes, document any non-monotonic timestamps.

### 4. Missing Chain Fields (`missing_fields`) — Severity: Error or Warning

**What it means:** The event lacks `prev_hash` and/or `hash` fields. This
occurs when:
- The event was recorded before hash-chain support was added (legacy event)
- The event was tampered with and the fields were stripped

**Response:**
- Legacy events: The chain resets to genesis at that boundary. Events before
  and after the legacy event are independently verifiable, but continuity
  across the boundary cannot be proven.
- Non-legacy: Treat as tampering. The event should be re-recorded or
  redacted properly.

### 5. HMAC Mismatch (`hmac_mismatch`) — Severity: Error

**What it means:** The `chain_hmac` field does not match the HMAC-SHA256 of
the event hash keyed with the per-run secret. This indicates:
- The secret key has changed (e.g., key rotation)
- The event was tampered with by someone without the key
- The key file was corrupted or lost

**Response:**
- Verify the key file at `~/.teaagent/run-keys/<run_id>.key`.
- If the key was rotated, re-sign events after the rotation point.
- If no key is available, HMAC verification cannot be performed, but
  hash and prev_hash checks still apply.

---

## Programmatic Verification

```python
from pathlib import Path
from teaagent.audit_chain import verify_audit_chain

result = verify_audit_chain(Path('.teaagent/audit.jsonl'))

if result.valid:
    print(f"Chain valid: {result.event_count} events")
else:
    print(f"Chain broken: {len(result.failures)} failures")
    for f in result.failures:
        print(f"  Event #{f.event_number} (line {f.line_number}): "
              f"[{f.category}] {f.message}")

    # Access aggregate counts
    print(f"Hash mismatches: {result.total_hash_mismatches}")
    print(f"Prev-hash mismatches: {result.total_prev_hash_mismatches}")
    print(f"Timestamp regressions: {result.total_timestamp_regressions}")
```

---

## Recovery Steps

### If Tampering Is Detected

1. **Do not panic.** Hash chain breaks can have benign causes (legacy events,
   clock adjustments, authorized redactions).

2. **Isolate the log.** Copy the audit log to a secure location:
   ```bash
   cp .teaagent/audit.jsonl /secure/backup/audit-$(date +%Y%m%d-%H%M%S).jsonl
   ```

3. **Identify the scope.** Look at the failure report to determine:
   - Which events are affected (event numbers and line numbers)
   - Whether the break is isolated or cascading
   - Whether timestamps suggest reordering vs clock skew

4. **Check for legitimate causes:**
   - Were events redacted by an authorized process?
   - Did the system clock change (check NTP logs)?
   - Were legacy events present (indicated by `missing_fields`)?
   - Was the secret key rotated?

5. **Compare with backups:** If you maintain audit log backups or replicas,
   compare the affected events against a trusted copy.

6. **For confirmed tampering:**
   - Rotate the per-run secret key.
   - Generate a signed attestation of the current state:
     ```bash
     teaagent audit verify --root . --signature ~/.ssh/id_ed25519
     ```
   - Document the incident in your security log with the verification output.
   - Consider enabling compliance mode (`TEAAGENT_COMPLIANCE_MODE=1`) to
     enforce audit durability.

7. **For authorized modifications:**
   - Re-run verification to confirm the chain is now in a known state.
   - Document the modification reason and scope.
   - Consider exporting a compliance bundle before and after:
     ```bash
     teaagent audit export --run-id <id> --output before.json
     teaagent audit export --run-id <id> --output after.json
     ```

### Preventative Measures

- **Enable HMAC signing** by setting a per-run secret key.
- **Enable compliance mode:** `export TEAAGENT_COMPLIANCE_MODE=1`
- **Regular verification:** Schedule `teaagent audit verify` as part of
  your CI pipeline or a cron job.
- **Audit log backups:** Replicate `audit.jsonl` to a write-once medium.
- **Monitor for regressions:** Set up alerts on verification failures.
