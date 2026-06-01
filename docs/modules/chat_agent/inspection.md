# chat_agent — Purpose, Dependencies, Exported API, and Call Graph

## Purpose

`chat_agent.py` is the **orchestration layer** of teaagent. It wires together every subsystem (LLM, tools, memory, skills, budget, approval, audit, heartbeat) and delegates the actual iterative reasoning loop to `AgentRunner`. Callers at the CLI and TUI layer only need to call `run_chat_agent(config, task)` — all internal wiring is hidden.

---

## Source File

`teaagent/chat_agent.py` — 713 lines

---

## Dependencies

### Standard Library
- `contextlib`, `threading`, `warnings`, `dataclasses`, `pathlib`, `typing`, `uuid`

### Internal teaagent packages

| Import | Used for |
|--------|----------|
| `teaagent.audit.AuditLogger` | Event logging throughout execution |
| `teaagent.auto_mode.AutoModeConfig` | Automatic mode configuration for runner |
| `teaagent.browser_tools.register_browser_tools` | Registers browser navigation tools |
| `teaagent.budget.RunBudget` | Tracks iteration, tool call, and cost limits |
| `teaagent.code_analysis.*` | LSP-backed code analysis and context injection |
| `teaagent.context.ContextCompactor` | Context compaction passed to runner |
| `teaagent.errors.ToolValidationError` | Caught during decision JSON parsing retries |
| `teaagent.heartbeat.Heartbeat` | Background liveness ping thread |
| `teaagent.hooks.HookRegistry` | Pre/post tool call hooks |
| `teaagent.llm.*` | LLM adapter, message, and request types |
| `teaagent.memory.*` | `MemoryCatalog`, `memory_entries_to_prompt` |
| `teaagent.policy.*` | `ApprovalPolicy`, `MultiSigQuorumConfig`, `PermissionMode` |
| `teaagent.prompt.*` | `assemble_agent_prompt`, `parse_model_decision`, schema constants |
| `teaagent.runner.*` | `AgentRunner`, `ApprovalHandler`, `BudgetPromptHandler`, `Decision`, `FinalAnswer`, `RunResult` |
| `teaagent.skill_loader.*` | Skill discovery, loading, and token estimation |
| `teaagent.subagents.*` | `SubagentManager`, `register_subagent_tools` |
| `teaagent.tools.ToolRegistry` | Container for all registered tools |
| `teaagent.workspace_tools.*` | Workspace tool builder and git tools |

### Lazy / conditional imports (inside functions)
- `teaagent.config_loader.ConfigResolver` — in `ChatAgentConfig.from_root()`
- `teaagent.ergonomics.approval_store.ApprovalPresetStore` — when `use_approval_store=True`
- `teaagent.mcp_trust.apply_mcp_trust_hooks` — on fresh registry
- `teaagent.plan.PlanContract` — when context_extra contains plan_contract
- `teaagent.streaming.content_filter.DecisionContentStreamer` — when streaming with text_only

---

## Exported API

### Classes

| Name | Type | Description |
|------|------|-------------|
| `ChatAgentConfig` | `@dataclass(frozen=True)` | All configuration for a single agent run |
| `ModelDecisionEngine` | class | Wraps LLM adapter; assembles prompts, retries on parse failure |

### Functions

| Name | Signature | Description |
|------|-----------|-------------|
| `run_chat_agent` | `(config, task, *, ...) -> RunResult` | Primary public entry point; supports positional and deprecated keyword-only forms |
| `with_memories` | `(context, memories) -> dict` | Merges memory list into agent context |
| `register_subagent_tool` | `(registry, *, adapter, config, depth) -> None` | Register subagent tools on an existing registry |

### Private / Internal (used by module itself)

| Name | Description |
|------|-------------|
| `_run_chat_agent_impl` | Actual implementation after argument normalization |
| `_plain_text_answer_fallback` | Fallback for simple Q&A tasks when JSON parse fails |
| `_looks_like_simple_answer_task` | Heuristic to detect factual question tasks |
| `_looks_like_plain_text_answer` | Heuristic to validate free-text answers |
| `_auto_curate_memory` | Post-run memory curation |
| `_build_auto_curated_summary` | Builds the memory entry text |
| `_subagent_error` | Builds a standardized error dict for subagent failures |

---

## Entry Points

1. **Primary** — `run_chat_agent(config, task)` called by:
   - `teaagent/tui/__init__.py::TeaAgentTUI._run_agent_task()` (line 907)
   - `teaagent/cli/_handlers/chat_repl.py::run_chat_repl()` (line 1023, 1283)
   - `teaagent/cli/_handlers/_chat.py::chat_command()` (indirectly via TUI)
   - `teaagent/cli/_handlers/_agent.py::agent_run_task()` (via `DefaultCommandExecutor`)
   - `teaagent/chat_session_controller.py::ChatSessionController.execute_task()` (line 132)

2. **Secondary** — `ChatAgentConfig.from_root()` called widely to build configs from workspace root.

---

## Call Graph

```
run_chat_agent(args/kwargs)
  └─► _run_chat_agent_impl(config, task, ...)
        ├─► build_workspace_tool_registry(config.root)       [workspace_tools]
        ├─► register_code_analysis_tools(...)                 [optional]
        ├─► register_subagent_tools(...)                      [optional]
        ├─► register_git_tools(...)                           [optional]
        ├─► register_browser_tools(...)                       [optional]
        ├─► apply_mcp_trust_hooks(...)                        [optional]
        ├─► load_project_instructions(config.root)            [prompt]
        ├─► MemoryCatalog.search(task)                        [memory]
        ├─► discover_skill_index(...) / load_skills_with_report(...)  [skill_loader]
        ├─► audit_logger.record('skill_load', ...)            [audit]
        ├─► RunBudget(...)                                     [budget]
        ├─► ModelDecisionEngine(...)
        │     └─► decide(context)
        │           ├─► assemble_agent_prompt(...)            [prompt]
        │           ├─► budget.check_cost_preflight(...)      [budget]
        │           ├─► adapter.complete(LLMRequest(...))     [llm]
        │           └─► parse_model_decision(response)        [prompt]
        ├─► ApprovalPresetStore(config.root)                  [ergonomics]
        ├─► AgentRunner(...)
        │     └─► runner.run(task, decide=lambda, ...)
        ├─► Heartbeat.start() / .stop()                       [heartbeat]
        └─► _auto_curate_memory(...)
              └─► MemoryCatalog.add(...)                      [memory]
```
