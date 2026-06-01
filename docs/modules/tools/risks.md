# tools — Risk Vectors & Known Issues

## TOOL-R-001: No output schema validation
**File**: `tools.py:50-79`
**Risk**: `ToolDefinition.output_schema` exists but `ToolRegistry.call()` does not validate the handler's return value against it.
**Failure mode**: A buggy handler returns unexpected structure; downstream LLM parsing fails silently.

## TOOL-R-002: Rate limit uses wall-clock time, not monotonic
**File**: `tools.py` (rate limit implementation)
**Risk**: If the system clock jumps backward (NTP correction), calls made before the jump fall outside the window and the counter resets incorrectly.

## TOOL-R-003: HookError from post-hook is not caught
**File**: `tools.py` dispatch path
**Risk**: `PostToolUseHookFn` raising `HookError` (valid for `run_tests_hook`) propagates out of `call()` as-is. Callers expect only `ToolExecutionError` / `ToolValidationError`.
**Failure mode**: Uncaught `HookError` crashes the agent loop.

## TOOL-R-004: Handler exceptions are not wrapped
**File**: `tools.py`
**Risk**: If a tool handler raises an arbitrary exception, it propagates unmodified from `ToolRegistry.call()`. The runner must wrap it; if it doesn't, the agent loop crashes.

## TOOL-R-005: `ToolAnnotations.destructive=True` + `read_only=True` returns 'Critical'
**File**: `tools.py:64-76`
**Risk**: Contradictory annotation (`destructive=True, read_only=True`) resolves to `Critical` tier. A developer typo could accidentally elevate a safe tool to Critical, requiring unnecessary approval.
