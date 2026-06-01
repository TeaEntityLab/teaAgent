# llm — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/llm/__init__.py` | Re-exports public symbols |
| `teaagent/llm/_types.py` | All dataclasses, protocols, exceptions |
| `teaagent/llm/_adapters.py` | `ClaudeAdapter`, `OpenAICompatibleAdapter`, `GeminiAdapter`, `WorkersAIAdapter` |
| `teaagent/llm/_config.py` | `ProviderConfig` registry, cost estimation |
| `teaagent/llm/_extract.py` | Content/delta extraction helpers per provider |
| `teaagent/llm/_retry.py` | `LLMRetryConfig`, `_call_with_retry` with exponential backoff |
| `teaagent/llm/_sse.py` | SSE/NDJSON stream parser (`consume_sse_json_chunks`) |
| `teaagent/llm/_transport.py` | `UrllibHTTPTransport` (stdlib-only HTTP), SSL context from env |

## Key Exports (`_types.py`)

### Exception hierarchy
```
LLMAdapterError (RuntimeError)
  ├── LLMConfigurationError  — bad config, missing env var
  ├── LLMHTTPError           — HTTP-level error (has .status_code)
  ├── LLMProviderError       — provider returned error JSON
  └── LLMResponseFormatError — unexpected response shape
```

### Core dataclasses
- `LLMMessage(role, content)` — frozen
- `LLMToolDefinition(name, description, input_schema)` — frozen
- `LLMToolCall(tool_name, tool_input, call_id='')` — frozen
- `LLMSafetyBlock(blocked, category?, detail='')` — frozen
- `LLMRequest(messages, model?, system?, max_tokens, temperature, stream, on_chunk?, tools, response_format?)` — frozen
- `LLMResponse(provider, model, content, raw, input_tokens, output_tokens, tool_calls, safety?)` — frozen; has `estimated_cost_cents` property
- `ProviderConfig(name, api_key_env, default_model, base_url, ...)` — frozen; `resolved_api_key()`, `resolved_model()`, `resolved_base_url()`

### Protocols
- `HTTPTransport` — `post_json(url, headers, payload, *, timeout) -> dict`
- `LLMAdapter` — `complete(request: LLMRequest) -> LLMResponse`

## Dependencies

```
llm/_adapters.py
  ├── teaagent.llm._extract
  ├── teaagent.llm._retry
  ├── teaagent.llm._sse
  ├── teaagent.llm._transport
  └── teaagent.llm._types

llm/_types.py
  └── (lazy) teaagent.llm._config  [estimated_cost_cents property]

All adapters use stdlib urllib only — no requests/httpx dependency.
```

## Entry Points

1. `runner/_core.py` — constructs adapter from `ProviderConfig`, calls `adapter.complete(request)` in agent loop
2. `chat_agent.py` — uses adapter for chat completions
3. `intent.py` — uses adapter for intent classification

## Call Graph

```
runner._core: agent iteration
  adapter.complete(LLMRequest)
    ├── _prepare_payload(request, model)
    ├── transport.post_json(url, headers, payload, timeout)
    │     └── UrllibHTTPTransport: urllib.request.urlopen
    ├── _extract_*_content(response)
    ├── _extract_*_tool_calls(response)
    └── LLMResponse(...)

[streaming path]
  adapter._complete_streaming(request, model, payload)
    └── consume_sse_json_chunks(iter_lines, on_data)
          └── on_data(chunk) → request.on_chunk(text)
```
