# Design Patterns Catalog

Patterns used in the TeaAgent codebase, with examples and the rationale for their use.

---

## 1. Adapter Pattern

**Where:** `teaagent/llm/_adapters.py`, `teaagent/acp_adapter.py`, `teaagent/anp_adapter.py`  
**What:** A provider-specific adapter translates between an external protocol's data shape and TeaAgent's internal types (`LLMRequest` → provider-specific HTTP body; external ANP task → internal `DelegatedTask`).  
**Why:** LLM providers have incompatible API contracts. The adapter pattern isolates all provider-specific logic in one place, so the rest of the codebase works against a single `LLMAdapter` interface. Adding a new provider is adding one adapter, not changing call sites.  
**Example:**
```python
# llm/_adapters.py
class ClaudeAdapter:
    def complete(self, req: LLMRequest) -> LLMResponse:
        body = {"model": req.model, "messages": req.messages, ...}
        raw = self._transport.post("/v1/messages", body)
        return _extract_claude_content(raw)
```

---

## 2. Registry Pattern

**Where:** `teaagent/backend_registry.py`, `teaagent/tool_permissions.py`, plugin registration in `teaagent/plugins.py`  
**What:** A central dictionary maps string keys (provider name, tool name, plugin ID) to factory functions or class instances. Components register themselves; consumers look up by key.  
**Why:** Allows dynamic extension (plugins, new backends) without modifying existing code. Avoids hard-coded `if provider == "openai"` branches scattered across the codebase.  
**Example:**
```python
_REGISTRY: dict[str, type[KnowledgeBackend]] = {}

def register_backend(name: str, cls: type[KnowledgeBackend]) -> None:
    _REGISTRY[name] = cls

def get_backend(name: str) -> KnowledgeBackend:
    return _REGISTRY[name]()
```
**Limitation:** Proposed ADR-0013 notes that the current implementation uses module-level dicts rather than an explicit `BackendRegistry` class — this makes testing harder.

---

## 3. Strategy Pattern

**Where:** `teaagent/policy.py` (permission mode strategies), `teaagent/model_routing.py` (routing strategies), `teaagent/governance/tool_lint.py` (validation profiles)  
**What:** A family of algorithms (permission check strategies, model selection strategies) is encapsulated behind a common interface. The context object holds a reference to the current strategy and delegates to it.  
**Why:** Permission modes (READ_ONLY, WORKSPACE_WRITE, PROMPT, ALLOW, DANGER_FULL_ACCESS) are five distinct approval algorithms. Encoding them as strategy objects avoids a 5-branch `if/elif` chain in every tool-call check.

---

## 4. Observer / Event Hook Pattern

**Where:** `teaagent/hooks.py`, `teaagent/audit.py`  
**What:** Hooks registered in `HookRegistry` are called at lifecycle events (pre-tool, post-tool, on-error, on-budget-exceeded). Audit events are emitted to `AuditLogger`, which fans out to registered handlers.  
**Why:** Separates cross-cutting concerns (audit logging, telemetry, UI notification) from the agent execution loop. The runner does not know what the audit logger does with events.  
**Example:**
```python
# hooks.py
class HookRegistry:
    def on_tool_call(self, fn: Callable[[ToolCallEvent], None]) -> None:
        self._pre_tool_hooks.append(fn)
    def fire_pre_tool(self, event: ToolCallEvent) -> None:
        for hook in self._pre_tool_hooks:
            hook(event)
```

---

## 5. Chain of Responsibility

**Where:** `teaagent/audit.py` (hash chain), `teaagent/approval_manager.py` (approval pipeline)  
**What:** Each handler in a chain processes a request and passes it to the next handler (or halts). For audit events, each event is processed → redacted → hashed → appended. For approvals, each check (budget, permission mode, JIT, multi-sig) may approve or halt.  
**Why:** Allows adding, removing, or reordering validation steps without changing the core execution path. The audit chain and approval chain are both open for extension.

---

## 6. Factory Method

