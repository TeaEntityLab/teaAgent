# Upgrade Paths

For each major component, the viable evolution paths: what to change, what new dependencies or infrastructure it requires, and what assumptions must be revisited.

---

## 1. Storage: JSONL → Relational Database

**Current state:** JSONL files under `.teaagent/`, `fcntl.LOCK_EX` for write exclusion (ADR-0026, ADR-0029).  
**Driver to upgrade:** Multi-node deployment, cross-run query requirements, or audit log size exceeding grep practicality.

### Path A: SQLite per Run
- Replace per-project JSONL with one SQLite file per run (`<run_id>.db`)
- Use WAL mode; concurrent read is native
- `teaagent audit verify` uses SQL aggregation instead of file scan
- **Effort:** Medium. Schema migration tooling needed. Hash-chain query must be adapted.  
- **Preserves:** Single-node posture, local file portability  
- **Breaks assumption:** A3 (audit file is grep-able)

### Path B: PostgreSQL Shared Store
- Audit events, run records, approval queues → PostgreSQL tables
- Hash chain stored as a computed column or trigger-maintained field
- `fcntl` locking replaced by `SELECT FOR UPDATE` or advisory locks
- **Effort:** High. Connection management, migration scripts, schema versioning.  
- **Requires:** PostgreSQL instance, `psycopg2` or `asyncpg` dependency  
- **Enables:** Multi-node swarm (assumption S1 lifted), cross-run query API  
- **Breaks assumption:** D2 (POSIX local filesystem)

### Migration Strategy
Run JSONL and SQLite in parallel via `WriteThroughStore` adapter for one release cycle. Validate hash-chain parity before cutting over. Provide `teaagent migrate-store sqlite` CLI command.

---

## 2. LLM Adapter: urllib → SDK or httpx

**Current state:** stdlib `urllib` HTTP adapter per provider (ADR-0027).  
**Driver to upgrade:** Provider requires HTTP/2 or WebSocket; connection pooling becomes measurable latency; provider API change frequency exceeds quarterly maintenance window.

### Path A: Add `httpx` as optional dep
- Replace `UrllibHTTPTransport` with `HttpxTransport` implementing the same interface
- Connection pooling and HTTP/2 are automatic
- **Effort:** Low. The `HTTPTransport` interface is already in place (ADR-0027).  
- **Install:** `pip install teaagent[http2]`  
- **Breaks assumption:** P0 zero-dependency posture (optional dep only — acceptable)

### Path B: Official SDK as optional dep per provider
- Implement `AnthropicSDKAdapter(LLMAdapter)` wrapping `anthropic.Anthropic` client
- Select via `TEAAGENT_USE_ANTHROPIC_SDK=1` env var
- **Effort:** Medium. SDK must be isolated to avoid import-time side effects.  
- **Benefit:** Automatic SDK updates for API changes; built-in prompt caching headers  
- **Risk:** SDK version pins conflict with other project deps

---

## 3. Concurrency: fcntl → Multi-Node Coordination

**Current state:** `fcntl.LOCK_EX` + atomic rename for single-node concurrency (ADR-0029).  
**Driver to upgrade:** Swarm requires coordination across multiple hosts.

### Path A: Redis-backed Distributed Lock
- Replace `fcntl.flock()` calls with `RedisLock` using Redlock algorithm
- Approval queues become Redis hashes/lists
- **Effort:** Medium. Redis client dependency (`redis-py`). Operator must provision Redis.  
- **Install:** `pip install teaagent[distributed]`  
- **Breaks assumption:** S1 (single-node), D3 (requires external service)

### Path B: PostgreSQL Advisory Locks
- If Path B of storage upgrade (PostgreSQL) is already in place, use `pg_advisory_lock(key)` for mutual exclusion
- No additional dependencies
- **Effort:** Low (given PostgreSQL is already deployed)  
- **Elegant:** Locks and data in the same database; lock release is automatic on connection loss

### Path C: etcd / Consul for Lightweight Coordination
- Use etcd's distributed lease/lock for concurrency, keep JSONL for data
- **Effort:** High. Two external services (etcd + PostgreSQL or etcd + JSONL on shared FS).  
- **Use case:** Kubernetes-based deployments where etcd is already available

---

## 4. Code Mode Sandbox: Process-Level → Docker → gVisor

**Current state:** `multiprocessing.Process` with AST allow-list, RLIMIT_CPU, RLIMIT_AS (advisory on macOS) (ADR-0003).  
**Driver to upgrade:** Production deployment with untrusted LLM-generated code.

### Path A: Docker per Execution (already partially implemented)
- `DockerSandbox` is available today; `SkillRouter` routes high-risk tasks to Docker
- Operator enables by setting `CODE_MODE_SANDBOX=docker`
- **Effort:** Zero code change. Operator effort to provision Docker.  
- **Trade-off:** ~1s startup latency per execution (ADR-0003, rejected for interactive mode)  
- **Accepts assumption change:** A3 (runs may take longer due to container overhead)

