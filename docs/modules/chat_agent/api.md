# chat_agent — Public API Reference

## Classes

---

### `ChatAgentConfig`

```python
@dataclass(frozen=True)
class ChatAgentConfig:
    root: Path
    max_iterations: int = 10
    max_tool_calls: int = 10
    max_estimated_cost_cents: int = 0
    allow_destructive: bool = False
    model: Optional[str] = None
    permission_mode: PermissionMode = PermissionMode.PROMPT
    memory_limit: int = 5
    approved_call_ids: frozenset[str] = frozenset()
    enable_subagent: bool = False
    max_subagent_depth: int = 1
    heartbeat_seconds: float = 0.0
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None
    stream_text_only: bool = True
    approval_handler: Optional[ApprovalHandler] = None
    budget_prompt_handler: Optional[BudgetPromptHandler] = None
    checkpoint_store: Any = None
    chat_messages: Optional[list[LLMMessage]] = None
    cancel_token: Optional[threading.Event] = None
    subagent_manager: Optional[SubagentManager] = None
    code_analysis_config: Optional[CodeAnalysisConfig] = None
    enable_git_tools: bool = False
    skill_search_dirs: Optional[list[str]] = None
    skill_source_profile: SkillSourceProfile = 'default'
    selected_skills: Optional[frozenset[str]] = None
    skill_prompt_mode: str = 'eager'
    hook_registry: Optional[HookRegistry] = None
    auto_mode_config: Optional[AutoModeConfig] = None
    use_approval_store: bool = True
    require_plan: bool = False
    skip_plan_check: bool = False
    validation_profile: Optional[str] = None
```

**Pre-conditions:** `root` must be convertible to an absolute `Path`.

**Post-conditions:** All fields are immutable (frozen dataclass). `root` is *not* automatically resolved in the default constructor — use `from_root()`.

#### `ChatAgentConfig.from_root(root, **kwargs) -> ChatAgentConfig`

**Pre-conditions:**
- `root` is a `str` or `Path` pointing to the workspace root (need not exist as a directory).
- Any `kwargs` key present in the constructor is accepted. Unknown keys raise `TypeError`.
- `skill_source_profile='custom'` requires `skill_search_dirs` to be provided in kwargs.

**Post-conditions:**
- `config.root` is `Path(root).resolve()`.
- Workspace config file (`.teaagent/config.json` or `.teaagent/config.toml`) values are merged as defaults for any field *not* present in `kwargs`.
- `memory_limit=None` in kwargs is treated as "not provided" and falls back to the dataclass default of `5`.

**Raises:** `ValueError` (from `ConfigResolver`) if config file is malformed.

---

### `ModelDecisionEngine`

```python
class ModelDecisionEngine:
    def __init__(
        self,
        *,
        adapter: LLMAdapter,
        registry: ToolRegistry,
        budget: Optional[RunBudget] = None,
        project_instructions: str = '',
        model: Optional[str] = None,
        task_spec: Optional[str] = None,
        stream: bool = False,
        on_chunk: Optional[Callable[[str], None]] = None,
        stream_text_only: bool = True,
        chat_messages: Optional[list[LLMMessage]] = None,
        skills: Optional[list[SkillContent]] = None,
        skill_index: Optional[list[SkillIndexEntry]] = None,
    ) -> None
```

**Fields:**
- `max_parse_retries: int = 2` — Maximum additional LLM calls on JSON parse failure.

#### `ModelDecisionEngine.decide(context: dict) -> Decision`

**Pre-conditions:**
- `context` must contain key `'task'` (string).
- `context` may contain `'decision_summary'`, `'observations'`, `'memories'`, `'_cost_cents'`, `'_input_tokens'`, `'_output_tokens'`.

**Post-conditions:**
- Returns a `Decision` object (one of `FinalAnswer`, `ToolCall`, or other runner decision types).
- `context['_cost_cents']`, `context['_input_tokens']`, `context['_output_tokens']` are **incremented** (not replaced) on each LLM response.
- If all retries are exhausted and no fallback applies, returns `FinalAnswer` with content `'{"status":"error","action":"wait","reason":"invalid_model_decision_json"}'` and `metadata={'decision_fallback': 'invalid_model_decision_json'}`.

