# chat_agent — Behavior Specification

## Module Purpose

`chat_agent.py` is the primary entry point for all agent execution. It assembles and wires together the LLM engine, tool registry, skill loader, memory catalog, budget, approval policy, and audit logger, then delegates to `AgentRunner` to execute an iterative reasoning loop.

---

## Behavior Contract

### `run_chat_agent(config, task, ...)`

**What the module guarantees:**

1. **Task execution completeness** — The agent will attempt to complete `task` or explicitly terminate with a status (`completed`, `budget_exceeded`, `suspended`, `error`). It will never return without a `RunResult`.
2. **Cost tracking** — The `_cost_cents` key in context is incremented on every LLM call. `RunResult.cost_cents` reflects the actual sum across all iterations.
3. **Audit trail** — Every tool call and LLM decision is emitted to the `AuditLogger` before and after execution. The heartbeat (if enabled) emits periodic liveness events.
4. **Memory auto-curation** — On a `completed` run, a summary entry is written to `MemoryCatalog` unless an identical `auto-curated` entry exists in the last 50 entries.
5. **Budget enforcement** — `ModelDecisionEngine.decide()` calls `budget.check_cost_preflight()` before every LLM request. If the budget is exceeded, the call is aborted before sending tokens.
6. **Skill loading audit** — A `skill_load` event is always recorded at the start of `_run_chat_agent_impl`, whether skills were found or not.
7. **Heartbeat lifecycle** — If `heartbeat_seconds > 0`, the `Heartbeat` thread is started before `runner.run()` and unconditionally stopped in the `finally` block.
8. **Plan contract injection** — If `context_extra` contains a `plan_contract` dict, it is reconstructed into a `PlanContract` object and set as `runner._plan_contract` before execution begins.
9. **Subagent registration** — If `enable_subagent=True` and `depth < max_subagent_depth`, subagent tools are registered on every call to `_run_chat_agent_impl`.

### `ModelDecisionEngine.decide(context)`

**What the method guarantees:**

1. **Always returns a `Decision`** — On parse failure after `max_parse_retries` retries, it falls back to `_plain_text_answer_fallback()` or returns a `FinalAnswer` with a sentinel error payload.
2. **Retry loop correctness** — When JSON parse fails and retries remain, the invalid response and a repair request are appended to the message history before the next LLM call.
3. **Cost accumulation** — `context['_cost_cents']`, `context['_input_tokens']`, and `context['_output_tokens']` are accumulated (not replaced) on each LLM response.
4. **Stream filtering** — When `stream=True` and `stream_text_only=True`, the raw `on_chunk` callback is wrapped with `DecisionContentStreamer` to strip JSON scaffolding.

---

## Invariants

| Invariant | Location |
|-----------|----------|
| `config.root` is always an absolute resolved `Path` | `ChatAgentConfig.from_root()` line 107 |
| `skill_source_profile='custom'` without `skill_search_dirs` raises `ValueError` | `_run_chat_agent_impl()` line 472 |
| `heartbeat` is always stopped in `finally`, even if runner raises | `_run_chat_agent_impl()` lines 621–623 |
| `_auto_curate_memory()` is called only on `result.status == 'completed'` | line 673 |
| `context['_cost_cents']` is always added to, never overwritten | `ModelDecisionEngine.decide()` lines 238–239 |
| `adapter` is always non-None when `_run_chat_agent_impl` is called (created by caller if not passed) | Enforced by `run_chat_agent()` signature |
| Registry is marked `_registry_fresh = registry is None` to prevent duplicate tool registration | line 438 |

---

## State Machine — Agent Execution Lifecycle

```
┌──────────────────────────────────────────────────────┐
│  run_chat_agent() / _run_chat_agent_impl()            │
│                                                       │
│  ① Build tool_registry (fresh or passed)             │
│  ② Register optional tools (code analysis, subagent, │
│     git, browser, MCP trust)                         │
│  ③ Load project instructions + memories              │
│  ④ Load skills (eager / index_only mode)             │
│  ⑤ Build RunBudget and ModelDecisionEngine           │
│  ⑥ Build ApprovalPolicy (with approval store)        │
│  ⑦ Build AgentRunner                                 │
│  ⑧ Start Heartbeat (if enabled)                      │
│  ⑨ runner.run() ──────────────────────┐              │
│                                       │              │
│     ┌─────────────────────────────────▼──┐           │
│     │  AgentRunner iteration loop        │           │
│     │  Per iteration:                    │           │
│     │    a. engine.decide(context)       │           │
│     │       ├── assemble prompt          │           │
│     │       ├── LLM call (with retries)  │           │
│     │       └── return Decision          │           │
│     │    b. Execute tool calls           │           │
│     │    c. Check budget/stop conditions │           │
│     └───────────────────────────────────┘           │
│                                                      │
│  ⑩ Stop Heartbeat (finally)                         │
│  ⑪ _auto_curate_memory() (if completed)             │
│  ⑫ Return RunResult                                  │
└──────────────────────────────────────────────────────┘
```

### Decision Retry State Machine

```
[LLM call]
    │
    ▼
[parse_model_decision()]
    │
    ├── success ──► return Decision
    │
    └── ToolValidationError
            │
            ├── attempt < max_parse_retries ──► append repair prompt ──► [LLM call]
            │
            └── attempt == max_parse_retries
                    │
                    ├── _plain_text_answer_fallback() returns FinalAnswer ──► return it
                    │
                    └── return FinalAnswer(sentinel error payload)
```

### Memory Auto-Curation Gate

```
result.status == 'completed'?
    NO  ──► skip
    YES ──► build summary
               │
               ├── summary empty? ──► skip
               │
               └── duplicate in last-50 entries? ──► skip
                       │
                       NO ──► MemoryCatalog.add(summary, tags=('auto-curated', 'run-summary'))
```
