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
  search_text · git_status                                    │
├─────────────────────────────────────────────────────────────┤
│              Multi-Agent Coordination Layer (Phase 4-5)       │
│  TaskCoordinator · AgentFactory · ToolPermissionManager       │
│  WorkflowEngine (polish mode, multi-step execution)          │
│  ContextBus (cross-sandbox Delta sharing)                     │
│  JITApprovalServer (remote SSE with timeout)                │
│  CentralizedApprovalQueue (aggregated subagent approvals)    │
├─────────────────────────────────────────────────────────────┤
│                      State Layer                             │
│  AuditLogger · RunStore · MemoryCatalog · UltraworkStore     │
├─────────────────────────────────────────────────────────────┤
│                  Infrastructure                              │
│  OAuth 2.1/DPoP · MCP HTTP/stdio · OTel · Graph RAG         │
│  Code Mode · LLM Conformance · Provability                   │
└─────────────────────────────────────────────────────────────┘
```

## 5-Loop Governance System (Completed Hardening)

The TeaAgent governance system has been hardened through a comprehensive 5-loop architecture that provides complete operational closure and security boundaries:

### Loop 1: Tool Governance (CI Gate & Manifests)
- **ToolRegistry with security tier mapping**: Tools now include `security_tier` annotations (Low, Medium, High, Critical) with automatic tier calculation based on annotations and capability manifests
- **Enhanced tool linting**: Static validation checks for write-like keywords in `read_only` tool descriptions, capability manifest validation with tier mismatch warnings
- **AST-based fuzz checking**: `selftest.py` includes static analysis to detect tools marked as `read_only=True` that contain write operations in their implementation
- **Capability manifest enforcement**: Tools must declare capabilities (filesystem_write, network) with preflight warnings for undeclared capabilities

### Loop 2: Coding Safety Loop (Plan Binding & Validation)
- **Strict plan-before-write enforcement**: `workspace-write` mode now requires plan binding by default (user-approved strict immediate block)
- **PlanContract file target validation**: Plans include approved file target lists with `allows_file_write()` method to prevent un-declared file modifications
- **Validation profile integration**: Fast, Standard, and Strict validation profiles wired to WorkflowEngine with automatic rollback on strict validation failure
- **JIT rollback integration**: Strict validation failures trigger automatic rollback via UndoJournal

### Loop 3: Audit / Replay Loop (Tiered Logging & Integrity)
- **Tiered audit levels**: L0 (Metrics-only), L1 (Metadata), L2 (Redacted Payload), L3 (Full Local Trace) with configurable filtering
- **Audit chain integrity verification**: SHA-256 hash chain validation for trace import to prevent tampering
- **Per-project encryption support**: L3 audits support per-project encryption keys for metadata leakage prevention
- **TUI run trace surface**: Interactive run store management for trace, export, and replay operations

### Loop 4: Memory / Failure Loop (Curation & Warning Injection)
- **Confidence-based blocking**: Low-confidence failure cards never block execution automatically (enforced warning thresholds)
- **Enhanced CLI curation suite**: `teaagent memory failures review/prune/invalidate` commands with confidence filtering
- **Custom invalidation rules**: Per-project automated invalidation rules (e.g., auto-pruning when target files change)
- **Memory hygiene enforcement**: TTL expiration rules and manual correction capabilities for memory poisoning

### Loop 5: Swarm & Tournament Sandbox Hardening
- **Approval lineage tracing**: Subagents carry parent-run IDs and inherit permission mode constraints with structured tracking
- **Fail-fast approval logic**: Tournament/parallel mode halts immediately if any subagent requires human permission (user-approved)
- **Git worktree sandbox enforcement**: Tournament runs require git worktree isolation as hard pre-condition for zero-contamination guarantees
- **Security-aware tournament scoring**: Weighted comparator schema (tests 40%, performance 15%, lint 10%, diff size 10%, architectural fit 15%, security 10%)

## Phase 4-5 Roadmap (Beta)

Core Phase 4 (consensus) and Phase 5 (sandbox routing/execution) modules are shipped
with CLI, unit tests, and E2E acceptance. Optional hardening (async vote polling,
WASM skill execution) is shipped; `docker-smoke` CI is advisory (see [CONTRIBUTING.md](../CONTRIBUTING.md#ci-jobs)).
Remaining Beta work is native WASM modules and deeper tournament benchmarks. See [backlog-priority.md](backlog-priority.md).

### Phase 4: Federated Swarm Consensus & Peer Attestations — **Beta**
- `ConsensusEngine`, peer registry, voting mechanisms, and attestation trail
- Swarm pre-approval gate when `ConsensusConfig.enable_pre_approval` matches task patterns
- Async vote collection via `ConsensusConfig.async_vote_collection` + `poll_until_resolved`
- CLI: `teaagent consensus` (`teaagent/cli/_handlers/_consensus.py`)
- E2E: `tests/acceptance/test_consensus_flow.py`

### Phase 5: Hardened Sandbox Virtualization — **Beta**
- Docker resource limits via `prepare_subagent_isolation` (`--cpus` / `--memory`)
- WASM runtime wrapper (`teaagent/wasm_runtime.py`) and skill routing (`teaagent/skill_router.py`)
- Skill execution: `teaagent/skill_executor.py`, `teaagent sandbox execute`
- `isolation=auto` on subagents with `skill_path` / `skill_risk_level`
- Resource monitoring CLI (`teaagent sandbox monitor`)
- E2E: `tests/acceptance/test_sandbox_enhancement_flow.py`

### Phase 6: Skill writer, docker monitor, control plane — **Beta**
- `SkillWriter` publish/review pipeline (`teaagent/skill_writer.py`)
- Docker sandbox resource monitor + abort (`teaagent/docker_sandbox.py`)
- Prompt tournament fitness scoring in `SwarmManager` (`.teaagent/prompt_gene_pool.jsonl`)
- Control plane HTTP + dashboard (`teaagent/control_plane_api.py`, `teaagent/html_dashboard/`)
- CLI: `teaagent control-plane serve` (workflow/focus/JIT SSE dashboard)

See [backlog-priority.md](backlog-priority.md) for detailed task breakdowns and implementation status.

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

### 6. Governance Hardening (Tranche B)

**Plan-before-Write Enforcement:**
- `workspace-write` mode now enforces plan-by-default for safety
- `--require-plan` flag blocks destructive tools without a bound plan artifact
- `--skip-plan-check` provides explicit override for power users
- Implemented in `teaagent/governance/plan_gate.py` with strict defaults

**Automated Memory Invalidation:**
- Conservative default rules prevent memory corruption:
  - `file_signature_change`: invalidate when files change
  - `test_refactor`: warn when test files are modified
  - `dependency_version_change`: warn on dependency updates
- Per-project customization via `.teaagent/config.json`
- CLI command: `teaagent memory failures auto-invalidate`
- Implemented in `teaagent/memory/failure_card.py` with signature tracking

**Centralized Approval Queue:**
- Aggregates destructive tool requests from multiple subagents
- Supports batch approval/deny with full lineage tracking
- Prevents approval fatigue in tournament/swarm modes
- Timeout handling and request lifecycle management
- Implemented in `teaagent/subagents/_approval_queue.py`

**Governance Fuzz Tests:**
- Comprehensive adversarial test suite in `tests/test_governance_fuzz.py`
- Validates plan-before-write enforcement, memory invalidation, and approval queue security
- Tests conservative defaults and path filtering
- Integrated into CI governance gate

### 7. OAuth 2.1 / DPoP

`OAuth21AuthorizationServer` and `OAuth21ResourceServer` implement the
authorization code grant with PKCE (S256) and optional DPoP proof-of-possession:

- Authorization codes are one-time (consume-and-delete semantics).
- Access tokens are HS256 JWTs with `kid` for key rotation.
- DPoP nonces are consumed on validation (no replay).
- DPoP proof `jti` values have short-lived replay caches.
- `SQLiteOAuthStore` provides durable client/authorization-code/nonce storage
  with PBKDF2-SHA256 client-secret hashing.

### 8. MCP Transport

Two transports share the same `handle_mcp_request()` dispatch:

- **stdio**: Standard JSON-RPC over stdin/stdout.
- **Streamable HTTP**: `POST /mcp` (JSON-RPC), `GET /mcp` (SSE keepalive),
  `DELETE /mcp` (session teardown), `OPTIONS /mcp` (CORS preflight).

The HTTP server enforces:
- Bearer token or OAuth 2.1 authentication for non-loopback binds.
- Origin allowlist for browser-initiated requests.
- `Mcp-Session-Id` session tracking.
- Body size limits with `413` for oversized payloads.

### 9. LLM Integration

`teaagent.llm` provides a unified adapter layer (`LLMAdapter`) across 13
registered providers in `PROVIDER_CONFIGS`: `claude`, `gpt`, `gemini`,
`openrouter`, `ollama`, `vllm`, `opencodezen`, `opencodezen-go`, `mistral`,
`deepseek`, `grok`, `workers-ai`, and `aigateway`. Credential env vars are
unique per provider key except shared `CLOUDFLARE_API_TOKEN` (workers-ai and
aigateway) and shared `OPENCODEZEN_API_KEY` (both OpenCodeZen adapters). Each
adapter implements `chat()` returning an `LLMResponse`. Features include:

- Configurable exponential-backoff retry (`LLMRetryConfig`).
- Cost budget pre-flight.
- Streaming via `stream=True` and `on_chunk` callbacks.

### 10. External Federation Boundary (ANP Adapter)

TeaAgent treats ANP as an optional external federation surface through a
bidirectional adapter boundary:

- **Inbound** (`ANP -> TeaAgent`): `ANPGovernedService` normalizes network
  requests into `AgentRunner` tool execution and must still pass `ToolRegistry`,
  `ApprovalPolicy`, budget enforcement, and `AuditLogger`.
- **Outbound** (`TeaAgent -> ANP`): selected tasks can be delegated to ANP
  peers through a typed client, then mapped back into internal result/audit
  models.

This keeps core runtime governance stable while enabling cross-organization
agent interoperability. See ADR 0007 for scope and invariants.

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
| `UltraworkStore`  | JSONL   | `atomic_write_text`                  | Worker lifecycle records     |
| `SQLiteOAuthStore`| SQLite | WAL + `BEGIN IMMEDIATE`              | OAuth clients/codes/nonces   |
| `ContextBus`      | SQLite | WAL; per-thread connections        | Cross-agent Delta cards      |
| `FederatedGraphSync` | JSON | none (single-writer file)         | Graph sync state + exports   |

JSONL rows assume a **single writer per workspace** on a local or advisory-lock-safe
filesystem. NFS multi-writer shared roots are unsupported — see [ADR 0008](adr/0008-p4-strategic-posture.md).

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
- **New hook**: register through `HookRegistry` with 8-event lifecycle.
- **New plugin**: add to `.teaagent/plugins/` with `plugin.json`.

## Hook System (8-Event Lifecycle)

TeaAgent implements Claude Code compatible 8-event hook system:

| Event | Trigger | Use Case |
|-------|---------|----------|
| `SessionStart` | Before session begins | Initialize context, load configs |
| `UserPromptSubmit` | After user message | Log prompts, analyze intent |
| `PreToolUse` | Before tool execution | Permission checks, input validation |
| `PostToolUse` | After tool execution | Lint checks, test runs |
| `PreCompact` | Before context compression | Prepare for compaction |
| `Stop` | Before session stops | Save state, cleanup |
| `SubagentStop` | After subagent completes | Aggregate results |
| `SessionEnd` | After session ends | Finalize audit, memory flush |

Built-in hooks:
- `permission_check_hook` - Enforce Allow/Ask/Deny patterns
- `lint_check_hook` - Run linter after file modifications
- `run_tests_hook` - Run tests after code changes
- `mcp_tool_filter_hook` - Filter MCP tools by allow/block lists

## Three-Tier Memory System

Claude Code compatible memory hierarchy:

| Tier | Location | Git-tracked | Use Case |
|------|----------|-------------|----------|
| Project | `.teaagent/memory.jsonl` | Yes | Team-shared context |
| Personal | `~/.config/teaagent/memory.jsonl` | No | User-specific notes |
| Auto-Memory | `.claude/MEMORY.md` | No | Persistent learnings

```python
from teaagent.memory import MemoryHierarchy

