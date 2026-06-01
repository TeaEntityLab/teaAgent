# Rejected Alternatives

What we evaluated, why we rejected it, and what would need to change to reconsider.  
Grouped by concern area. Cross-references the ADR where the decision is recorded.

---

## LLM Provider Integration

### Anthropic Python SDK / OpenAI SDK / litellm
**Rejected in:** ADR-0001, ADR-0027  
**Why:** Each SDK pulls ~8–50 transitive dependencies (httpx, anyio, pydantic, etc.), violating the zero-dependency P0 posture. SDK abstractions also hide provider-specific features behind a lowest-common-denominator interface.  
**To reconsider:** If a provider requires HTTP/2, WebSockets, or streaming framing that urllib cannot handle; or if a specific SDK becomes a de-facto standard adopted by >50% of the Python LLM ecosystem with a stable ABI.

### LangChain / LlamaIndex for RAG
**Rejected in:** ADR-0002  
**Why:** 50+ transitive dependencies. The in-memory RAG use case (embedding search over a context window) is served by ~30 lines of stdlib-compatible code using simple cosine similarity. These frameworks are designed for production vector database integrations, not in-session retrieval.  
**To reconsider:** If persistent vector search across multiple sessions is required, and the embedding index exceeds what fits in memory — at that point, LlamaIndex with a local vector store is appropriate.

---

## Storage

### SQLite as Universal Persistent Store
**Rejected in:** ADR-0026  
**Why:** Binary format is not grep-able or human-readable. Schema migration tooling burden for a rapidly evolving audit schema. Single-writer WAL mode doesn't improve over JSONL + fcntl for our access patterns. The one exception (context bus) uses SQLite WAL because concurrent cross-worktree reads are genuinely needed.  
**To reconsider:** If query complexity (cross-run correlation, time-range aggregation) justifies schema management; or if file size makes grep-based analysis impractical (>100 MB logs per run).

### PostgreSQL / Remote DB
**Rejected in:** ADR-0026, ADR-0008  
**Why:** External operational dependency defeats local/developer zero-infra usage. Connection management, migrations, and backups add operational surface. None of our current query patterns require relational joins.  
**To reconsider:** Multi-node deployment (multiple agents sharing state across machines) — at that point, JSONL + fcntl cannot provide the required consistency guarantees.

### MessagePack / CBOR / Protobuf
**Rejected in:** ADR-0026  
**Why:** Binary formats eliminate the human-readability benefit that is the primary reason for choosing JSONL over SQLite in the first place.  
**To reconsider:** If serialisation performance (currently not measured as a bottleneck) becomes a constraint.

---

## Concurrency

### threading.Lock for shared file state
**Rejected in:** ADR-0029  
**Why:** Thread-local — provides no mutual exclusion across process boundaries. Subagents are separate processes (spawned via `multiprocessing.Process`), so this is categorically insufficient.  
**To reconsider:** Never for file state shared across processes. Thread locks are appropriate for in-process data structures.

### portalocker (cross-platform file locking)
**Rejected in:** ADR-0029  
**Why:** Adds a dependency solely to support Windows, which is not a supported platform. The stdlib `fcntl` is correct and sufficient on POSIX.  
**To reconsider:** When Windows is explicitly added as a supported platform.

### Redis / ZeroMQ / message queue for approval routing
**Rejected in:** ADR-0022, ADR-0029  
**Why:** External service dependency. Approval queue semantics (JSON file with TTL cleanup) are simple enough that an in-process poll loop with file-based persistence is adequate.  
**To reconsider:** If swarm size exceeds ~20 concurrent subagents and approval queue polling becomes a CPU bottleneck; or if approval routing needs to cross network boundaries.

---

## Security / Sandboxing

### Python subinterpreters (PEP 554) for Code Mode isolation
**Rejected in:** ADR-0003  
**Why:** Not available in Python 3.10 (minimum supported version). Subinterpreters do not prevent shared global state mutation via C extension modules.  
**To reconsider:** When Python 3.14+ subinterpreters with full isolation (PEP 734) are widely deployed and the minimum supported version is raised.

### Docker per Code Mode execution
**Rejected in:** ADR-0003  
**Why:** ~1 second container startup latency per execution is unacceptable for interactive code mode where a user is waiting. Suitable for batch/background execution. Currently available as an opt-in (`DockerSandbox`) for higher-risk execution.  
**To reconsider:** For production deployments where the 1s overhead is acceptable and security requirements mandate full container isolation.

