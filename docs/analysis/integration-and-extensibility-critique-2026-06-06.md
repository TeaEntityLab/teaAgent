# teaAgent: Integration & Extensibility Critique

**Date:** 2026-06-06  
**Status:** Point-in-time analysis of HEAD (`main` branch)  
**Scope:** Integration landscape, MCP, tool ecosystem, approval policy, LLM providers, storage backends, UI surfaces, abstraction quality, user pain points

---

## 1. Integration Inventory

teaAgent integrates with external systems across six layers. The table below distinguishes what is built-in (hard-wired) from what is pluggable (swappable without forking core code).

| Layer | What exists | Built-in or pluggable? |
|---|---|---|
| LLM providers | 14 providers (claude, gpt, gemini, ollama, vllm, openrouter, mistral, deepseek, grok, workers-ai, aigateway, opencodezen, opencodezen-go, fake) | Partially pluggable: OpenAI-compatible via config dict; custom response formats require core edits |
| MCP (inbound) | HTTP + stdio server exposing registered tools as JSON-RPC | Built-in; tool set reflects `ToolRegistry` at runtime |
| MCP (outbound) | HTTP client + trust policy + tool adapter | Built-in client; remote servers pluggable via config |
| Built-in tools | 24+ tools: file I/O, git, shell, search, code-parse | Pluggable via `importlib.metadata` entry-points |
| Approval/policy | 5 permission modes (READ\_ONLY, WORKSPACE\_WRITE, PROMPT, ALLOW, DANGER\_FULL\_ACCESS) | Not pluggable; modes are an enum, no custom logic path |
| Audit logging | JSONL file + hash-chain + opt. encryption; webhook sink; OpenTelemetry sink | Pluggable via `AuditLogger.add_sink()` |
| Run storage | JSONL file per run; index file | Not pluggable; no interface to swap |
| Memory/catalog | JSONL file per session | Not pluggable; no interface to swap |
| Approval grants | JSON file at `.teaagent/approval-grants.json` | Not pluggable; no interface to swap |
| Knowledge/code backends | `BackendRegistry`; adapters for search + AST parse | Pluggable via `BackendRegistry.register_*_backend()` |
| Hook lifecycle | 8 events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, SubagentStop, SessionEnd) | Pluggable via `HookRegistry.register_*()` in code; no config-based hook entry-points |
| UI surfaces | CLI + TUI (prompt-toolkit) | Not pluggable; no surface contract |

---

## 2. MCP Server Capability

### What the MCP interface exposes

teaAgent operates in both MCP server and MCP client roles. As a server (`teaagent/mcp_server.py`, `teaagent/mcp_http/`), it exposes whatever tools are registered in the active `ToolRegistry` over JSON-RPC 2.0 via the MCP spec revision `2024-11-05`. Remote clients can:

- **Discover tools**: `tools/list` — returns name, description, `input_schema`, `output_schema`, and MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `statefulHint`) for every registered tool (`tools.py:271–286`)
- **Execute tools**: `tools/call` — full argument passing; result returned as MCP content envelope
- **Establish sessions**: `initialize` + session IDs via `Mcp-Session-Id` header; SSE stream for async results

Two transports are supported: HTTP (ThreadingHTTPServer at `mcp_http/__init__.py`) and stdio (`mcp_server.py`). A stateless variant exists at `stateless_mcp.py` for single-request deployments.

### Trust model

`mcp_trust.py` implements per-server TTL-based trust: `MCPServerTrust` carries `trusted: bool`, `allowed_tools`, `denied_tools`, and `expires_at` (Unix timestamp, default TTL 86400s). Trust is checked at every tool call (`mcp_trust.py:177–203`); expired entries are rejected. Trust data is Fernet-encrypted at `~/.teaagent/mcp-trust.json`.

### Gaps

1. **No nested MCP composition.** teaAgent cannot be simultaneously a server and a client in the same request path. Chaining remote MCP tools through teaAgent to another MCP server requires a wrapper process.
2. **DPoP OAuth refresh is wired but nonfunctional.** `FilteredMCPClient.refresh_oauth_token()` exists in the interface but does nothing with the returned token. OAuth refresh is effectively a no-op.
3. **No manifest integrity verification.** A remote MCP server can advertise any tool names/schemas. There is no signature on the manifest; trust is per-server identity only.
4. **Session state is in-memory only.** `MCPSessionStore` uses a `threading.Lock`-guarded set. Server restart orphans all active sessions. No TTL on sessions (distinct from trust TTL).
5. **No auto-discovery.** Remote MCP endpoints require manual `endpoint` + `auth_token` configuration. There is no DNS-SD, `.well-known/mcp`, or registry lookup.

