# Engineering Architecture Critique — teaAgent
**Date:** 2026-06-06  
**Scope:** HEAD `main` only — no aspirational claims, no roadmap items  
**Method:** Direct code reading of ~280 source files; every claim below is traceable to a file:line

---

## 1. Architecture Foundations

### Design Patterns Actually Used

**Core run loop — Strategy + Decide/Execute cycle**  
The `AgentRunner.run()` loop ([`runner/_core.py:801`](../../teaagent/runner/_core.py)) is a while-loop over a budget ceiling. Each iteration calls an injected `decide: DecisionFn` callback, receives either a `FinalAnswer` or `ToolRequest`, and dispatches accordingly. This is a clean strategy pattern: the decision engine is fully swappable. `ModelDecisionEngine` in `chat_agent.py:158` is the production implementation; `FakeAdapter` exists for tests.

**Layered delegation**  
`AgentRunner` → `ToolRegistry.execute()` → tool handler. Three clean layers. The runner doesn't know how tools work; tools don't know they're in a run.

**Value objects with frozen dataclasses**  
`AuditEvent`, `ToolDefinition`, `RunResult`, `ToolAnnotations`, `ChatAgentConfig` are all `@dataclass(frozen=True)`. Good — prevents accidental mutation of configuration and records.

**Append-only JSONL audit with hash-chaining**  
`AuditLogger` ([`audit.py:111`](../../teaagent/audit.py)) writes every event to a JSONL file with SHA-256 chaining and per-run HMAC. This is a defensible forensics story.

**ContextVar for ambient state**  
`tool_call_context.py` and `subagent_run_context.py` use Python `ContextVar` for thread-safe ambient state. This is the correct pattern for passing audit context and parent run IDs without threading the values through every call signature.

**Registry pattern for tools**  
`ToolRegistry` is a dict-backed registry with schema validation, rate limiting, and hook dispatch. Plugins can register tools at startup via entry-points. Clean extension point.

### Strengths
- Synchronous, single-threaded run loop is simple to trace and debug
- `RunBudget` + `PhaseTracker` for multi-axis budget enforcement is genuinely useful
- Audit chain integrity is verifiable after the fact
- `PermissionMode` enum with a well-defined ladder (read-only → prompt → workspace-write → allow → danger-full-access) is a sound model

### Weaknesses
- The run `context` dict is a mutable shared state bag, not a typed structure (see §6)
- `chat_agent.py` acts as a God Orchestrator — 17 first-party imports, 838 lines
- No async-first design; async is grafted on as a bridge (see §4)

---

## 2. Scalability Ceilings

### ThreadPoolExecutor Limits

**`ApprovalPolicy` spawns an unmanaged thread pool per instantiation**  
[`policy.py:70`](../../teaagent/policy.py): `concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix='sig-collect')` is created in `__post_init__`. Since `ApprovalPolicy` is constructed fresh for every `run_chat_agent()` call and tests, and there is no `shutdown()`, `__del__`, or context-manager usage anywhere, these pools accumulate. In a long-lived process (daemon, TUI session, test suite run of 3000+ tests), this creates dozens to hundreds of leaked threads.

**Swarm parallelism ceiling**  
[`swarm.py:692`](../../teaagent/swarm.py): `ThreadPoolExecutor(max_workers=self._max_parallel)` with no default cap visible from the invocation. Python's default `ThreadPoolExecutor` on CPython is `min(32, cpu_count + 4)`. Each subagent thread is itself a blocking synchronous HTTP call. At 32 concurrent subagents doing LLM calls, you saturate file descriptors and OS thread limits before you saturate the LLM API.

### JSONL Ceiling

**`AuditLogger.events` list grows without bound in memory**  
[`audit.py:123`](../../teaagent/audit.py): `self.events: list[AuditEvent] = []` is never pruned. For a process that runs 100 tasks (e.g., an automation daemon), the in-memory event list grows forever. At ~500 bytes per event and 1000 events per run × 100 runs, this is ~50 MB of live objects that will never be collected.

**`verify_chain_integrity()` reads the full file into memory**  
[`audit.py:463`](../../teaagent/audit.py): `self.path.read_text()` followed by `splitlines()`. For a 10k-event audit log with rich payloads, this is fine. At 100k events with full tool outputs, this becomes a blocking pause. No streaming verification exists.

**`runs-index.jsonl` grows forever**  
[`run_store.py:47`](../../teaagent/run_store.py): `self._index_path = self.store_dir / 'runs-index.jsonl'` is appended forever. Listing runs reads this file. At 10k+ runs, listing requires reading the entire index. No pagination, no pruning, no index rotation.