### gVisor / Firecracker for Phase 5 sandbox
**Rejected in:** ADR-0020  
**Why:** Requires system-level privileges and OS-specific configuration. Too operationally heavy for an agent that must run on a developer laptop. Docker + resource limits is a sufficient intermediate step.  
**To reconsider:** For cloud-deployed agent fleets where the operator controls the host OS and can provision gVisor/Firecracker at the infrastructure level.

### Blockchain / external timestamping (RFC 3161) for audit integrity
**Rejected in:** ADR-0030  
**Why:** External service dependency. Latency on every audit write. Blockchain has ordering/throughput issues incompatible with high-frequency event logging. RFC 3161 is appropriate for long-term legal evidence — overkill for an agent runtime.  
**To reconsider:** If legal or regulatory requirements mandate third-party notarisation of audit records.

### Per-event RSA/ECDSA signatures for audit integrity
**Rejected in:** ADR-0030  
**Why:** Key management overhead (generation, rotation, revocation). ~1ms/event CPU overhead for signing. Marginal security gain over HMAC-chain for single-operator deployments where the same party controls both the signing key and the audit log.  
**To reconsider:** Multi-party audit scenarios where different operators must independently verify that their peer did not alter the log — at that point, asymmetric signatures with hardware key storage are appropriate.

---

## Authentication

### Authlib / PyJWT for OAuth implementation
**Rejected in:** ADR-0004  
**Why:** Each library adds 5–15 dependencies. HMAC-SHA256 JWT and DPoP proof generation are 20–30 lines of stdlib code. The complexity of the full OAuth spec does not require a full library for the specific flows (auth code + PKCE + DPoP + refresh rotation) that TeaAgent implements.  
**To reconsider:** If TeaAgent needs to act as a full OAuth Authorization Server (consent screens, dynamic client registration) — at that point, Authlib is the right tool.

### Storing OAuth tokens in environment variables
**Rejected in:** ADR-0006  
**Why:** Environment variables leak to child processes and show up in `ps aux`. OAuthKeyRing with keychain backend (macOS Security framework, Linux Secret Service) is safer. SQLiteOAuthStore provides PBKDF2-SHA256 hashed client secrets as the default fallback.  
**To reconsider:** If the deployment environment has no keychain service (minimal containers) — the `InMemoryKeyRing` fallback already handles this with an explicit security warning.

---

## TUI / UX

### curses (stdlib)
**Rejected in:** ADR-0028  
**Why:** No Windows support. No built-in readline emulation. Screen arithmetic (move, addstr, clrtobot) is error-prone and produces unmaintainable code for a REPL. Zero-dependency but unacceptable ergonomics for a long-lived interactive session.  
**To reconsider:** Never as primary TUI — curses does not satisfy the completion and async output requirements. Could supplement `prompt-toolkit` for a full-screen cockpit pane.

### Textual (Textualize)
**Rejected in:** ADR-0028  
**Why:** Pulls in `rich` + `textual` (~4 MB). Widget/CSS reactive model is powerful for dashboards but heavyweight for a linear REPL chat flow. Adopting Textual would change the UX model from "readline-style interactive shell" to "TUI application with discrete widgets."  
**To reconsider:** If the cockpit (token count, cost, permission mode, subagent status) grows to require a true dashboard layout with live-updating widgets — Textual's `DataTable` and `ProgressBar` widgets would be a better fit than rolling custom `prompt-toolkit` layouts.

---

## Agent / Governance Frameworks

### Adopting vendor agent SDKs (Claude Agent SDK, OpenAI Agents, Google ADK, LangGraph)
**Rejected in:** ADR-0001  
**Why:** Governance-first requirements (approval policy, audit logging, budget enforcement, multi-sig quorum) are not configurable in vendor SDKs — they assume the vendor's own safety/oversight model. Vendor lock-in prevents provider-agnostic model routing. SDK update cadence does not match TeaAgent's release schedule.  
**To reconsider:** If a vendor SDK provides a formal governance plugin API that allows TeaAgent to own the approval/audit/budget primitives while delegating orchestration logic — at that point, the SDK becomes a viable orchestration layer underneath TeaAgent's governance shell.

### External consensus frameworks (Raft, Paxos) for swarm
**Rejected in:** ADR-0019  
**Why:** Raft and Paxos solve distributed log consensus — they are optimised for ensuring all replicas agree on a sequence of writes, not for agent-level task approval voting. The TeaAgent swarm voting model (N peers vote on a task proposal, result is a GO/NO-GO decision) is simpler and well-served by the purpose-built `ConsensusEngine` (~200 lines).  
**To reconsider:** If the swarm needs to maintain a globally consistent ordered log of task decisions across nodes (e.g., for replay/audit in a multi-node cluster) — at that point, a proper Raft implementation is appropriate.
