# TeaAgent Architecture

## System Overview

TeaAgent is a thin governance-first agent harness. It does not implement its own
LLM framework — it connects to model providers through adapters and enforces
safety boundaries around tool execution.

```
┌─────────────────────────────────────────────────────────────┐
│                          CLI / TUI                           │
├─────────────────────────────────────────────────────────────┤
│                      ModelDecisionEngine                     │
│  (prompt assembly → JSON parsing → structured decisions)    │
├──────────────────────┬──────────────────────────────────────┤
│     AgentRunner       │          ChatAgentConfig             │
│  (decision loop,      │    (high-level convenience wrapper   │
│   budget, approval,   │     around AgentRunner + LLM)       │
│   audit)              │                                      │
├──────────────────────┴───────────┬──────────────────────────┤
│           ToolRegistry            │      ApprovalPolicy       │
│    (register, dispatch, validate) │  (5 permission modes)     │
├──────────────────────────────────┴──────────────────────────┤
│                     Workspace Tools                          │
│  read_file · write_file · apply_patch · edit_at_hash         │
│  run_shell_inspect · run_shell_mutate · list_files           │
│  search_text · git_status                                    │
├─────────────────────────────────────────────────────────────┤
│                      State Layer                             │
│  AuditLogger · RunStore · MemoryCatalog · UltraworkStore     │
├─────────────────────────────────────────────────────────────┤
│                  Infrastructure                              │
│  OAuth 2.1/DPoP · MCP HTTP/stdio · OTel · Graph RAG         │
│  Code Mode · LLM Conformance · Provability                   │
└─────────────────────────────────────────────────────────────┘
```

## Component Layers

### 1. Decision Loop

`AgentRunner` is the core execution loop. It accepts a `DecisionFn` — any callable
that takes a context dict and returns either a `ToolRequest` or `FinalAnswer`:

- **ToolRequest**: name + arguments to dispatch through `ToolRegistry`.
- **FinalAnswer**: content + metadata to return to the caller.

The loop enforces iteration limits, tool-call limits, and cost budgets on every
iteration. Every decision and execution is recorded through `AuditLogger`.

`ModelDecisionEngine` implements the standard LLM path: it assembles a system
prompt, appends tool metadata and memory, calls the LLM adapter, and parses the
JSON response into `Decision` objects. `ChatAgentConfig` bundles all the
configuration needed for a complete model-driven agent run.

### 2. Tool Governance

All tools are registered through `ToolRegistry` with:

| Property       | Purpose                                     |
|----------------|---------------------------------------------|
| `name`         | Unique identifier (no spaces)               |
| `description`  | Human-readable purpose for prompt injection |
| `input_schema` | JSON Schema for argument validation         |
| `output_schema`| JSON Schema for result validation           |
| `annotations`  | `read_only`, `destructive`, `idempotent`    |

`ApprovalPolicy` sits between the decision loop and tool execution. It checks
annotations against the active `PermissionMode` before any destructive tool runs:

| Mode                 | Read | Write | Shell Mutate | Destructive Approval |
|----------------------|------|-------|-------------|-----------------------|
| `read-only`          | Yes  | No    | No          | Blocked               |
| `workspace-write`    | Yes  | Yes   | No          | Blocked               |
| `prompt`             | Yes  | Yes   | Conditional | Human-in-the-loop     |
| `allow`              | Yes  | Yes   | Yes         | Session-scoped        |
| `danger-full-access` | Yes  | Yes   | Yes         | None                  |

### 3. Audit and Observability

`AuditLogger` is the universal event sink. Every `AgentRunner` iteration,
tool call, approval decision, and final result produces an `AuditEvent`:

- Events are appended to a per-run JSONL file with `fcntl.LOCK_EX` and `fsync`.
- Sensitive keys (`api_key`, `token`, `secret`, …) and tool argument values
  (`content`, `command`, …) are redacted before persistence.
- String-level patterns (Bearer tokens, `sk-*` keys, query-param secrets) are
  also redacted.

Sinks plug into `AuditLogger.add_sink()`:
- `InMemoryMetricsSink` collects counters and histogram samples.
- `OTelAuditSink` converts events into OpenTelemetry spans.
- `OTelMetricsSink` converts events into OTel counters/histograms.

`RunStore` manages per-run audit files and provides listing, inspection, task
replay, and heartbeat tracking for resumable agent runs.

### 4. Workspace Isolation

Workspace tools operate within a configurable root directory. Every tool goes
through:

1. **Path resolution** — rejects `../`, absolute paths, and symlink escapes.
2. **Size enforcement** — `max_read_bytes`, `max_write_bytes`, `max_shell_output_bytes`.
3. **Shell classification** — quote-aware scanning splits commands into inspect
   (safe: `ls`, `cat`, `git status`) and mutate (everything else).
