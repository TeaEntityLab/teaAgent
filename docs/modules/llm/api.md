# llm — Public API Reference

## Core Dataclasses (`_types.py`)

### `LLMMessage`
```python
@dataclass(frozen=True)
class LLMMessage:
    role: str     # 'user' | 'assistant' | 'system'
    content: str
```

### `LLMToolDefinition`
```python
@dataclass(frozen=True)
class LLMToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema object
```

### `LLMToolCall`
```python
@dataclass(frozen=True)
class LLMToolCall:
    tool_name: str
    tool_input: dict[str, Any]
    call_id: str = ''
```

### `LLMRequest`
```python
@dataclass(frozen=True)
class LLMRequest:
    messages: list[LLMMessage]
    model: Optional[str] = None          # overrides ProviderConfig.default_model
    system: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.2
    stream: bool = False
    on_chunk: Optional[Callable[[str], None]] = None  # streaming callback
    tools: list[LLMToolDefinition] = field(default_factory=list)
    response_format: Optional[dict[str, Any]] = None  # JSON schema for structured output
```

### `LLMResponse`
```python
@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str               # text response (may be empty if tool-only)
    raw: dict[str, Any]        # raw provider response
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    safety: Optional[LLMSafetyBlock] = None

    @property
    def estimated_cost_cents(self) -> float: ...
```

### `ProviderConfig`
```python
@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str           # e.g. 'ANTHROPIC_API_KEY'
    default_model: str
    base_url: str
    api_key: Optional[str] = None      # inline key (not recommended)
    model: Optional[str] = None
    base_url_env: Optional[str] = None

    def resolved_api_key(self) -> str       # raises LLMConfigurationError if missing
    def resolved_model(self) -> str         # checks {PREFIX}_MODEL env var
    def resolved_base_url(self) -> str      # resolves CLOUDFLARE_ACCOUNT_ID etc.
```

---

## Adapter Classes (`_adapters.py`)

### `ClaudeAdapter`
```python
ClaudeAdapter(
    config: ProviderConfig,
    *,
    transport: Optional[HTTPTransport] = None,
    timeout: int = 60,
    retry_config: Optional[LLMRetryConfig] = None,
    streaming_lines: Optional[list[bytes]] = None,  # test injection
)
```
`complete(request: LLMRequest) -> LLMResponse`
- POST to `{base_url}/messages` with `x-api-key` and `anthropic-version: 2023-06-01`
- Supports streaming via `content_block_delta` / `message_delta` SSE events

### `OpenAICompatibleAdapter`
```python
OpenAICompatibleAdapter(config, *, transport, timeout, retry_config, streaming_lines)
```
`complete(request: LLMRequest) -> LLMResponse`
- POST to `{base_url}/chat/completions`
- Falls back to dropping `response_format` on 4xx if provider doesn't support it

### `GeminiAdapter`
```python
GeminiAdapter(config, *, transport, timeout, retry_config, streaming_lines)
```
`complete(request: LLMRequest) -> LLMResponse`
- POST to `{base_url}/models/{model}:generateContent?key={api_key}`
- Populates `safety` field from `finishReason: SAFETY` candidates

### `WorkersAIAdapter(OpenAICompatibleAdapter)`
- Strips `@cf/` prefix for AI Gateway endpoints
- Removes `response_format` unless `TEAAGENT_WORKERS_AI_FORCE_JSON_OBJECT=1`
- `disable_tools=True` removes tools from payload

---

## Exceptions

| Exception | When raised |
|-----------|------------|
| `LLMConfigurationError` | Missing env var for API key/URL |
| `LLMHTTPError` | HTTP error from provider (has `.status_code`) |
| `LLMProviderError` | Provider returned `{"error": ...}` body |
| `LLMResponseFormatError` | Response doesn't contain expected content shape |

---

## Protocols

### `LLMAdapter`
```python
class LLMAdapter(Protocol):
    provider: str
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

### `HTTPTransport`
```python
class HTTPTransport(Protocol):
    def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], *, timeout: int
    ) -> dict[str, Any]: ...
```
