# Provider Authoring Guide

LLM providers implement the `LLMAdapter` protocol:

```python
class LLMAdapter(Protocol):
    provider: str
    def complete(self, request: LLMRequest) -> LLMResponse: ...
```

## Steps

1. Add a `ProviderConfig` entry to `PROVIDER_CONFIGS` in `teaagent/llm.py`.
2. Implement an adapter class or reuse `OpenAICompatibleAdapter`.
3. Validate response shape strictly. Missing content must raise `LLMResponseFormatError`, not return an empty string.
4. Classify provider-side blocks and errors as `LLMProviderError`.
5. Use `LLMRetryConfig` for transient HTTP failures.
6. Add unit tests for request payload, headers, malformed responses, and provider errors.
7. Run `teaagent model conformance --provider <provider>` before using the provider in agent runs.

## Required Behavior

- Respect `LLMRequest.system` when the provider supports system prompts.
- Respect `max_tokens` and `temperature` where supported.
- Populate `input_tokens` and `output_tokens` when the provider reports usage.
- Preserve the raw provider response in `LLMResponse.raw` for debugging.

## Conformance Levels

- `smoke`: provider returns non-empty content.
- `contract`: exact content, system-prompt adherence, and token-budget reporting.
- Future tiers: streaming, structured output, tool calling, latency budgets, safety/block taxonomy.