### In-Memory Constraints

**`_approval_queues` global dict — no eviction**  
[`subagents/_approval_queue.py:673`](../../teaagent/subagents/_approval_queue.py): `_approval_queues: dict[tuple[str, str], CentralizedApprovalQueue] = {}` is module-level mutable state. Queues are created on demand and removed only via explicit `pop()` in cleanup code. In a daemon that runs many parallel batches, orphaned queues accumulate. No TTL, no LRU, no max size.

**Compacted summary chain grows linearly**  
[`context.py:74`](../../teaagent/context.py): `compacted['compacted_summary'] = f'{existing_summary}\nThen, {summary}'`. Each compaction appends to the previous summary string. Over 50+ compaction cycles on a very long run, the summary itself becomes a significant fraction of context.

**Ceiling summary:**

| Component | Fails at scale when... |
|-----------|------------------------|
| `ApprovalPolicy` thread pool | > ~100 policy instantiations (test suite, daemon) |
| Swarm parallelism | > ~32 concurrent subagents (OS thread limit) |
| `AuditLogger.events` | Long-lived daemon, many runs without restart |
| `verify_chain_integrity()` | > 50k events with large payloads |
| `runs-index.jsonl` | > 10k runs in one workspace |
| `_approval_queues` global | > hundreds of concurrent batched subagent runs |

---

## 3. Technical Debt Ledger

| ID | Location | Issue | Effort to Fix | Impact if Left |
|----|----------|--------|---------------|----------------|
| TD-01 | `policy.py:65-90` | `ApprovalPolicy` is `@dataclass(frozen=True)` but bypasses freeze via `object.__setattr__` to store a `ThreadPoolExecutor`. Breaks equality, hashing, and the immutability contract. | Medium (redesign as regular class or split state/config) | High — false confidence in immutability; thread pool leak |
| TD-02 | `policy.py:70` | Unmanaged `ThreadPoolExecutor` created per policy instance, never shut down | Low (add `shutdown(wait=False)` or make context manager) | Medium — thread accumulation in long processes |
| TD-03 | `subagents/_approval_queue.py:673` | Module-level `_approval_queues` dict with no eviction policy | Medium (add TTL or weak refs) | Medium — unbounded growth in daemon use |
| TD-04 | `audit.py:123` | `self.events` list never pruned — grows for life of process | Medium (add max-events cap or separate per-run storage) | Medium — memory leak in daemon |
| TD-05 | `runner/_core.py:389` | `context` dict is an untyped mutable shared-state bag; side-channel data (`_cost_cents`, `_input_tokens`) written by `ModelDecisionEngine` and read by runner via `context.get()` | High (introduce typed `RunContext` dataclass) | High — implicit protocol, any new code that touches context silently breaks invariants |
| TD-06 | `chat_agent.py:386` | `run_chat_agent()` has dual signatures (positional/keyword-only) dispatched via `*args/**kwargs`. Deprecation warning is emitted but not enforced | Low (remove old signature in next major version) | Low — caller confusion, missed migrations |
| TD-07 | `cli/_handlers/_agent.py:3026 lines` | God handler file, no real sub-structure | High (split into focused handlers) | Medium — every new CLI feature lands here, growing the coupling surface |
| TD-08 | `tui/__init__.py:1632 lines` | TUI UI logic and business logic interleaved in one file | High (extract controller) | Medium — testing UI requires whole TUI; refactor is risky |
| TD-09 | `audit.py:381` | `_prev_hash` read without `self._lock` inside `file_lock` — CPython GIL makes this safe today but not guaranteed in Python 3.13+ nogil mode | Low (add explicit lock) | Low now, High in nogil builds |
| TD-10 | `runner/_core.py:325` | `from teaagent.ergonomics.run_summary import ...` — lazy import inside method body, used to avoid circular dependency | Medium (fix the circular dependency properly) | Low now — runtime cost; signals structural coupling |
| TD-11 | `policy.py:434` | `asyncio.get_running_loop()` + thread executor to bridge sync→async. If already in an async context with a restricted executor, this can deadlock | Medium (unify async model) | Medium — rare deadlock in embedded/test contexts |
| TD-12 | Tests: 1208 `MagicMock`/`@patch` usages | Heavy mock coverage means many tests verify mock contracts, not actual behavior. `test_zero_coverage_modules.py` and `test_low_coverage_modules.py` acknowledge known coverage gaps | Ongoing (replace mocks with `FakeAdapter` pattern where possible) | Medium — false green tests on behavior regressions |