mem = MemoryHierarchy(root="/path/to/project")
mem.project.add("Found a bug in auth module", tags=("bug", "auth"))
mem.personal.add("User prefers dark mode", tags=("preference",))

# Search across all tiers
results = mem.search_all("bug", limit=10)
```

## Plugin System

Four extension points (Claude Code compatible):

### 1. Commands
Slash commands that add CLI functionality.

### 2. Agents
Custom subagents with specialized prompts and tool subsets.

### 3. Hooks
Lifecycle event handlers (see Hook System above).

### 4. MCP Servers
External tool integrations.

Discovery order (first match wins):
1. Project: `<workspace>/.teaagent/plugins/`
2. User: `~/.config/teaagent/plugins/`
3. Built-in: `teaagent/plugins/builtin/`

## Context Compaction

Automatic context compression at threshold levels (Claude Code traffic light):

| Level | Token Usage | Behavior |
|-------|-------------|----------|
| Green | 0-75% | Normal operation |
| Yellow | 75-92% | User hints for session save |
| Red | 92%+ | Auto-triggered compaction |

```python
from teaagent.context import CompactionManager

manager = CompactionManager()
if manager.should_compact(token_count=180000):
    result = manager.check_and_compact(context, 180000)
    # Tokens saved: result.tokens_saved
