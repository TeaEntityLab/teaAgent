# Python API Specification

**Package:** `teaagent`  
**Status:** Public classes/functions documented here are stable. Names prefixed `_` are internal and may change without notice.

---

## `teaagent.tui` — TUI Entry Point

### `TeaAgentTUI`

Top-level class for the interactive terminal UI.

```python
class TeaAgentTUI:
    def __init__(
        self,
        database: str = ':memory:',
        provider: Optional[str] = None,
        model: Optional[str] = None,
        root: Union[str, Path] = '.',
        allow_destructive: bool = False,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        input_fn: Callable[..., str] = input,
        output_fn: Callable[..., None] = print,
        adapter_factory: Optional[Callable] = None,
        initial_task: Optional[str] = None,
        session_id: Optional[str] = None,
        progress: bool = False,
        stream: bool = False,
        subagent: bool = False,
        route_model: bool = False,
        heartbeat: int = 0,
    ) -> None: ...

    def run_repl(self) -> int:
        """
        Start the interactive REPL loop. Blocks until the user exits.

        Returns:
            int: Exit code. 0 = clean exit, non-zero = error.
        """

    def _save_tui_state(self) -> None:
        """Persist current session state to .teaagent/tui_state.json."""

    def _handle_tui_command(self, raw_command: str) -> bool:
        """
        Dispatch a raw REPL command string.

        Args:
            raw_command: The full text entered at the prompt.

        Returns:
            bool: True if the command was handled, False if unrecognised.
        """
```

**Pre-conditions:**
- `root` must be a readable directory.
- `provider`, if set, must be in `teaagent.llm.available_providers()`.

**Post-conditions:**
- `run_repl()` always returns; it never raises.

---

## `teaagent.policy` — Permission & Approval

### `PermissionMode`

```python
class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'
```

---

### `ApprovalPolicy`

Immutable policy object. Constructed once per run; shared across tool calls.

```python
@dataclass(frozen=True)
class ApprovalPolicy:
    # Deprecated/inert compatibility field for removed call-ID preapproval.
    preapproved_call_ids: frozenset[str]
    # Active pre-run payload approval: digest of tool name + arguments.
    preapproved_payload_digests: frozenset[str]
    allow_all_destructive: bool
    permission_mode: PermissionMode
    approval_store: Optional[ApprovalPresetStore]
    approval_origin_run_id: Optional[str]
    enable_jit_prompt: bool
    multi_sig_config: MultiSigQuorumConfig
    agent_id: str
    workspace_root: str
    def assert_allowed(
        self,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any],
    ) -> None:
        """
        Assert that a tool call is permitted under this policy.

        Raises:
            ApprovalDeniedError: If the call is not allowed.
        """
```

---

### `JITApprovalState`

Mutable just-in-time approval state for a single session.

```python
@dataclass
class JITApprovalState:
    approved_call_ids: set[str]
    session_approved_tools: set[str]

    def approve_once(self, call_id: str) -> None:
        """Approve one in-flight call ID via JIT/session state."""

    def approve_session(self, tool_name: str) -> None:
        """Approve all calls to a tool for the current session."""

    def is_call_approved(self, call_id: str) -> bool:
        """Return True if this in-flight call ID has a live JIT/session approval."""
```

---

### `MultiSigQuorumConfig`

Configuration for multi-signature quorum approval.

```python
@dataclass(frozen=True)
class MultiSigQuorumConfig:
    enabled: bool
    required_approvals: int
    peer_agent_ids: list[str]
    peer_public_keys: dict[str, str]    # agent_id → SSH public key
    peer_relay_urls: dict[str, str]     # agent_id → relay URL
    local_relay_base_url: Optional[str]
    allow_dev_signatures: bool
    high_risk_patterns: list[str]       # glob patterns for high-risk tools
    timeout_seconds: int
```

---

### `PeerSignature`

```python
@dataclass(frozen=True)
class PeerSignature:
    peer_id: str
    signature: str          # base64-encoded signature
    timestamp: float        # Unix timestamp
    ssh_key_id: Optional[str]
```

---

## `teaagent.tools` — Tool Registry

### `ToolAnnotations`