4. **Shell execution** — inspect commands run with `shell=False` after allowlist
   argv validation; `find -delete`/`-exec` and `git -c`/`--config` are blocked.
5. **Edit safety** — `apply_patch` requires unique match; `edit_at_hash` uses
   CRC32 line anchors.

### 5. Code Mode

Restricted Python execution with AST allow-list validation:

| Backend               | Isolation Level                                |
|-----------------------|------------------------------------------------|
| Child process (default)| `RLIMIT_CPU`, wall-clock timeout, advisory `RLIMIT_AS` |
| Container              | Docker/Podman: `--network none`, `--read-only`, `--cap-drop=ALL`, non-root, tmpfs, CPU/memory/PID limits, streaming output cap, image digest pinning, image allowlist |

Code Mode allows only a fixed set of AST nodes and builtin functions — no
imports, no attributes, no arbitrary calls.

### 6. OAuth 2.1 / DPoP

`OAuth21AuthorizationServer` and `OAuth21ResourceServer` implement the
authorization code grant with PKCE (S256) and optional DPoP proof-of-possession:

- Authorization codes are one-time (consume-and-delete semantics).
- Access tokens are HS256 JWTs with `kid` for key rotation.
- DPoP nonces are consumed on validation (no replay).
- DPoP proof `jti` values have short-lived replay caches.
- `SQLiteOAuthStore` provides durable client/authorization-code/nonce storage
  with PBKDF2-SHA256 client-secret hashing.

### 7. MCP Transport

Two transports share the same `handle_mcp_request()` dispatch:

- **stdio**: Standard JSON-RPC over stdin/stdout.
- **Streamable HTTP**: `POST /mcp` (JSON-RPC), `GET /mcp` (SSE keepalive),
  `DELETE /mcp` (session teardown), `OPTIONS /mcp` (CORS preflight).

The HTTP server enforces:
- Bearer token or OAuth 2.1 authentication for non-loopback binds.
- Origin allowlist for browser-initiated requests.
- `Mcp-Session-Id` session tracking.
- Body size limits with `413` for oversized payloads.

### 8. LLM Integration

`teaagent.llm` provides a unified adapter layer (`LLMAdapter`) across five
providers: OpenAI, Anthropic, Gemini, OpenRouter, and OpenCodeZen. Each adapter
implements `chat()` returning an `LLMResponse`. Features include:

- Configurable exponential-backoff retry (`LLMRetryConfig`).
- Cost budget pre-flight.
- Streaming via `stream=True` and `on_chunk` callbacks.

## Data Flow

```
User / CLI
  │
  ├─ task ───────────────────────────────────────► AgentRunner.run()
  │                                                  │
  │                                    ┌─────────────┴──────────────┐
  │                                    │  while iter < budget:       │
  │                                    │    decision = decide(ctx)   │
  │                                    │    if FinalAnswer → return  │
  │                                    │    if ToolRequest:          │
  │                                    │      policy.assert_allowed  │
  │                                    │      result = reg.execute   │
  │                                    │      ctx.observations.add   │
  │                                    │    audit.record(every step) │
  │                                    └────────────────────────────┘
  │
  └─ RunResult ◄──────────── final_answer, iterations, tool_calls, status
```

## State Boundaries

| Store            | Medium  | Locking                              | Purpose                      |
|------------------|---------|--------------------------------------|------------------------------|
| `AuditLogger`    | JSONL   | `fcntl.LOCK_EX` + `fsync`            | Per-run event log            |
| `MemoryCatalog`  | JSONL   | `fcntl.LOCK_EX` + `fsync`            | Workspace observations       |
| `RunStore`       | JSONL   | `atomic_write_text` (lock + replace) | Run history and replay       |
| `UltraworkStore` | JSONL   | `atomic_write_text`                  | Worker lifecycle records     |
| `SQLiteOAuthStore`| SQLite | WAL + `BEGIN IMMEDIATE`              | OAuth clients/codes/nonces   |

All state is externalized to the filesystem. In-memory runner state is
temporary only — every meaningful event persists to disk before the caller
sees the result.

## Extension Points

- **New tool**: register through `ToolRegistry` with schemas and annotations.
- **New LLM provider**: implement `LLMAdapter.chat()` returning `LLMResponse`.
- **New OAuth store**: implement `OAuthStore` protocol (SQL, Redis, …).
- **New Code Mode backend**: implement `CodeModeBackend` protocol.
- **New audit sink**: call `audit.add_sink(callback)` with any `AuditEvent → None`.
- **New MCP transport**: call `handle_mcp_request(registry, payload)`.