---

## 3. Tool Ecosystem Extensibility

### Pattern and registration

A tool is a `ToolDefinition` dataclass (`tools.py:50`) containing:

```
name: str
description: str
input_schema: dict           # JSON Schema
output_schema: dict          # JSON Schema
annotations: ToolAnnotations # read_only, destructive, idempotent, stateful, security_tier
handler: Callable[[dict], dict]
```

Registration: `registry.register(name, description, input_schema, output_schema, annotations, handler)`. Duplicate names are rejected unless `allow_override=True`. The `ToolRegistryBuilder` in `workspace_tools/builder.py` provides fluent chaining (`.with_workspace_tools().with_git_tools().build()`).

### Existing tools (24+)

- **File tools** (6): `workspace_read_file`, `workspace_write_file`, `workspace_read_file_hashed`, `workspace_edit_at_hash`, `workspace_apply_patch`, `workspace_list_files` — `workspace_tools/_files.py`
- **Git tools** (8): `git_add`, `git_commit`, `git_lore_commit`, `git_branch`, `git_checkout`, `git_push`, `git_pull`, `git_status` — `workspace_tools/_git.py`
- **Shell tools** (2): `run_shell`, `run_shell_argv` — `workspace_tools/_shell.py`
- **Knowledge/search** (3+): `knowledge_search`, `code_parse_overview`, `code_parse_symbols`
- **Browser tools**: `browser_tools.py`

### How to add a new tool

Adding a tool that stays outside core code works well:

1. Implement `handler(args: dict) -> dict`.
2. Create a Python package exposing `register(registry: ToolRegistry) -> None` that calls `registry.register(...)`.
3. Declare `[project.entry-points."teaagent.tools"] my-tool = "mypackage.tool:register"` in `pyproject.toml`.
4. `load_plugins()` in `teaagent/plugins.py:111` discovers and calls all registered entry-points.

The plugin path is the right path for external tools. No core edits required. Security audit of third-party plugin sources runs at load time (`plugins.py:67–108`).

### Pitfalls

- **Tools are functions, not objects.** There is no class hierarchy, so tool-level composition (pre/post middleware on a specific tool, tool versioning, tool-level retry config) requires wrapping the handler callable manually.
- **Two parallel plugin systems.** `teaagent/plugins.py` handles `importlib.metadata` entry-points (tools only). `teaagent/plugin_system.py` handles manifest-based plugins (commands, agents, hooks, MCP servers) discovered from filesystem directories. Neither is aware of the other. A developer authoring a plugin has to choose which system to target — and the docs don't explain the difference.
- **`plugin_system.py` discovers but doesn't load.** `discover_plugins()` returns `Plugin` objects with `module=None`. There is no `load_plugins()` equivalent that actually imports the modules and registers commands/agents into the runtime. The `PluginRegistry` is populated with built-in agents only (`register_builtin_plugins()`) and there is no evidence it is wired to the CLI or TUI at runtime.
- **Rate limiting is an afterthought.** `ToolRateLimit` exists as a dataclass but is not enforced by `ToolRegistry.execute()` — enforcement is caller responsibility.

---

## 4. Approval Policy Extensibility

### Architecture

`ApprovalPolicy` (`policy.py:37`) is a frozen dataclass, not an abstract base class. It delegates to a concrete `ApprovalManager` that is constructed inside `__post_init__`. The five permission modes are an enum:

```
PermissionMode.READ_ONLY
PermissionMode.WORKSPACE_WRITE
PermissionMode.PROMPT          # default — JIT TTY prompt
PermissionMode.ALLOW
PermissionMode.DANGER_FULL_ACCESS
```

Approval decisions flow through:
1. `PermissionModeEnforcer.check()` — mode-based block/allow
2. `JITApprovalManager.prompt_and_resolve()` — interactive TTY prompt + per-session memory
3. `_check_multi_sig_quorum()` — multi-party signature collection for high-risk operations
4. `ApprovalStoreManager` — validates against persistent grant database

### Can a user supply custom approval logic?

**No.** The `ApprovalManager` is constructed internally. `ApprovalPolicy.__post_init__` wires all components; there is no injection point for a custom approval strategy. An integrator who wants to route approvals through a CI/CD pipeline, Slack bot, or organizational policy engine must either monkey-patch `PermissionModeEnforcer.check()` or fork the class.

### What context does the approver receive?

The approval context is rich: `tool_name`, `call_id`, `destructive: bool`, `arguments: dict` (full payload), `plan_contract` (allows file-write scope check), `read_only`, `description`. This is sufficient for informed policy decisions — the problem is not context poverty, it is that the decision function itself is not injectable.

