# chat_agent — Risk Vectors, Failure Modes, Edge Cases, Known Issues

## Risk Vectors

### CHA-R-001: Deprecated `run_chat_agent` keyword-only signature silently accepted

- **File:line** — `chat_agent.py:401–416`
- **Description** — The legacy `run_chat_agent(*, task=..., adapter=..., config=...)` form emits only a `DeprecationWarning` and continues. Any caller that passes `adapter=None` along with keyword-only args will silently use `None` as the adapter, causing a downstream `AttributeError` inside `_run_chat_agent_impl`.
- **Impact** — Potential `AttributeError` at `adapter.complete()` with a confusing traceback.
- **Mitigation** — Callers should use the positional form. The deprecation warning is not enforced.

---

### CHA-R-002: `_plain_text_answer_fallback` bypasses structured decision contract

- **File:line** — `chat_agent.py:272–286`
- **Description** — When JSON parse fails on all retries, the fallback checks if the task "looks like a simple question". If heuristics match, the raw LLM text is returned as a `FinalAnswer` without any tool call validation or schema enforcement.
- **Impact** — Could return nonsense or partial LLM output as an answer for simple factual tasks. No audit event records the fallback decision.
- **Mitigation** — `metadata={'decision_fallback': 'plain_text_final_answer'}` is set but callers must check it.

---

### CHA-R-003: `plan_contract` injection uses `object.__setattr__` on frozen dataclass

- **File:line** — `chat_agent.py:596–604`
- **Description** — `AgentRunner` is not a frozen dataclass, but the pattern `object.__setattr__(runner, '_plan_contract', ...)` bypasses normal attribute assignment. If `AgentRunner`'s `__init__` already sets `_plan_contract`, this works; if `AgentRunner` changes its initialization to be truly immutable, this will break silently or raise `AttributeError`.
- **Impact** — Fragile coupling between `chat_agent.py` and `AgentRunner` internals.

---

### CHA-R-004: Skill loading errors not propagated to caller

- **File:line** — `chat_agent.py:474–522`
- **Description** — `load_skills_with_report()` returns skipped/warning items but does not raise on partial failures. Skipped skills are only recorded in the `skill_load` audit event. The caller has no way to detect that an expected skill was silently dropped.
- **Impact** — Silent skill degradation that may change agent behavior without any user-visible error.

---

### CHA-R-005: `_registry_fresh` logic gates tool registration to the first call only

- **File:line** — `chat_agent.py:438–465`
- **Description** — When a `registry` is passed in, `_registry_fresh = False` and none of the optional tools (code analysis, git, browser, MCP trust) are registered. This is the intended behavior for subagent calls, but callers who pass a pre-built registry and expect these tools to be registered will find them absent.
- **Impact** — Subagent calls or custom registry callers may silently lack tools.

---

### CHA-R-006: `_auto_curate_memory` is not transactional

- **File:line** — `chat_agent.py:666–686`
- **Description** — The deduplication check (`catalog.list(limit=50)`) and the `catalog.add()` call are not atomic. Under concurrent runs sharing the same workspace root, duplicate auto-curated entries can be written.
- **Impact** — Memory catalog grows with duplicate run summaries.

---

### CHA-R-007: Heartbeat thread leak if `runner.run()` raises an unexpected exception

- **File:line** — `chat_agent.py:575–623`
- **Description** — The `finally` block does stop the heartbeat, but if `object.__setattr__` (line 596) raises (e.g., `AttributeError`), the exception occurs before `runner.run()`, and the heartbeat thread may have been started (line 580) but only stopped if the `finally` runs. The `finally` does run in this case — this is safe. However if the heartbeat `start()` itself raises, `heartbeat` remains non-None and `stop()` will be called on a potentially corrupt object.
- **Impact** — Low probability; heartbeat thread leak.

---

### CHA-R-008: `max_estimated_cost_cents = -1` silently delegates to `RunBudget` default

- **File:line** — `chat_agent.py:523–527`
- **Description** — A value of `-1` falls through the condition `if config.max_estimated_cost_cents >= 0` to `RunBudget().max_estimated_cost_cents`. This is documented behavior but is easy to misunderstand: `-1` does NOT mean "no limit", it means "use RunBudget default".
- **Impact** — Unexpected cost caps if callers pass `-1` intending unlimited.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `task` is an empty string | `ModelDecisionEngine.decide()` builds a prompt with an empty task; LLM receives a near-empty user message |
| `selected_skills=frozenset()` with `skill_prompt_mode='eager'` | `load_skills_with_report()` returns empty skills list; model receives no skill prompts |
| `initial_observations` passed to a fresh (non-resumed) run | Observations are appended to runner context before the first LLM call |
| `chat_messages` is a non-empty list with no prior context | Used as-is; the model sees historical messages before the current task |
| `skill_source_profile='custom'` with empty `skill_search_dirs=[]` | Raises `ValueError` at line 472 (checked: `not config.skill_search_dirs`) |

---

## Known Issues (with file:line refs)

| ID | Description | Location |
|----|-------------|----------|
| CG-03 (partial) | Cost on decision retries accumulates correctly in `context['_cost_cents']` but subagent calls create their own `_run_chat_agent_impl` frames with separate context dicts — session-level cost aggregation depends on the caller | `chat_agent.py:238–245` |
| Decision fallback has no audit event | `FinalAnswer` with `decision_fallback` metadata is returned but not recorded in the audit log as a distinct event | `chat_agent.py:263–269` |
| `_subagent_error` is defined but never called | The function at line 655 builds an error dict but no call site in this file uses it; it may be dead code or intended for future use | `chat_agent.py:655–663` |
