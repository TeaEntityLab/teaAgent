# Risk Report — audit chain tip resync

> **Claim class:** Risk note for one high-risk edit. Not current truth.
> **Last reviewed:** 2026-10-23

**Date:** 2026-10-23
**Scope:** `teaagent/audit.py` `AuditLogger.record` and `_chain_tip`
**High-risk path touched:** `teaagent/audit.py`

## What changes

`record` used to chain each new event from `self._prev_hash`, which was loaded once at startup. `file_lock` serialized writers, but a second `AuditLogger` on the same path still appended `prev_hash=genesis` (or whatever it had cached) after the first logger had moved the file forward. `verify_audit_chain` then failed with a prev-hash mismatch.

Under the same lock, `record` now reads the last event that has a `hash` and uses that as `prev_hash`. If that event's `created_at` is later than this process's cached timestamp, the new event's timestamp is not allowed to move backward past it. Lines without a hash are skipped, same as startup recovery. A missing or empty file still starts at `genesis`.

## Risk assessment

- **Blast radius:** every durable `AuditLogger.record` call does one extra tail read of the log file while it already holds the lock. Single-writer chains keep the same hashes they would have had, because the tip matches the cache. Multi-writer chains change from forked to linear.
- **Failure mode:** a tip read that raises `OSError` takes the existing disk-error path (compliance mode raises; otherwise the write is skipped and the consecutive-failure counter moves). A corrupt tail is skipped until a hashed line is found, or the event chains from `genesis` if the file has no hashed line, which matches startup.
- **What this does not do:** it does not repair an already forked file. It does not change redaction, HMAC key selection, or event types. The same file no longer imports OpenTelemetry at import time; `enable_opentelemetry` imports it when called. `record` does not, and the hash chain is unchanged by that import move.
- **Rollback:** revert the `record` hunk and `_chain_tip`. New appends go back to the in-memory tip. Existing valid chains remain valid.

## Tests

`tests/test_audit_chain_tip_resync.py` opens two loggers, lets each append after the other, and requires `verify_audit_chain(..., strict=True)` to pass, including when the intervening event is larger than the first read window. `tests/test_audit.py` and `tests/test_ws3_audit_chain_remaining.py` passed after the change.

## Decision

Proceed. The lock was necessary and not sufficient. A second process is the normal shape of a command hook, and it is also a normal shape of two runtimes sharing a log. The fix is the smaller integrity change; it does not add an enforcement mode.
