# ADR-0026: JSONL Newline-Delimited JSON as Canonical Persistent Storage

**Status:** Accepted  
**Date:** 2026-06-02  
**Deciders:** Core team  
**Related ADRs:** ADR-0008 (P4 Strategic Posture), ADR-0009 (5-Loop Governance), ADR-0030 (Hash-Chained Audit)

---

## Context

TeaAgent needs to persist:
- Audit events (append-only, high frequency)
- Run records and summaries
- Plan history and contracts
- Approval queues (transient, per-parent-run)
- Prompt gene pool (evolutionary, append-dominant)
- Memory invalidation rules

These stores have different access patterns: audit events are write-once-read-occasionally; approval queues are read-modify-write with short TTL; plan history is read-dominant. The storage format must be inspectable without tooling (developer ergonomics), append-efficient, and portable across deployments.

## Decision

Use newline-delimited JSON (JSONL) as the canonical format for all persistent state, with:
- `fcntl.LOCK_EX` for write exclusion (single-node)
- Atomic rename via `write-to-temp + os.rename()` for crash safety
- `WAL` mode for the context-bus SQLite store (the one exception — cross-sandbox sharing requires concurrent reads)
- Files stored under `.teaagent/` workspace directory per project

## Consequences

**Positive:**
- Human-readable without tooling — `grep`, `jq`, `cat` work natively
- Append-only for audit/gene-pool — no read-modify-write, minimal lock contention
- No schema migration tooling needed — add fields freely, ignore unknown keys
- Trivially backed up with `cp` or `rsync`
- Exact format for GitHub CI artifact upload (ADR-0009 Loop 3)

**Negative:**
- No cross-file ACID transactions — approval queue + audit log update cannot be atomic
- No query language — must `grep` or parse in Python; slow for large files
- No referential integrity — a plan reference in an audit event is not enforced
- `fcntl` is POSIX-only; Windows deployments require a compatibility shim
- NFS mount support is explicitly unsupported (documented limitation, not a bug)

## Alternatives Considered

### SQLite as primary store
- **Rejected:** Binary format (not `grep`-able), schema migration complexity for evolving audit schema, WAL mode still single-writer, adds SQLite schema management burden. Kept for context-bus (cross-sandbox concurrent reads), but not as the general store.

### PostgreSQL
- **Rejected:** External operational dependency, connection management, migration tooling, defeats zero-external-service posture for local/developer usage. Would be the right choice for multi-node deployment — see Upgrade Paths.

### Raw JSON (whole-file)
- **Rejected:** Requires full file read + rewrite on every append. Under high audit event frequency (many tool calls per second), this is O(n) per write and risks corruption if process is killed mid-write.

### MessagePack / CBOR
- **Rejected:** Not human-readable, no tooling advantage over SQLite, adds binary format parser dependency.

## Rationale

The primary users of stored data are developers debugging agent runs, not query engines. Readability without tooling outweighs query convenience at single-node scale. JSONL's append-only characteristic aligns perfectly with audit log semantics — events are immutable once written. The atomic-rename pattern provides the crash safety guarantee without needing a WAL.

## Conditions to Reconsider

- If audit event volume exceeds ~10K events/run regularly → partition by run or switch to SQLite per run
- If multi-node deployment is required → PostgreSQL with pgcrypto for hash-chain verification
- If Windows support is required → replace `fcntl` with `msvcrt.locking` or use SQLite uniformly