**Raises:** Any exception from `adapter.complete()` propagates unhandled (network errors, auth failures, etc.).

---

## Functions

---

### `run_chat_agent`

```python
# Preferred positional form
run_chat_agent(
    config: ChatAgentConfig,
    task: str,
    *,
    adapter: LLMAdapter | None = None,
    audit: Optional[AuditLogger] = None,
    registry: Optional[ToolRegistry] = None,
    task_spec: Optional[str] = None,
    depth: int = 0,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
) -> RunResult

# Deprecated keyword-only form (emits DeprecationWarning)
run_chat_agent(
    *,
    task: str,
    adapter: LLMAdapter,
    config: ChatAgentConfig,
    ...
) -> RunResult
```

**Pre-conditions:**
- `config` and `task` must both be provided.
- `adapter` is optional; if `None`, a default adapter is created from `config.model`.
- `depth` must be `>= 0`; typically `0` for top-level calls, incremented for subagent calls.
- If `config.skill_source_profile == 'custom'`, `config.skill_search_dirs` must be non-empty.

**Post-conditions:**
- Returns a `RunResult` with fields: `run_id`, `status`, `final_answer`, `iterations`, `tool_calls`, `cost_cents`, `input_tokens`, `output_tokens`, `error_message`, `metadata`.
- Heartbeat (if configured) is unconditionally stopped before returning.
- If status is `'completed'` and `final_answer` is non-None, an auto-curated memory entry may be written to `MemoryCatalog`.

**Raises:**
- `TypeError` if both `config` and `task` are missing.
- `ValueError` if `skill_source_profile='custom'` and `skill_search_dirs` is empty.

---

### `with_memories`

```python
def with_memories(context: dict, memories: list[dict]) -> dict
```

**Pre-conditions:** `context` is any dict; `memories` is a list (may be empty).

**Post-conditions:**
- If `memories` is empty, returns `context` unchanged (same object).
- If non-empty, returns a shallow copy of `context` with `context['memories'] = memories`.

---

### `register_subagent_tool`

```python
def register_subagent_tool(
    registry: ToolRegistry,
    *,
    adapter: LLMAdapter,
    config: ChatAgentConfig,
    depth: int,
) -> None
```

**Pre-conditions:** `depth >= 0`. `registry` must be a valid `ToolRegistry` instance.

**Post-conditions:** Subagent tools are registered on `registry`. If `config.code_analysis_config` is set, code analysis tools are also registered.

---

## Data Models

### `RunResult` (from `teaagent.runner._types`)

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Unique hex run identifier |
| `status` | `str` | `'completed'`, `'pending_approval'`, `'failed:model_logic'`, `'failed:permission'`, `'failed:system'`, `'failed:transient'` |
| `final_answer` | `Optional[FinalAnswer]` | Agent's final answer on success |
| `iterations` | `int` | Number of LLM calls made |
| `tool_calls` | `int` | Total tool invocations |
| `cost_cents` | `float` | Estimated cost in US cents |
| `input_tokens` | `int` | Total input tokens consumed |
| `output_tokens` | `int` | Total output tokens generated |
| `error_message` | `Optional[str]` | Error description on failure |
| `metadata` | `dict` | Arbitrary metadata from runner |

### `ChatAgentConfig.from_root()` — config file keys merged

| Config key | Maps to field |
|-----------|---------------|
| `permission_mode` | `permission_mode` |
| `max_iterations` | `max_iterations` |
| `max_tool_calls` | `max_tool_calls` |
| `model` | `model` |
| `code_analysis_enabled` | `code_analysis_config` |
| `git_tools_enabled` | `enable_git_tools` |
| `github_tools_enabled` | `enable_github_tools` |
| `skill_search_dirs` | `skill_search_dirs` |
| `skill_source_profile` | `skill_source_profile` |