---

## 4. Coupling Analysis

### Coupling Matrix (directional, by import weight)

```
chat_agent.py ──────────→ audit, budget, context, heartbeat, hooks, llm,
                           memory, policy, prompt, runner, skill_loader,
                           subagents, tools, workspace_tools  [17 imports]
                           
runner/_core.py ─────────→ audit, auto_mode, budget, budget_monitor, context,
                           errors, file_policy, long_result_envelope, phase_tracker,
                           plugins, policy, proof_of_use, subagent_run_context,
                           tool_call_context, tools  [15 imports]
                           
approval_manager.py ─────→ errors, read_only_gate, config_loader (runtime),
                           ergonomics/approval_store (TYPE_CHECKING)
                           
policy.py ───────────────→ approval_manager (full re-export for compat)
                           Effectively: policy.py IS approval_manager.py with a compat shim on top
```

### Most Tightly Coupled Problem Areas

**1. `chat_agent.py` is the system integration point with no seam**  
You cannot use `AgentRunner` without going through `run_chat_agent()`, which pulls in browser tools, code analysis, git tools, memory catalog, skill loader, and subagent manager — even if you need none of them. Testing the runner requires either mocking all of these or accepting the full import graph.

**2. `policy.py` ↔ `approval_manager.py` dual-layer redundancy**  
`policy.py:37-90` re-declares `ApprovalPolicy` as a frozen dataclass wrapper around `ApprovalManager`. Every `ApprovalPolicy.assert_allowed()` call delegates to `self._approval_manager.assert_allowed()`. Two code paths for the same behavior — when they diverge, bugs are invisible.

**3. Mutable `context` dict couples runner ↔ decision engine**  
`ModelDecisionEngine.decide()` writes `_cost_cents`, `_input_tokens`, `_output_tokens` into the context dict ([`chat_agent.py:239`](../../teaagent/chat_agent.py)). `AgentRunner.run()` reads them back ([`runner/_core.py:816`](../../teaagent/runner/_core.py)). This is an implicit interface. Any new decision engine implementation must know and replicate this side-channel protocol or tokens/cost won't be tracked.

**4. `AuditLogger` is ambient state via ContextVar AND explicit dependency**  
The runner holds an explicit `self.audit` reference. Tool handlers can also access audit via `get_tool_call_context()` → `.audit`. Two pathways to the same object, neither documented as canonical. A tool that emits audit events through the ContextVar pathway bypasses the runner's event ordering assumptions.

### Would async/await help or hurt?

**Verdict: Would hurt significantly in the current codebase.**

To make `async/await` work properly throughout the system:
1. `LLMAdapter.complete()` would need to become `async` — but it uses `urllib` (blocking I/O) and `fcntl.flock` (not async-safe)
2. All tool handlers would need to be async-capable
3. `ApprovalPolicy`'s sync-in-async bridge ([`policy.py:434`](../../teaagent/policy.py)) would need to be replaced — it uses `asyncio.run()` as a fallback which fails inside an existing event loop
4. The `file_lock` in `storage.py` uses `fcntl.flock`, which blocks the event loop

The right async story would be: pick `asyncio` as the transport layer for LLM calls (HTTP streaming), keep tool dispatch synchronous with `asyncio.to_thread()` for blocking tools. That's a 2-4 week refactor.

---

## 5. Extensibility Gaps — Ranked by Effort × Impact

### Adding a New Surface (IDE plugin, web UI, mobile)
**Pain: High**

The CLI ([`cli/__init__.py`](../../teaagent/cli/__init__.py)) and TUI ([`tui/__init__.py`](../../teaagent/tui/__init__.py)) both directly construct `ChatAgentConfig` and call `run_chat_agent()`. There is no surface-agnostic protocol layer (no RPC interface, no server mode, no message queue). An IDE plugin would need to either:
- Embed the Python runtime and call `run_chat_agent()` directly (coupling to Python internals)
- Stand up its own HTTP server and duplicate the config/run setup logic

The TUI alone is 1632 lines with UI rendering and agent invocation interleaved. There is no controller/view separation to reuse in a different surface.

**What's missing:** A thin `AgentServer` abstraction that accepts `{task, config_overrides}` and returns a stream of events. The gateways (`gateway/_slack.py`, `_discord.py`, `_telegram.py`) suggest this was considered but each gateway reimplements its own run-chat-agent setup independently.

