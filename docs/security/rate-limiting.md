# LLM Provider Rate Limiting

TeaAgent supports sliding-window rate limiting for LLM provider API calls to prevent runaway cost and API abuse.

## Architecture

Rate limits are enforced by `TokenRateLimiter` (`teaagent/http_rate_limit.py`) — a per-key sliding-window counter — applied at the adapter transport layer before every HTTP request.

### Covered Adapters

- `OpenAICompatibleAdapter` — GPT, OpenRouter, Mistral, DeepSeek, Grok, etc.
- `ClaudeAdapter` — Anthropic Claude
- `GeminiAdapter` — Google Gemini
- `WorkersAIAdapter` — Cloudflare Workers AI / AI Gateway

When a rate limit is exceeded, the adapter raises `LLMHTTPError` with status code 429 before any HTTP request is made.

## Configuration

Rate limits are configured in `.teaagent/config.json` under the `rate_limits` key:

```json
{
  "rate_limits": {
    "enabled": true,
    "default": {
      "max_calls": 100,
      "window_seconds": 60
    }
  }
}
```

### Schema

| Key | Type | Default | Description |
|------|------|---------|-------------|
| `rate_limits.enabled` | bool | `false` | Master toggle |
| `rate_limits.default.max_calls` | int | `100` | Max calls in window |
| `rate_limits.default.window_seconds` | float | `60` | Sliding window duration |

### Loading Rate Limits

```python
from teaagent.llm._config import load_llm_rate_limiter, create_llm_adapter

limiter = load_llm_rate_limiter(workspace_root='.')
if limiter:
    adapter = create_llm_adapter('gpt', rate_limiter=limiter)
```

If no rate limiter is configured or `enabled` is `false`, `load_llm_rate_limiter` returns `None` and no rate limit is applied.

## Behavior

- **Sliding window**: Calls are counted within the configured window; each call slides the window forward.
- **Thread-safe**: `TokenRateLimiter` uses `threading.Lock` for concurrent access.
- **Provider-level**: All calls from a single provider share the same quota. Multiple adapters for the same provider count against the same limit.
- **Non-blocking**: When the limit is hit, the call fails immediately with an error — there is no queuing or backpressure.

## Best Practices

- Set conservative limits during initial evaluation (e.g., 10 calls/60s).
- Increase limits for batch/production workloads after establishing baseline usage.
- Monitor rate limit errors via audit log events.
- Consider per-provider limits if using multiple providers with different cost profiles.
