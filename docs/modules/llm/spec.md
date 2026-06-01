# llm — Behavior Specification

## Purpose

Provider-agnostic LLM abstraction layer. Normalizes Claude (Anthropic), OpenAI-compatible (OpenAI, OpenRouter, Groq, etc.), Gemini, Cloudflare Workers AI, and any other HTTP-based LLM provider behind a single `LLMAdapter.complete(request) -> LLMResponse` interface.

## Behavior Contract

1. **Single interface** — all adapters implement the `LLMAdapter` Protocol: `complete(LLMRequest) -> LLMResponse`.
2. **Retry on transient errors** — all adapters use `_call_with_retry` with a configurable `LLMRetryConfig`. Default: exponential backoff on 429 / 5xx.
3. **Streaming** — when `LLMRequest.stream=True`, responses are streamed via SSE. The `on_chunk` callback receives each text chunk incrementally.
4. **Tool calls** — tool call blocks are extracted from provider-specific response shapes and normalized into `LLMToolCall` dataclasses.
5. **Safety blocks** — Gemini safety blocks are surfaced via `LLMSafetyBlock` in `LLMResponse.safety`. Other providers return `None`.
6. **Cost estimation** — `LLMResponse.estimated_cost_cents` computes a best-effort cost using token counts and provider pricing from `_config.py`.
7. **Workers AI quirks** — `WorkersAIAdapter` strips `@cf/` model prefix for AI Gateway, removes `response_format` to avoid 500s, and can disable tools entirely.

## Supported Providers

| Provider | Adapter class | Protocol |
|----------|--------------|---------|
| `claude` | `ClaudeAdapter` | Anthropic Messages API |
| `openai`, `openrouter`, `groq`, etc. | `OpenAICompatibleAdapter` | OpenAI Chat Completions |
| `gemini` | `GeminiAdapter` | Gemini generateContent |
| `workers-ai` | `WorkersAIAdapter` | Cloudflare Workers AI (OAI-compat) |

## Data Flow

```
LLMRequest
  → adapter._prepare_payload()   [provider-specific JSON]
  → transport.post_json()        [HTTP POST]
  → _extract_*_content()         [text extraction]
  → _extract_*_tool_calls()      [tool call normalization]
  → LLMResponse
```

## Invariants

- `LLMResponse.content` is always a string (may be empty if only tool calls returned).
- `LLMResponse.tool_calls` is always a list (may be empty).
- `ProviderConfig.resolved_api_key()` raises `LLMConfigurationError` if env var not set.
- `ProviderConfig.resolved_model()` always returns a string (falls back to `default_model`).