### Adding a New Tool Type
**Pain: Low**

`ToolRegistry.register()` takes a name, description, input schema, output schema, annotations, and handler. Adding a new tool is ~10 lines. MCP tools are already bridged via `mcp_tool_adapter.py`. WASM skills via `wasm_skill.py`. This is a genuine strength.

**Pain points:** Tool handlers must return `dict[str, Any]` — no typed contracts enforced at runtime. Schema validation is opt-in. A handler that returns `None` or a string will silently break tool call flow.

### Adding a New Approval Policy
**Pain: High**

`PermissionMode` is an `str` Enum ([`approval_manager.py:94`](../../teaagent/approval_manager.py)). Adding a new mode requires:
1. Adding a new `PermissionMode` value
2. Adding a new branch in `ApprovalManager.assert_allowed()` (the main dispatch function, ~200 lines)
3. Adding CLI/TUI flags to select it
4. Adding tests for all existing permission mode combinations with the new mode

The dispatch logic is not a strategy — it's a large conditional chain. New modes must understand and not break all existing mode semantics.

### Adding a New LLM Provider
**Pain: Low-Medium**

`LLMAdapter` ([`llm/_types.py`](../../teaagent/llm/_types.py)) is a simple interface: `complete(LLMRequest) -> LLMResponse`. `_adapters.py` has Claude/OpenAI/Gemini implementations. Adding a new provider means implementing one method. The pain comes from response format normalization (structured JSON output handling differs per provider, as evidenced by the `OpenAICompatibleAdapter` retry logic).

---

## 6. State Management

### Current State Map

| State | Location | Type | Thread-safe? | Transactional? |
|-------|----------|------|--------------|----------------|
| Run context (task, observations, cost) | `dict` passed by ref | Mutable dict | No — single-threaded by design | No — mutations are incremental |
| Audit events | `AuditLogger.events: list` | Mutable list | Yes — `threading.Lock` | Append-only, no rollback |
| JSONL on disk | `audit.path` file | JSONL append | Yes — `fcntl.flock` | Append-only; no transaction |
| Tool call context | `ContextVar` | Module-level ContextVar | Yes — ContextVar is thread-local | N/A |
| Parent run ID | `ContextVar` | Module-level ContextVar | Yes | N/A |
| JIT approval state | `JITApprovalState.approved_call_ids: set` | Mutable set | No explicit lock | No |
| Approval queues | `_approval_queues: dict` | Module-level global dict | No explicit lock | No |
| Compaction summary | `context['compacted_summary']` | String in context dict | N/A — single-thread | No |

### What Could Break

**Context dict mutation is not transactional**  
`_execute_tool_decision()` appends to `context['observations']` at [`runner/_core.py:680`](../../teaagent/runner/_core.py) and `720`. If `store_long_result()` raises halfway through, the observation dict is partially constructed and appended. There is no rollback. The next `decide()` call sees a corrupt observation.

**`_prev_hash` read without lock**  
[`audit.py:381`](../../teaagent/audit.py) — admitted in a comment: `_prev_hash is read without self._lock because (1) atomic string assignment (2) inside file_lock`. This is CPython-safe due to GIL but not Python-safe. Under Python 3.13 nogil, this is a data race.

**`_approval_queues` global is not lock-protected**  
[`subagents/_approval_queue.py:673`](../../teaagent/subagents/_approval_queue.py). In the swarm case, multiple threads call `get_or_create_centralized_queue()` simultaneously. The dict read-modify-write at lines 728-750 is not atomic even under CPython GIL with dict-reallocation.

**`AutoModeManager` state accumulates per-run**  
`AutoModeManager.record_tool_call()` and `record_iteration()` update counters ([`runner/_auto_mode_manager.py`](../../teaagent/runner/_auto_mode_manager.py)). Since `AgentRunner` is reused across calls (by design), these counters from a previous run can pollute the next run's auto-mode decisions if the runner is not reconstructed. No explicit reset between runs is documented.

---

## 7. Error Boundaries

### Silent Failures

**1. Audit disk I/O silently degraded**  
[`audit.py:439`](../../teaagent/audit.py): `OSError` is caught, stored in `self._disk_error`, and the run continues. The audit log on disk is now missing events, but the run proceeds as if nothing happened. A compliance user reading the chain will see a gap (hash mismatch) but won't know *when* the disk error started or how many events were lost. The 30-second cooldown means up to 30 seconds of events can be silently dropped after a single transient disk error.