**Where:** `teaagent/agent_factory.py`, `teaagent/llm/__init__.py` (`create_llm_adapter`), `teaagent/sandbox.py`  
**What:** A factory function/method creates objects based on configuration, hiding the concrete class from the caller.  
**Why:** The caller of `create_llm_adapter(config)` does not need to know whether it gets a `ClaudeAdapter`, `OpenAIAdapter`, or `GeminiAdapter`. Configuration drives object construction.  
**Example:**
```python
def create_llm_adapter(config: ProviderConfig) -> LLMAdapter:
    match config.provider:
        case "anthropic": return ClaudeAdapter(config)
        case "openai":    return OpenAIAdapter(config)
        case "gemini":    return GeminiAdapter(config)
        case _: raise ValueError(f"Unknown provider: {config.provider}")
```

---

## 7. Decorator / Wrapper Pattern

**Where:** `teaagent/redaction.py` (wraps audit event payloads), `teaagent/budget_monitor.py` (wraps LLM calls with cost tracking)  
**What:** A wrapper adds behaviour (redaction, cost tracking) to an existing operation without modifying its interface.  
**Why:** The runner calls `adapter.complete(req)` without knowing that a budget monitor is tracking the token cost. The budget monitor wraps the adapter and intercepts the response.

---

## 8. Command Pattern

**Where:** `teaagent/tui/_commands.py`, `teaagent/cli/_handlers/`  
**What:** Each slash command (`/cost`, `/undo`, `/plan`, `/approve`) is an encapsulated command object (or function) with a consistent `execute(session, args) -> CommandResult` signature.  
**Why:** Allows the TUI REPL to dispatch commands uniformly without a large `if cmd == "/cost": ... elif cmd == "/undo": ...` block. New commands are added as new handlers, not as new branches.

---

## 9. Circuit Breaker (Budget Enforcement)

**Where:** `teaagent/budget.py`, `teaagent/budget_monitor.py`  
**What:** A `RunBudget` tracks cumulative cost and token usage. Once a threshold is exceeded, the circuit opens and further LLM calls are rejected until the operator resets or the run ends.  
**Why:** Prevents runaway cost from retry storms or infinite loops. The circuit breaker pattern is more expressive than a simple per-call check because it maintains state across multiple calls.

---

## 10. Template Method

**Where:** `teaagent/runner.py` (agent run loop), `teaagent/swarm.py` (swarm execution)  
**What:** A base class defines the skeleton of an algorithm (plan → iterate → approve → execute → log), and subclasses or configuration objects override specific steps (how to approve, which tools are available).  
**Why:** The agent run loop is the same regardless of permission mode, provider, or tool set. The template method lets configuration objects customise individual steps without rewriting the loop.

---

## 11. Atomic Write (Write-Temp + Rename)

**Where:** Throughout `teaagent/` wherever JSONL files are written  
**What:** Write the new content to a `.tmp` file in the same directory, then `os.rename()` it over the target. On POSIX, `os.rename()` is atomic — readers either see the old file or the new file, never a partial write.  
**Why:** Prevents readers from observing a half-written JSON line if the process is killed mid-write. This is a lower-level pattern than the Gang of Four catalog but it is used pervasively and deserves explicit documentation.

---

## 12. Dependency Injection (Configuration-Driven)

**Where:** `teaagent/chat_agent.py` (`ChatAgentConfig`), `teaagent/llm/_transport.py` (`HTTPTransport` interface)  
**What:** Instead of hard-coding concrete classes, a config object or constructor parameter accepts an interface and injects the concrete implementation at the call site.  
**Why:** Enables testing (inject a mock transport, inject a no-op audit logger) without patching module globals. The proposed ADR-0016 refactoring would extend this to tool factories.  
**Current limitation:** `ChatAgentConfig` directly instantiates several concrete classes (CodeAnalysisConfig, LSPServerManager) rather than injecting interfaces — a known coupling issue tracked in ADR-0012.

---

## 13. Immutable Event / Value Object

**Where:** `teaagent/audit.py` (`AuditEvent` is a frozen `dataclass`), `teaagent/llm/_types.py` (`LLMResponse`)  
**What:** Events and response objects are created once and never mutated. All fields are set at construction time.  
**Why:** Audit events must not be modified after emission — immutability enforces this at the type level. Frozen dataclasses produce `FrozenInstanceError` on attempted mutation, catching bugs at development time rather than at runtime corruption.