### Path B: Pre-warmed Docker Pool
- Maintain a pool of N warm containers; reuse containers with tmpfs reset between executions
- Reduces startup latency from ~1s to ~50ms
- **Effort:** High. Pool management, container health checks, tmpfs reset verification.

### Path C: WebAssembly (WASM) Runtime
- `WasmSkillRuntime` is already implemented (ADR-0020)
- Skills compiled to WASM run in a memory-safe sandbox with no system call access
- **Limitation:** Python code cannot run in WASM today; requires skills to be written in Rust/Go and compiled to WASM, or using Pyodide (WebAssembly Python interpreter)  
- **Effort:** High for Python-in-WASM. Low for Rust/Go skills.

### Path D: gVisor / Firecracker (cloud deployments)
- Wrap Docker execution in gVisor's `runsc` runtime or Firecracker microVM
- Full kernel-level isolation with near-native performance
- **Effort:** Infrastructure-level change. Requires cloud operator control of container runtime.  
- **Use case:** Multi-tenant cloud service where different operators' agents run on the same host

---

## 5. Consensus: In-Process → Raft-Based Distributed Consensus

**Current state:** Purpose-built `ConsensusEngine` with in-memory peer registry and vote tracking (ADR-0019).  
**Driver to upgrade:** Swarm must maintain a globally consistent ordered log of task decisions across multiple hosts with guaranteed linearisability.

### Path A: Extend Current Engine with Persistence
- Persist peer votes and proposal state to JSONL (today: in-memory only)
- Peer state survives process restart; votes are replay-safe
- **Effort:** Low. Already have JSONL infrastructure.  
- **Limitation:** Still single-node — does not provide distributed consensus, only durable local consensus

### Path B: Raft via `raft-python` or gRPC-based Raft
- Replace `ConsensusEngine` with a Raft group where each swarm coordinator is a replica
- Proposals are Raft log entries; commit = consensus reached
- **Effort:** Very High. Raft implementation or integration, network partition handling, leader election.  
- **Use case:** Multi-datacenter agent swarms with strict consistency requirements

### Path C: etcd as Consensus Backend
- Delegate consensus to etcd; use etcd transactions for atomic vote submission and quorum check
- `ConsensusEngine` becomes a thin client to etcd
- **Effort:** High. External service. But etcd is production-hardened and well-understood.  
- **Trade-off:** Adds operational dependency; gains production-grade consensus

---

## 6. Authentication: HMAC JWT → Full PKI

**Current state:** HMAC-SHA256 JWTs with optional DPoP (ES256/RS256) for bound tokens (ADR-0004).  
**Driver to upgrade:** Multi-tenant deployment with independently verifiable tokens; regulatory requirement for asymmetric signatures.

### Path A: RS256 / ES256 JWTs with Key Distribution
- Already optional via `pip install teaagent[oauth]` + `cryptography` dep
- Publish JWKS endpoint for third-party token verification
- **Effort:** Low (infrastructure exists). Operator generates key pair and configures JWKS endpoint.

### Path B: Full PKI with Certificate Chain
- Issue per-agent X.509 certificates signed by a TeaAgent CA
- Token verification uses certificate chain, not shared HMAC secret
- **Effort:** Medium. CA management tooling, certificate rotation, CRL/OCSP.  
- **Use case:** Enterprise deployment where each agent's identity must be independently auditable

---

## 7. TUI: prompt-toolkit → Textual Dashboard

**Current state:** `prompt-toolkit` REPL loop with completion and async output (ADR-0028).  
**Driver to upgrade:** Cockpit requires live-updating widgets (running cost graph, subagent status panel, token waterfall).

### Migration Path
- Keep `prompt-toolkit` for the input pane (readline-style is appropriate for commands)
- Add `textual` for the output/cockpit pane as a split layout
- Both can coexist in separate threads (TUI input on main thread, Textual app on worker)
- **Effort:** Medium. Textual's async model requires careful integration with existing sync/async bridge.  
- **Install:** `pip install teaagent[tui-rich]`

---

## 8. Audit Log: HMAC Chain → Externally Verifiable Signatures

**Current state:** HMAC-SHA256 chain with per-project key (ADR-0030).  
**Driver to upgrade:** Multi-party audit (regulator must verify independently of the operator).

### Path A: Ed25519 Per-Event Signatures
- Sign each event with an Ed25519 private key held in hardware (TPM, HSM, YubiKey)
- Public key published for independent verification
- **Effort:** Medium. Key management tooling. ~0.1ms/event signing overhead.

### Path B: RFC 3161 Timestamping
- Submit a hash of each audit batch to an external timestamping authority
- Provides third-party notarisation of "this batch existed at time T"
- **Effort:** Low code change (HTTP call to TSA). External service dependency.  
- **Use case:** Legal evidence preservation where third-party timestamp is required