```python
@dataclass(frozen=True)
class ToolAnnotations:
    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    stateful: bool = False
    security_tier: str = 'Medium'  # Low | Medium | High | Critical
```

---

### `ToolRateLimit`

```python
@dataclass(frozen=True)
class ToolRateLimit:
    max_calls: int
    window_seconds: float = 60.0
```

---

### `ToolDefinition`

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]    # JSON Schema object
    output_schema: dict[str, Any]   # JSON Schema object
    annotations: ToolAnnotations
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    rate_limit: Optional[ToolRateLimit]
    capability_manifest: Optional[dict[str, Any]]

    def get_security_tier(self) -> str:
        """Return the security tier string from annotations."""
```

---

### `ToolRegistry`

Central registry for all tools. Typically accessed as a module-level singleton.

```python
class ToolRegistry:
    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        annotations: ToolAnnotations,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        rate_limit: Optional[ToolRateLimit] = None,
        capability_manifest: Optional[dict[str, Any]] = None,
        allow_override: bool = False,
    ) -> None:
        """
        Register a tool.

        Args:
            name: Unique tool name. Raises ValueError if already registered
                  and allow_override is False.
            description: Human-readable description for the model.
            input_schema: JSON Schema for the tool's arguments.
            output_schema: JSON Schema for the tool's return value.
            annotations: Security and behaviour annotations.
            handler: Callable invoked with the validated arguments dict.
            rate_limit: Optional per-tool rate limit.
            allow_override: If True, silently replaces an existing registration.

        Raises:
            ValueError: Duplicate name and allow_override is False.
            SchemaValidationError: input_schema or output_schema is invalid JSON Schema.
        """

    def lookup(self, name: str) -> Optional[ToolDefinition]:
        """Return the ToolDefinition for name, or None if not registered."""

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tools in registration order."""

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Invoke a tool by name.

        Args:
            tool_name: Registered tool name.
            arguments: Arguments dict, validated against input_schema.

        Returns:
            dict validated against output_schema.

        Raises:
            ToolNotFoundError: tool_name not registered.
            SchemaValidationError: arguments fail input_schema validation.
            ToolRateLimitError: Rate limit exceeded.
            Any exception raised by the handler.
        """
```

---

## `teaagent.audit` — Audit Logging

### `AuditEvent`

```python
@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    payload: dict[str, Any]
    event_id: str               # UUID hex
    created_at: str             # ISO 8601

    def to_json(
        self,
        prev_hash: Optional[str],
        event_hash: Optional[str],
        chain_hmac: Optional[str],
    ) -> str:
        """Serialise to a JSON string including chain fields."""
