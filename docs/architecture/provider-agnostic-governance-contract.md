# Provider-Agnostic Governance Contract

**Status:** Implemented (W11, 2026-06-11)
**Owner:** governance layer / `teaagent/llm/`

---

## Purpose

Every provider adapter must populate a `GovernanceMetadata` object on each `LLMResponse`. This ensures the runner can enforce cost budgets, detect refusals, and audit tool-call provenance without branching on provider-specific response shapes.

The contract guarantees:

1. Unknown values are **explicitly marked**, never silently zero or absent.
2. Estimated cost is **never treated as actual cost**.
3. Budget enforcement skips calls where cost is `UNKNOWN` rather than treating them as free.

---

## GovernanceMetadata Fields

All fields are required. Adapters that cannot supply a value must use the explicit sentinel listed below.

| Field | Type | Sentinel for unknown | Description |
|---|---|---|---|
| `provider_id` | `str` | — | Provider name, matches `LLMResponse.provider` |
| `model_id` | `str` | — | Resolved model name used for the call |
| `input_tokens` | `int` | `0` | Prompt tokens; check `tokens_known` before using |
| `output_tokens` | `int` | `0` | Completion tokens; check `tokens_known` before using |
| `tokens_known` | `bool` | `False` | `True` only when the provider reported token counts |
| `estimated_cost_cents` | `float` | `0.0` | Cost in cents; `0.0` when `cost_source == UNKNOWN` |
| `cost_source` | `CostSource` | `CostSource.UNKNOWN` | Whether cost is estimated or unknown |
| `actual_cost_cents` | `Optional[float]` | `None` | Reserved; `None` until a provider reports actual billing |
| `tool_call_format` | `ToolCallFormat` | `ToolCallFormat.NONE` | Wire format of tool calls in the raw response |
| `refusal_class` | `RefusalClass` | `RefusalClass.NONE` | Normalized reason the provider declined (or NONE) |
| `streaming_supported` | `bool` | `False` | Whether this adapter class supports streaming |

---

## Enum Values

### `CostSource`

| Value | Meaning |
|---|---|
| `ESTIMATED` | Cost computed from token counts × provider rate table |
| `UNKNOWN` | Provider gave no token counts; cost cannot be estimated |

### `RefusalClass`

| Value | Trigger |
|---|---|
| `NONE` | Normal response, no refusal |
| `SAFETY_BLOCK` | Provider safety filter blocked content (e.g., Gemini `finishReason=SAFETY`) |
| `CONTENT_FILTER` | Provider content policy filter (e.g., OpenAI `finish_reason=content_filter`) |
| `RATE_LIMIT` | Provider rate limit hit (HTTP 429); adapter raises `LLMHTTPError` before response |
| `CONTEXT_LENGTH` | Input exceeded context window |
| `AUTH_ERROR` | API key / authentication failure |
| `PROVIDER_ERROR` | Provider 5xx / internal error |
| `UNKNOWN` | Non-None refusal whose class cannot be determined |

> **Note:** `RATE_LIMIT`, `AUTH_ERROR`, and `PROVIDER_ERROR` typically cause exceptions before an `LLMResponse` is returned. `RefusalClass` values in a returned response are `NONE`, `SAFETY_BLOCK`, or `CONTENT_FILTER` in practice.

### `ToolCallFormat`

| Value | Provider |
|---|---|
| `ANTHROPIC` | Claude — tool calls in `content[].type == "tool_use"` blocks |
| `OPENAI` | OpenAI / OpenAI-compatible — tool calls in `message.tool_calls` |
| `GEMINI` | Gemini — tool calls in `candidates[].content.parts[].functionCall` |
| `NORMALIZED` | Already converted to `LLMToolCall` list (auto-fill path) |
| `NONE` | Response contains no tool calls |

---

## Contract Per Adapter

| Adapter | `tool_call_format` | `streaming_supported` | `tokens_known` source | `refusal_class` source |
|---|---|---|---|---|
| `ClaudeAdapter` | `ANTHROPIC` / `NONE` | `True` | `usage.input_tokens` present | Always `NONE` on returned response |
| `OpenAICompatibleAdapter` | `OPENAI` / `NONE` | `True` | `usage.prompt_tokens` present | `choices[0].finish_reason == content_filter` |
| `WorkersAIAdapter` (extends OpenAI) | `OPENAI` / `NONE` | `True` | inherited | inherited |
| `GeminiAdapter` | `GEMINI` / `NONE` | `True` | `usageMetadata` present | `LLMSafetyBlock.blocked == True` |
| `FakeLLMAdapter` | `NONE` | `False` | `input_tokens > 0` in scripted response | `NONE` |

**Providers covered by `OpenAICompatibleAdapter`:** `gpt`, `openrouter`, `ollama`, `vllm`, `deepseek`, `mistral`, `grok`, `opencodezen`, `workers-ai` (via `WorkersAIAdapter`), `aigateway`.

---

## Budget Enforcement Rule

`CostSource.UNKNOWN` cost **must not** be added to the running budget total.

```python
# chat_agent.py — cost accumulation guard
g = response.governance
assert g is not None
if g.cost_source != CostSource.UNKNOWN:
    self.usage.cost_cents += float(response.estimated_cost_cents)
```

Rationale: a provider that reports no token counts (e.g., a local Ollama model) would silently appear "free" and allow unlimited runs without this guard.

---

## Backward Compatibility

`LLMResponse.governance` is populated automatically via `__post_init__` when an adapter (or test) constructs `LLMResponse` without passing `governance=`. The auto-fill uses:

- `tokens_known = input_tokens > 0 or output_tokens > 0`
- `cost_source = ESTIMATED if tokens_known else UNKNOWN`
- `tool_call_format = NORMALIZED`
- `refusal_class = NONE`
- `streaming_supported = False`

All existing code that constructs `LLMResponse(provider=..., model=..., ...)` continues to work. Adapters that explicitly pass `governance=` override the auto-fill with accurate provider-specific metadata.

---

## Adding a New Adapter

1. Implement `complete(request: LLMRequest) -> LLMResponse`.
2. Call `_build_governance(...)` with:
   - `tokens_known=bool(usage_dict)` — False if the API response had no usage section
   - `refusal_class` — extract from provider-specific finish reason
   - `tool_call_format` — the provider's wire format
   - `streaming_supported` — `True` if the class implements `_complete_streaming`
3. Pass the result as `governance=` in the `LLMResponse(...)` constructor.
4. Do **not** set `actual_cost_cents` — it is `None` until a provider exposes billing APIs.

---

## Tests

`tests/test_governance_contract.py` verifies:

- All `GovernanceMetadata` fields exist and the struct is frozen.
- `LLMResponse.__post_init__` auto-fills governance from token counts.
- `CostSource.UNKNOWN` → `estimated_cost_cents == 0.0`, `actual_cost_cents is None`.
- `_openai_refusal_class` and `_gemini_refusal_class` helpers classify correctly.
- `_build_governance` sets `CostSource.ESTIMATED` / `UNKNOWN` correctly.
- `FakeLLMAdapter` responses carry governance.
- `OpenAICompatibleAdapter` and `ClaudeAdapter` set `tokens_known`, `tool_call_format`, `streaming_supported`.
- `GeminiAdapter` sets `tokens_known` based on `usageMetadata` presence.
- `UNKNOWN` cost does not accumulate in the simulated budget guard.
