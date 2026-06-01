# llm — Risk Vectors & Known Issues

## R1: API keys logged in debug output
**File**: `_adapters.py:276`
**Risk**: `self._headers()` returns `{'authorization': f'Bearer {api_key}'}`. If this dict is logged anywhere (e.g., debug dump of HTTP headers), the API key leaks.
**Mitigation**: Headers dict never enters audit payload. Keep it out of logging.

## R2: Streaming silently truncates on SSE parse error
**File**: `_sse.py`, `_adapters.py:244-274`
**Risk**: `consume_sse_json_chunks` ignores lines that aren't valid JSON. If the provider sends a partial line, that chunk is silently dropped.
**Failure mode**: Incomplete streaming response; no error raised.

## R3: LLMResponse.content is empty string when only tool calls returned
**File**: `_adapters.py:181-195`
**Risk**: Claude may return only `tool_use` blocks with no text. `_extract_claude_content` raises `LLMResponseFormatError`. The adapter catches this only if `tool_calls` is non-empty, then falls back to JSON-encoding the first tool call as `content`.
**Failure mode**: If `tool_calls` is also empty, `LLMResponseFormatError` propagates to the runner. The runner must handle it.

## R4: Workers AI strips response_format without telling the LLM
**File**: `_adapters.py:319-346`
**Risk**: `WorkersAIAdapter` removes `response_format` from the payload and instead appends a prompt instruction. If the model ignores the instruction, the response is not valid JSON, but the caller expects structured output.
**Failure mode**: JSON parse error downstream in the runner.

## R5: Cost estimation is stale
**File**: `_config.py`
**Risk**: Provider pricing is hardcoded and will drift as providers change rates.
**Failure mode**: `estimated_cost_cents` is directionally wrong, causing incorrect budget enforcement.

## R6: Retry on 401/403 wastes quota
**File**: `_retry.py`
**Risk**: If `DEFAULT_RETRY_CONFIG` retries on all 4xx errors, a 401 (invalid API key) or 403 (quota exceeded) will be retried N times, wasting time and potentially burning remaining credits.
**Mitigation**: Verify that `_call_with_retry` only retries 429 + 5xx (audit the retry predicate in `_retry.py`).

## R7: urllib has no connection pooling
**File**: `_transport.py`
**Risk**: `UrllibHTTPTransport.post_json` opens a new TCP connection per call. High-frequency short completions cause connection overhead.
**Failure mode**: Latency, file descriptor exhaustion at high concurrency.

## R8: No timeout on streaming
**File**: `_adapters.py:215-239`
**Risk**: `_iter_streaming_lines` passes `timeout=self.timeout` but `urllib.request.urlopen` timeout applies to the initial connection only, not to individual chunk reads. A stalled stream hangs forever.
