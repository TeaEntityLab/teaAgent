# ADR-0029: fcntl File Locking for Single-Node Write Concurrency

**Status:** Accepted  
**Date:** 2026-06-02  
**Deciders:** Core team  
**Related ADRs:** ADR-0008 (P4 Strategic Posture), ADR-0026 (JSONL Persistence)

---

## Context

Multiple processes may write to shared `.teaagent/` state files concurrently:
- The TUI REPL and a background runner may both append audit events
- Subagents spawned as separate processes share a parent's approval queue
- `teaagent approval subagents approve` (CLI) modifies a queue file while the parent run is reading it
- Swarm worktrees each write their own git branches but may share the gene pool JSONL

Without a concurrency mechanism, concurrent appends produce interleaved JSON lines that break parsers.

## Decision

Use `fcntl.LOCK_EX` (exclusive write lock) + `fcntl.LOCK_SH` (shared read lock) from Python's stdlib `fcntl` module, combined with the atomic-rename write pattern:

```python
# Write pattern (crash-safe):
tmp = target.with_suffix(".tmp")
tmp.write_text(content)
os.rename(tmp, target)  # atomic on POSIX

# Lock pattern:
with open(path, "a") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
    fh.write(line + "\n")
    fcntl.flock(fh, fcntl.LOCK_UN)
```

For approval queue files (read-modify-write), use `LOCK_EX` for the full read-parse-modify-write cycle.

## Consequences

**Positive:**
- Zero additional dependencies — `fcntl` is stdlib on all POSIX systems
- Kernel-enforced mutual exclusion — no userspace busy-wait
- Lock is automatically released if the process dies (kernel reclaims it)
- Works correctly for both intra-process threads and inter-process scenarios
- Atomic rename prevents partial reads during write — consumers never see half-written files

**Negative:**
- `fcntl` is not available on Windows — deployment on Windows requires a shim (`msvcrt.locking`) or SQLite
- NFS mounts do not honour `fcntl` locks reliably — explicitly documented as unsupported
- `flock` on macOS and Linux differ subtly (macOS: advisory only on local filesystems; Linux: same) — both work for our use case but are not perfectly identical
- Approval queue lock is held for the full read-parse-write cycle — starvation risk if a process hangs mid-cycle (mitigated by TTL cleanup)

## Alternatives Considered

### `threading.Lock`
- **Rejected:** Thread-local — provides no protection across process boundaries. Subagents are separate processes, so this is insufficient.

### SQLite with WAL mode as universal store
- **Rejected:** Works for concurrent readers, but changes the persistence format from human-readable JSONL to binary SQLite. Acceptable for the context bus (already uses SQLite WAL) but not justified for audit logs and approval queues.

### Redis or a message queue (ZeroMQ, etc.)
- **Rejected:** External service dependency. Defeats the "run with zero infra" posture. Appropriate if multi-node swarm becomes a hard requirement — see Upgrade Paths.

### `portalocker` (third-party cross-platform file locking)
- **Rejected:** Adds a dependency solely to support Windows, which is not currently a supported platform. Revisit when Windows support is explicitly prioritized.

### Advisory lock file (`<name>.lock` sentinel file)
- **Rejected:** Stale lock files after a crash require a GC mechanism. Kernel `flock` locks self-clean on process exit — strictly superior.

## Rationale

`fcntl.flock` is the POSIX primitive designed for exactly this pattern: multiple processes sharing files on a local filesystem. Combined with atomic rename (which is also a POSIX guarantee), it provides the crash safety and mutual exclusion we need without any additional infrastructure. The NFS limitation is a documented deployment constraint, not a code deficiency.

## Conditions to Reconsider

- If Windows becomes a supported platform → replace `fcntl` with `portalocker` or switch approval queues to SQLite
- If NFS deployments are required → migrate shared-state files to PostgreSQL or a lock service (etcd, Consul)
- If lock contention becomes observable (measurable wait times in approval queue operations) → implement lock-free append via O_APPEND + post-hoc deduplication