**2. Plugin load failures are warnings, not errors**  
[`runner/_core.py:159`](../../teaagent/runner/_core.py): `load_plugins(registry)` failures are logged as warnings and execution continues. A plugin that was supposed to register a security-relevant tool (e.g., a compliance tool) silently fails to register, and the agent proceeds with fewer capabilities than intended.

**3. Subagent errors masquerade as tool results**  
[`subagents/_manager.py:397`](../../teaagent/subagents/_manager.py): `_error()` returns `{'status': 'error', 'final_answer': '', ...}` as a dict. The parent agent receives this as a tool observation result. If the parent's prompt doesn't explicitly instruct it to check `status == 'error'`, the parent may treat a failed subagent as a successful (empty-answer) subagent and continue. No exception is raised; no audit event marks this as a system failure.

**4. `_emit_summary()` silently swallowed**  
[`runner/_core.py:362`](../../teaagent/runner/_core.py): `try/except Exception: logger.debug(...)`. Summary generation failures are invisible to the user.

**5. Audit sink failures are logged but don't stop delivery**  
[`audit.py:449`](../../teaagent/audit.py): Failed sinks (e.g., a downed OpenTelemetry collector) are logged with `logger.error()` but the call proceeds. If the sink was the compliance endpoint, events are silently dropped.

### Cascading Failures

**Budget check triplicate**  
[`runner/_core.py:808,819,844`](../../teaagent/runner/_core.py): `_check_phase_budget()` is called three times per iteration loop. If `phase_tracker.phase_cost_cents()` has side effects (it does — it updates internal state), calling it three times per iteration means phase cost accumulates faster than expected. A budget that should allow 10 phase iterations may cut off at iteration 3-4 due to triple-counting.

**`RunCancelledError` from budget warning leaves partial state**  
[`runner/_core.py:275`](../../teaagent/runner/_core.py): When `BudgetAction.PROMPT_CONFIRM` fires at 90% budget, a `RunCancelledError` is raised. This exits the run loop, but the run's final state in the audit log shows `run_failed` (from `_handle_harness_error`). The audit already contains `budget_warning` events and potentially partial tool results. The run is not cleanly terminated; it's abruptly failed.

**`ToolPermissionError` exception path carries approval metadata**  
[`runner/_core.py:885`](../../teaagent/runner/_core.py): `ToolPermissionError` is caught specially to produce a `pending_approval` `RunResult`. This works when `approval_handler is None`. But the same exception is re-raised in `_execute_tool_decision` (line 640) with `from None`, losing the original cause. Debuggers see a truncated stack trace; audit events don't record the original permission denial reason.

---

## 8. Critical Assessment

*What a skeptical senior engineer would say:*

### 1. The "frozen" dataclass is a lie, and it has resource consequences
`ApprovalPolicy` is `@dataclass(frozen=True)` but uses `object.__setattr__` to bypass the freeze and store a `ThreadPoolExecutor` and an `ApprovalManager`. The frozen annotation on a class with embedded thread pools gives every reader a false guarantee: "this is safe to share, copy, hash." In reality it is none of those things. The thread pool is leaked on every instantiation. In the 3000+ test suite, this means hundreds of leaked thread pools. Fix: make it a regular class, or split the immutable config from the mutable session state.

### 2. The audit chain looks stronger than it is
L3 audit encryption stores the key on the same host (`~/.teaagent/audit-encryption/`). The code itself documents this limitation ([`audit.py:274`](../../teaagent/audit.py)): *"Note: Key is stored on the same host, so this protects against log file copying but not host/user compromise."* This is honest, but the feature's name ("L3 Full Encrypted") implies a higher security guarantee than it delivers. An operator deploying teaAgent for compliance purposes would see "encrypted audit logs" and reasonably conclude that a compromised container does not expose audit contents. That assumption is wrong.

### 3. The context dict is a latent API surface
`context = {'task': task, 'observations': []}` grows as the run progresses: `_cost_cents`, `_input_tokens`, `_output_tokens`, `decision_summary`, `compacted_summary`, `memory_keys`, `compaction_count`, `compression_ratio`. None of these keys are in a schema. Any module that reads or writes to this dict is an implicit API contract with no compiler enforcement. The side-channel cost injection ([`chat_agent.py:239`](../../teaagent/chat_agent.py)) and side-channel cost readback ([`runner/_core.py:816`](../../teaagent/runner/_core.py)) are the most fragile: if a new decision engine doesn't write `_cost_cents`, cost tracking silently reads `0.0`.