```

**Event types:**

| Event Type | Description |
|-----------|-------------|
| `run_start` | Agent run began |
| `run_end` | Agent run completed |
| `tool_call` | Tool invoked |
| `tool_result` | Tool returned a result |
| `tool_error` | Tool raised an exception |
| `approval_request` | Approval prompt triggered |
| `approval_granted` | Call approved |
| `approval_denied` | Call denied |
| `model_request` | LLM request sent |
| `model_response` | LLM response received |
| `cost_checkpoint` | Intermediate cost recorded |
| `iteration_limit` | Iteration limit hit |
| `tool_call_limit` | Tool call limit hit |
| `validation_result` | Post-run validation result |

---

### `AuditLogger`

```python
class AuditLogger:
    def __init__(
        self,
        path: Union[str, Path],
        redaction_config: Optional[dict] = None,
        audit_level: str = 'L2',
    ) -> None:
        """
        Args:
            path: File path for the JSONL audit log.
            redaction_config: Dict mapping field names to redaction rules.
            audit_level: 'L0' (metrics only) | 'L1' (metadata) |
                         'L2' (redacted payloads) | 'L3' (full).
        """

    def log(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Append an audit event.

        Thread-safe. Events are appended atomically. If a disk error occurs,
        it is recorded in self.disk_error but not raised — callers must
        poll disk_error if they need to detect failures.
        """

    @property
    def events(self) -> list[AuditEvent]:
        """In-memory list of events logged in this session."""

    @property
    def disk_error(self) -> Optional[OSError]:
        """Last OS error encountered writing to disk, or None."""

    def get_chain_key(self) -> bytes:
        """Return the HMAC key used for chain integrity."""
```

---

## `teaagent.session` — Chat Sessions

### `ChatMessage`

```python
@dataclass(frozen=True)
class ChatMessage:
    role: str       # 'user' | 'assistant' | 'system'
    content: str
```

---

### `ChatSession`

```python
@dataclass
class ChatSession:
    id: str
    created_at: str         # ISO 8601
    updated_at: str         # ISO 8601
    messages: list[ChatMessage]
    label: str
    focus_stack: FocusStackManager
```

---

### `SessionStore`

```python
class SessionStore:
    def save(self, session: ChatSession) -> None:
        """
        Persist session to .teaagent/sessions/<id>.json.

        Creates the file if it doesn't exist; overwrites if it does.
        """

    def load(self, session_id: str) -> Optional[ChatSession]:
        """
        Load a session by ID.

        Returns:
            ChatSession if found, None otherwise.
        """

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all saved sessions as lightweight dicts.

        Returns:
            list of {'id', 'created_at', 'updated_at', 'label', 'message_count'} dicts,
            sorted by updated_at descending.
        """
```

---

## `teaagent.llm` — LLM Adapters

### Provider Config

```python
@dataclass
class ProviderConfig:
    name: str
    api_key_env: str        # Environment variable name for the API key
    default_model: str
    base_url: str
    base_url_env: str       # Environment variable to override base URL

# Module-level constant
PROVIDER_CONFIGS: dict[str, ProviderConfig]

# Cost tables (dollars per 1,000 tokens)
PROVIDER_COST_PER_1K_INPUT: dict[str, float]
PROVIDER_COST_PER_1K_OUTPUT: dict[str, float]
```

---

### `LLMMessage`

```python
@dataclass
class LLMMessage:
    role: str       # 'user' | 'assistant' | 'system'
    content: str
```

---

### `LLMRequest`

```python
@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    model: str
    max_tokens: Optional[int] = None
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[str] = None
    temperature: float = 0.0
```

---

### `LLMToolCall`

```python
@dataclass
class LLMToolCall:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
```

---

### `LLMResponse`

```python
@dataclass
class LLMResponse:
    content: str
    stop_reason: str        # 'end_turn' | 'tool_use' | 'max_tokens'
    tool_calls: list[LLMToolCall]
    input_tokens: int
    output_tokens: int
    cost_cents: float
```

---

### `LLMAdapter` (Abstract Base)

```python
class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[str]: ...
```

---

### Module-Level Functions

```python
def available_providers() -> list[str]:
    """Return names of all configured providers."""

def create_llm_adapter(
    provider: str,
    model: Optional[str] = None,
) -> LLMAdapter:
    """
    Instantiate an adapter for the given provider.

    Args:
        provider: Provider name (must be in available_providers()).
        model: Model override. If None, uses ProviderConfig.default_model.

    Raises:
        ValueError: Unknown provider.
        MissingAPIKeyError: Required environment variable not set.
    """

def estimate_cost_preflight(
    provider: str,
    model: str,
    prompt_tokens: int,
    max_output_tokens: int,
) -> dict[str, float]:
    """
    Estimate cost before making a call.

    Returns:
        {'input_cost_cents': float, 'max_output_cost_cents': float,
         'total_max_cents': float}
    """
```

---

## `teaagent.runner._types` — Run Types

### `ToolRequest`

```python
@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str
    reasoning: Optional[str]    # Model's reasoning for the call
```

---

### `FinalAnswer`

```python
@dataclass(frozen=True)
class FinalAnswer:
    content: str
    metadata: dict[str, Any]
```

---

### `ApprovalRequest`

```python
@dataclass(frozen=True)
class ApprovalRequest:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    annotations: dict[str, bool]
    run_id: Optional[str]
    workspace_secret: Optional[bytes]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON encoding."""
```

---

### `RunResult`

```python
@dataclass(frozen=True)
class RunResult:
    run_id: str
    final_answer: Optional[FinalAnswer]
    iterations: int
    tool_calls: int
    status: str     # 'completed' | 'failed' | 'approval_denied' |
                    # 'limit_exceeded' | 'cost_exceeded'
    metadata: dict[str, Any]
    error_message: Optional[str]
    cost_cents: float
    input_tokens: int
    output_tokens: int
```

---

## `teaagent.budget` — Run Budget

### `RunBudget`

```python
@dataclass(frozen=True)
class RunBudget:
    max_iterations: int = 25
    max_tool_calls: int = 25
    max_estimated_cost_cents: int | None = 500
```

Hard limits enforced by `AgentRunner` on every iteration. When any limit is
exceeded a `BudgetExceededError` is raised and the run fails.

**`max_estimated_cost_cents` semantics (as of 2026-06-05):**

| Value | Meaning |
|-------|---------|
| `None` | Unlimited — no cost check is performed |
| `0` | Zero spend allowed — any positive cost raises `BudgetExceededError` immediately |
| `N > 0` | Hard cap at N cents; exceeding it raises `BudgetExceededError` |

The default (`500`) gives a $5.00 hard cap per run.

**Test evidence:** `test_budget_zero_cents_rejects_any_spend`,
`test_budget_none_allows_unlimited`, `test_budget_default_500_cents`,
`test_zero_cost_cap_blocks_positive_cost_run`.

**Pre-conditions:**
- `max_iterations >= 1`
- `max_tool_calls >= 0`
- `max_estimated_cost_cents is None or max_estimated_cost_cents >= 0`

**`validate()`** raises `ValueError` if any pre-condition is violated.

**`check_cost_preflight(provider, model, approx_input_chars, max_output_tokens)`**
estimates the cost of a single LLM call before dispatching it. Raises
`BudgetExceededError` when the estimate exceeds the cap. No-op when
`max_estimated_cost_cents is None` or when the estimated cost is `0` and the
cap is `0`.

---

## `teaagent.cost_tracker` — Cost Reporting

### `CostTracker`

```python
class CostTracker:
    def __init__(self, root: Union[str, Path] = '.') -> None:
        """
        Args:
            root: Workspace root. Scans .teaagent/runs/*.jsonl for cost data.
        """

    def get_summary_by_label(self) -> dict[str, dict[str, float]]:
        """
        Returns:
            {'label': {'cost_cents': float, 'runs': int, 'input_tokens': int,
                       'output_tokens': int}}
        """

    def get_summary_by_model(self) -> dict[str, dict[str, float]]:
        """Aggregate cost grouped by model name."""

    def get_summary_by_day(self) -> dict[str, dict[str, float]]:
        """
        Aggregate cost grouped by calendar day.

        Returns:
            {'YYYY-MM-DD': {'cost_cents': float, 'runs': int}}
        """
```

---

## `teaagent.mcp_server` — MCP Server Internals

### `WorkspaceLock`

```python
@dataclass
class WorkspaceLock:
    workspace_path: str
    owner_pid: int
    acquired_at: str        # ISO 8601
```

---

### `WorkspaceRegistry`

```python
class WorkspaceRegistry:
    def acquire_lock(self, workspace_path: str) -> WorkspaceLock:
        """
        Acquire a workspace lock.

        Performs zombie cleanup: if the lock is held by a dead PID, it is
        automatically released before acquiring.

        Raises:
            WorkspaceLockConflictError: Another live process holds the lock.
        """

    def release_lock(self, workspace_path: str) -> None:
        """Release the lock for workspace_path. No-op if not locked."""
```

---

## Exceptions

| Exception | Module | Description |
|-----------|--------|-------------|
| `ApprovalDeniedError` | `teaagent.policy` | Tool call blocked by approval policy |
| `ToolNotFoundError` | `teaagent.tools` | Tool name not registered |
| `ToolRateLimitError` | `teaagent.tools` | Rate limit exceeded |
| `SchemaValidationError` | `teaagent.tools` | JSON Schema validation failed |
| `MissingAPIKeyError` | `teaagent.llm` | Required API key env var not set |
| `WorkspaceLockConflictError` | `teaagent.mcp_server` | Workspace already locked by another process |
| `RunLimitError` | `teaagent.runner` | Iteration or tool-call limit exceeded |
| `CostCapError` | `teaagent.runner` | Estimated cost exceeds cap |