```

## Plan Mode

Read-only exploration mode for safe codebase analysis:

```python
from teaagent.plan_mode import PlanMode, PlanModeState

plan = PlanMode()
plan.enable("Analyzing unfamiliar codebase")

# Tools blocked in plan mode:
# - workspace_write_file
# - workspace_apply_patch
# - shell

plan.add_note("Found authentication module at line 42")
plan.disable()
```

## ACP (Agent Client Protocol)

IDE integration for VS Code, Zed, and JetBrains:

```
CLI/TUI → ACPServer → JSON-RPC over stdio → IDE
```

Methods:
- `initialize` - Handshake and capability negotiation
- `tools/list` - List available tools
- `tools/call` - Execute a tool
- `completion` - Request agent completion
- `tools/cancel` - Cancel running tool

## Mainstream Framework Comparison

TeaAgent is a governance-first agent harness. This section documents how it
compares to the four mainstream coding-agent frameworks surveyed in
[scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md),
last refreshed 2026-05-24.

### Feature Coverage Matrix

| Capability | TeaAgent | Claude Code | Codex | OpenCode |
|---|---|---|---|---|
| Terminal-first CLI/TUI | ✅ | ✅ `claude` CLI | ✅ `codex` TUI | ✅ `opencode` TUI |
| Multi-provider LLM | ✅ 13 providers | ❌ Anthropic only | ❌ OpenAI only | ✅ 11+ providers |
| Permission modes | ✅ 5 modes | ✅ deny/ask/allow | ✅ 4 sandbox policies | ✅ 3 approval modes |
| Hook system (8 events) | ✅ Claude Code compatible | ✅ 8+ events | ✅ 7+ events | — |
| MCP server / client | ✅ stdio + HTTP | ✅ | ✅ codex-mcp-server | ✅ stdio + SSE |
| Skills / plugins | ✅ 4 extension points | ✅ Plugin marketplace | ✅ Skills + Plugins | — |
| Sub-agent isolation | ✅ 3 modes (shared/worktree/container) | ✅ 2 modes (shared/worktree) | ✅ Thread manager | — |
| Context compaction | ✅ 75-92% traffic light | ✅ 98% auto | ✅ History compaction | ✅ Auto-compact |
| Three-tier memory | ✅ Project/Personal/Auto | ✅ CLAUDE.md files | ✅ 2-phase extraction | — |
| Audit / governance | ✅ JSONL hash chain | — | — | — |
| Undo / rollback | ✅ Undo journal | — | — | ✅ File history |
| Read-before-write mtime guard | ✅ since v0.1.0 | — | ✅ (via Edit tool) | ✅ mtime check |
| Protected paths (.git/.teaagent) | ✅ default deny rules | — | ✅ .git/.codex/.agents | — |
| IDE integration | ✅ ACP + VS Code ext | ✅ VS Code ext | ✅ App Server (Zed/VS Code) | — |
| Session resume | ✅ RunStore JSONL | ✅ rollout files | ✅ rollout + fork | ✅ SQLite |
| OAuth / security | ✅ OAuth 2.1 + DPoP | — | ✅ OAuth for MCP | — |
| Telemetry | ✅ OTEL spans + metrics | ✅ OTEL spans | ✅ OTEL | — |
| Cloud / background tasks | ✅ Ultrawork + BackgroundRun | ✅ background sessions | ✅ Cloud Tasks | — |
| Acceptance test coverage | ✅ See [acceptance.md](acceptance.md) (pytest-collected AT, P0/P1/P2 tiers) | — | ✅ test suite | — |
| Declarative agent definitions | ✅ YAML/JSON/Markdown | ✅ .claude/agents/*.md | ✅ config.toml | — |

### TeaAgent Differentiators

- **Governance-first**: Every tool call, decision, and error is recorded in an
  immutable JSONL audit log with hash-chain integrity. No other framework
  provides this level of auditability.
- **Multi-protocol surface**: MCP + ACP + A2A + ANP — more integration
  protocols than any single mainstream framework.
- **Cross-provider**: 13 LLM providers vs. 1 per vendor framework.
- **Policy-as-code**: Declarative deny rules in `policy.yaml` that cannot be
  bypassed, even in `danger-full-access` mode.
- **Built-in undo**: Automatic pre-write snapshots with user-facing
  `teaagent agent undo` command.

### Alignment Gaps (Addressed)

These gaps identified in the 2026-05-24 competitive analysis have been closed:

- **LSP integration** → Code analysis tools (`code_definition`, `code_references`,
  `code_diagnostics`, `code_symbols`, `code_tree_sitter_relations`) registered
  when `code_analysis_enabled: true`.
- **Read-before-write mtime guard** → `workspace_write_file` accepts
  `expected_mtime` and rejects overwrites on concurrent modification.
- **Protected paths** → `.git/*` and `.teaagent/*` are blocked by default
  through built-in `FilePolicy` deny rules.
- **Declarative sub-agent definitions** → YAML/JSON/Markdown frontmatter files
  in `.teaagent/subagents/` with `isolation`, `background`, `disallowed_tools`,
  and `effort` fields.