### 4. 280+ source files at v0.1.0 Alpha is a concentration risk
The `pyproject.toml` self-describes as `Development Status :: 3 - Alpha`. At alpha, codebase breadth should be minimum viable. Instead: `aibom.py`, `a2a_trace.py`, `anp_adapter.py`, `tsb_format.py`, `ultrawork.py`, `wasm_skill.py`, `sigstore_signer.py`, `federated_sync.py`, `swarm.py`, `tournament/`, `graphqlite_store.py` — all committed, most with thin or no tests. This is feature accumulation, not feature delivery. Every new file is a future maintenance obligation.

### 5. Test coverage is wide but mock-heavy
1208 `MagicMock`/`@patch` usages in tests. The acceptance tests in `tests/acceptance/` largely test that the CLI dispatches to the right handler (which is mocked), not that the handler produces correct output. `test_zero_coverage_modules.py` and `test_low_coverage_modules.py` acknowledge coverage gaps are tracked. Tracking gaps is good; the gaps themselves remain. The most dangerous untested paths are: the budget-check triple-call in the run loop, the async-from-sync bridge in ApprovalPolicy, and the subagent error masquerade.

### 6. No migration story for the context dict protocol
When `RunContext` eventually becomes a typed dataclass (it should), every module that reads `context.get('_cost_cents', 0.0)` or `context['observations']` will need updating. There are at least 15 such call sites across `runner/_core.py`, `chat_agent.py`, `context.py`, `subagents/_manager.py`, `plan_validator.py`, and ergonomics modules. This is a one-time large refactor with high regression risk.

---

## 9. Pain Points — Ranked by Effort × Impact

| Rank | Pain Point | Effort | Impact |
|------|-----------|--------|--------|
| P1 | Introduce typed `RunContext` to replace mutable context dict | High | Critical — removes the entire class of implicit-contract bugs |
| P2 | Fix `ApprovalPolicy` frozen-but-mutable design; manage thread pool lifecycle | Medium | High — stops thread leaks; restores immutability guarantee |
| P3 | Add `AuditLogger` event cap or separate per-run stores; make `verify_chain_integrity()` streaming | Medium | High — prevents daemon memory growth |
| P4 | Evict `_approval_queues` global via TTL or WeakValue dict | Low | Medium — prevents queue accumulation in long-lived processes |
| P5 | Split `chat_agent.py` into `setup.py` (wiring) + `engine.py` (run loop) | Medium | High — enables testing runner without full dependency graph |
| P6 | Add lock to `_approval_queues` dict operations | Low | Medium — correctness under nogil/concurrent batch subagents |
| P7 | Remove deprecated `run_chat_agent(*args)` signature | Low | Low — reduces cognitive load |
| P8 | Fix `_check_phase_budget()` triple-call in run loop | Low | Medium — prevents premature budget exhaustion |
| P9 | Replace CLI god-file `_agent.py` (3026 lines) with focused modules | High | Medium — long-term maintainability |
| P10 | Normalize subagent errors to exceptions, not status-dict returns | Medium | Medium — makes failure visible to parent and auditable |

---

## 10. Recommended Rewrites vs. Refactors

### Rewrite (break API)
- `ApprovalPolicy` — redesign as a regular class with explicit lifecycle management; eliminate the frozen-but-mutable pattern
- Context protocol — introduce `RunContext` typed dataclass to replace the dict; migrate incrementally using `TypedDict` as intermediate step

### Refactor (preserve API, improve internals)
- `AuditLogger` — add configurable `max_in_memory_events` with oldest-event drop; make chain verification streaming
- `chat_agent.run_chat_agent()` — extract a `RunSetup` helper that wires tools/memory/skills/subagents, separating it from the execution call
- `runner/_core.py` — deduplicate the `_check_phase_budget()` call from 3× to 1× per iteration with explicit pre/post labels
- `subagents/_manager.py::_error()` — raise `SubagentError` instead of returning dict; caller can convert to audit event

### Leave alone (cost exceeds benefit now)
- JSONL storage format — switching to SQLite or a real DB would require migration tooling and breaks the simple forensics story
- Synchronous HTTP transport — replacing urllib with httpx/aiohttp is the right long-term direction but requires the full async refactor first; doing it piecemeal is worse than doing it all at once
- `asyncio` threading model — do not introduce async/await until LLM transport is the bottleneck and the sync-in-async bridge is removed

---

*All file references in this document point to HEAD `main` as of 2026-06-06. Architecture findings are based on direct code reading; no aspirational claims are included.*