### The quorum mechanism is a hidden gem

`_check_multi_sig_quorum()` implements genuine multi-party approval with peer signature collection (`_collect_peer_signatures()`, `_run_async_signature_collection()`) and HMAC-anchored approval hashes. This capability is entirely opaque to external integrators since there is no documented configuration path.

### Critical finding

Approval is one of the highest-value extension points for enterprise integrators (audit compliance, org policy engines, automated LGTM pipelines). The current design makes it the most closed part of the system.

---

## 5. LLM Provider Pluggability

### Abstraction quality

The `LLMAdapter` Protocol (`llm/_types.py:177–180`) is cleanly minimal:

```python
class LLMAdapter(Protocol):
    provider: str
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

`LLMRequest` and `LLMResponse` are frozen dataclasses covering messages, tools, streaming preferences, and safety blocks. The type contract is strong and implementable without importing any teaagent internals.

### Factory design

`create_llm_adapter()` (`llm/_config.py:140–171`) uses a hard-coded if-chain:

```python
if normalized == 'claude':   return ClaudeAdapter(config, ...)
if normalized == 'gemini':   return GeminiAdapter(config, ...)
if normalized == 'workers-ai': return WorkersAIAdapter(config, ...)
return OpenAICompatibleAdapter(config, ...)
```

For OpenAI-compatible providers, the factory is data-driven: adding a provider requires only a new entry in `PROVIDER_CONFIGS` dict and two cost-rate lists. For providers with custom response formats (à la Claude or Gemini), a code edit is unavoidable.

There is no registration mechanism. An external adapter class cannot self-register. The factory must be modified.

### Duplication across adapters

The `llm/` package shows good module extraction for shared concerns:

- `_sse.py` (36 LOC): SSE line parsing
- `_extract.py` (119 LOC): tool call extraction across provider formats
- `_transport.py` (63 LOC): HTTP transport abstraction
- `_retry.py` (50 LOC): retry loop

The main `_adapters.py` is 680 LOC covering `OpenAICompatibleAdapter`, `WorkersAIAdapter`, `ClaudeAdapter`, and `GeminiAdapter`. Payload building (`_prepare_payload()`) is still duplicated: each adapter implements its own version rather than sharing a base. Header assembly, streaming entry points, and error wrapping follow the same pattern in each class.

### Adding provider #14

- OpenAI-compatible: ~5 LOC (config dict entry + cost entries). Zero adapter code.
- Custom protocol: ~80–100 LOC for the adapter class + one `if` branch in the factory. Requires editing `llm/_config.py`.
- **Missing**: provider feature flags (e.g., "this provider doesn't support streaming" or "this provider has a 512-token tool description limit"). Currently per-adapter logic embeds these as hard-coded values.

---

## 6. Storage Backend Options

### Audit logging — done right

`AuditLogger.add_sink(sink: Callable[[AuditEvent], None])` (`audit.py:308`) is a clean push-based sink interface. Two non-trivial sinks ship:

- **Webhook sink** (`webhook_sink.py`, 140 LOC): POST with GitHub-style `X-TeaAgent-Signature-256` HMAC header, event filtering, configurable timeout.
- **OpenTelemetry sink** (`audit.py:337–344`): wraps `configure_telemetry()` with an adapter.

The underlying audit log is hash-chained (`audit_chain.py`, 255 LOC) with optional HMAC per-run secret, giving tamper evidence for the file-based log. This is the most mature extensibility story in the whole codebase.

### Everything else — not done right

`RunStore` (`run_store.py`, 464 LOC), `MemoryCatalog/MemoryHierarchy` (in `memory/`), and `ApprovalPresetStore` (`ergonomics/_approval_state.py`) share no common abstract interface. Each is a concrete class backed by JSONL or JSON files in `.teaagent/`. Swapping any of these (e.g., to Postgres, Redis, or S3) requires forking the class or monkey-patching at the import site.

`storage.py` (47 LOC) is not an abstraction layer — it is a pair of utility helpers (`file_lock`, `append_jsonl_line`). The function name suggests an abstraction that does not exist.

### The `BackendRegistry` exception

`BackendRegistry` in `backend_registry.py` accepts any object for knowledge search and code parse backends, using duck typing (`initialize()`, `shutdown()`, `check_health()` if present). This is the only general-purpose storage extensibility in the codebase outside of audit sinks.

### What would a cloud deployment need to add?

A team deploying teaAgent in a shared environment (multiple users, centralized audit, remote run history) would need to either:
- Accept JSONL files per instance and aggregate externally (works if they only need audit — webhook sink handles that), or
- Rewrite `RunStore` and `MemoryHierarchy` without a stable interface to satisfy.

---

## 7. UI Extensibility

### Existing surfaces

- **CLI** (`cli/__init__.py`): monolithic argparse dispatcher, 738 lines of imports/registration, 150+ handler functions in `cli/_handlers/`. Directly instantiates `ChatAgentConfig`, `RunStore`, `AuditLogger`.
- **TUI** (`tui/`): prompt-toolkit-based, 3,017+ LOC. Manages 20+ instance attributes. Directly calls `run_chat_agent()`. Contains its own cockpit state refresh, file watcher, git checkpoint logic.

### Is there a surface contract?

No. Neither CLI nor TUI exposes or adheres to a defined interface between the UI layer and the agent core. `CommandExecutor` (`cli/execution.py`) is an ABC with a single abstract method `execute(context: ExecutionContext) -> RunResult`, but CLI handlers call `run_chat_agent()` directly, bypassing it entirely.

### What would building a web UI require?

A developer building a web UI (FastAPI, Django, etc.) would need to:

1. **Re-implement config assembly.** `ChatAgentConfig` takes 8+ parameters including deeply nested `ApprovalPolicy`, `ToolRegistry`, `RunStore`, `AuditLogger`. No factory that produces a sensible default from a flat config dict.
2. **Duplicate approval/permission wiring.** Approximately 400 LOC of CLI handler code (`cli/_handlers/_approval*.py`) handles the interactive approval flow. A web UI needs a different delivery mechanism (WebSocket, polling) with no hook into the existing `JITApprovalManager`.
3. **Implement its own streaming event loop.** The TUI drives output via prompt-toolkit; the CLI via stdout. Neither exposes a generic event/callback stream that a web layer could consume.
4. **Replicate cockpit state logic.** TUI-specific state (run tree, active tool, cost meter) has no canonical data model; it is entangled with prompt-toolkit widgets.

Estimated duplication: approximately 40% of CLI/TUI LOC would need to be independently reimplemented, with no shared interface guarantees.

### The plugin system's promise

`plugin_system.py` defines `PluginType.COMMAND` and `PluginType.AGENT` as extension types with a manifest-based discovery system. This is the right direction for slash-command extension. However, as noted in §3, `discover_plugins()` returns unloaded modules and the `PluginRegistry` of commands is never wired into the CLI dispatcher at runtime. The promise is not yet delivered.

---

## 8. Abstraction Quality Audit

| Component | Pattern | Grade | Key failure |
|---|---|---|---|
| `LLMAdapter` Protocol | Structural Protocol | A | Factory hard-codes adapter selection; no external registration |
| Audit sink | Push-based `Callable` list | A | None — this is the model to copy |
| `ToolRegistry` + builder | Registry + plugin entry-points | B+ | Two parallel plugin systems with no composition |
| `BackendRegistry` | Duck-typed registry | B | Only covers knowledge/code backends; not generalized |
| `HookRegistry` | Typed Protocols, 8 events | B | Hook registration is code-only; no plugin-authored hooks wired |
| `PermissionMode` / approval | Enum + concrete class | D | No abstract base, no injection point, quorum logic opaque |
| Storage (run, memory, grants) | Concrete JSONL classes | D | No interface; three classes that should share an `AbstractStore` |
| UI surface contract | None | F | `CommandExecutor` ABC exists but is never called |
| Plugin system | Two parallel systems | D | `plugin_system.py` loads manifests but never activates them |

### The audit sink / `LLMAdapter` Protocol contrast

The audit sink system shows what good looks like: a minimal `Callable[[AuditEvent], None]` interface backed by two working implementations (webhook, OTel), with documentation and test coverage. The `LLMAdapter` Protocol is similarly clean at the type level. The problem is that every other layer in the codebase chose a different pattern — or no pattern at all.

---

## 9. User Integration Pain Points

These are the friction points a developer would hit trying to embed teaAgent in their system:

**1. "I want to plug teaAgent into our approval workflow (Slack bot, GitHub Actions)."**  
There is no approval hook. You must fork `ApprovalManager` or monkey-patch `PermissionModeEnforcer.check()`. The multi-sig quorum feature, which is exactly what enterprise approval workflows need, is internal and undocumented as an extension point.

**2. "I want to build a web UI."**  
No surface contract. Start by reading 3,000+ LOC of TUI and CLI code to understand config assembly. The `CommandExecutor` ABC looks promising but is unused — calling it directly will not produce a working session.

**3. "I want to store run history in our database."**  
`RunStore` has no interface. You can receive audit events via webhook sink (that works), but run history requires a fork. Searching or querying past runs via SQL is impossible without exporting JSONL and importing it yourself.

**4. "I want to write a tool plugin."**  
This actually works, via `importlib.metadata` entry-points. The friction is documentation: the `plugin_system.py` manifest-based system exists and looks authoritative, but it doesn't activate plugins at runtime. A developer following the manifest path will produce dead code.

**5. "I want to add a new LLM provider."**  
If it's OpenAI-compatible, edit `PROVIDER_CONFIGS` dict and cost lists — 5 lines, no class needed. If it needs custom parsing (e.g., a provider that uses a non-standard streaming format), write a class and edit the factory if-chain. Not documented; must read `_config.py` to discover the pattern.

**6. "I want to connect teaAgent to our observability stack."**  
The audit logger has OpenTelemetry support and a webhook sink. Both work. This is the best-supported integration story in the codebase. Tracing individual tool calls through a distributed system still requires custom `PostToolUse` hooks.

**7. "I want to chain teaAgent as an MCP tool server inside a larger orchestration."**  
The MCP server works. The gap is that the same teaAgent process cannot simultaneously be an MCP client calling a remote server inside the same session. Chaining requires a second process.

---

## 10. Critical Assessment

**The honest answer to "are we actually extensible?":** Partially. The tool registry and audit sink are genuinely extensible. The rest is either closed (approval, storage, UI contract) or architecturally present but operationally dead (manifest-based plugins, `CommandExecutor` ABC).

**What's working well:**

- `LLMAdapter` Protocol is a clean seam; adding an OpenAI-compatible provider is trivial.
- Audit extensibility (sink API, webhook sink, OTel) is the strongest integration story. This is the pattern the rest of the codebase should emulate.
- MCP trust model (per-server TTL, deny lists, encryption) is thoughtful.
- `ToolRegistry` with `importlib.metadata` entry-points works correctly for external tools.
- 8-event hook lifecycle covers the right points; the Protocol types are correct.

**What needs the most work:**

- **Approval policy**: needs an `ApprovalBackend` abstract base class with a single `approve(request: ApprovalRequest) -> ApprovalDecision` method. The current 5 modes become built-in implementations. Enterprise integrators can provide their own.
- **Storage layer**: needs an `AbstractStore[T]` generic interface, then `RunStore`, `MemoryStore`, and `ApprovalGrantStore` become concrete implementations. Separating the interface from the JSONL implementation unblocks database-backed deployments.
- **Plugin system unification**: merge `plugins.py` (entry-points) and `plugin_system.py` (manifests) into one system. Fix `discover_plugins()` to actually load and activate command/agent plugins.
- **UI surface contract**: `CommandExecutor` is the right idea. Make CLI and TUI implement it, then document it as the stable API surface for third-party UIs.
- **LLM factory**: add an external adapter registry (e.g., `register_adapter_factory(prefix, factory_fn)`) so third-party adapters don't require editing `_config.py`.

---

## 11. Extensibility Roadmap

Items are ordered by user impact vs. implementation effort.

| Priority | Item | File(s) to change | Effort | Impact |
|---|---|---|---|---|
| P0 | Approval policy injection point | `policy.py`, `approval_manager.py` | Medium | Enables enterprise approval routing |
| P0 | Unify plugin systems | `plugins.py`, `plugin_system.py`, `cli/__init__.py` | Medium | Fixes dead plugin_system.py path |
| P1 | Abstract store interface + JSONL implementations | `run_store.py`, `memory/catalog.py`, `ergonomics/_approval_state.py` + new `abstract_store.py` | Medium | Enables DB-backed deployments |
| P1 | `CommandExecutor` ABC enforcement | `cli/execution.py`, `cli/_handlers/*.py` | Medium | Creates stable UI surface contract |
| P2 | LLM adapter external registration | `llm/_config.py` | Small | Third-party provider packages |
| P2 | Hook plugin entry-points | `hooks.py`, `plugins.py` | Small | Config-driven hooks (no code) |
| P3 | MCP nested composition | `mcp_client.py`, `mcp_server.py` | Large | Orchestration pipelines |
| P3 | DPoP OAuth completion | `mcp_client.py` | Small | Remote secured MCP servers |
| P3 | Session state persistence | `mcp_http/__init__.py` | Small | MCP server survivability |

---

*Sources: live code at HEAD (`main`), all claims traceable to file paths and line ranges cited above. Security posture and performance characteristics are out of scope; see `docs/analysis/dependency-audit-and-security-2026-06-02.md` and `docs/analysis/performance-profiling-and-optimization-roadmap-2026-06-02.md`.*
