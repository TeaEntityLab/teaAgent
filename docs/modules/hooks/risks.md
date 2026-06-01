# hooks — Risk Vectors & Known Issues

## R1: Hook registration race
**File**: `hooks.py:99-120`
**Risk**: `HookRegistry.register_*` methods append directly to the list without a lock. If hooks are registered from multiple threads after the agent loop starts, list corruption is possible.
**Failure mode**: Missing hooks, IndexError, or double execution.
**Mitigation**: Register all hooks before starting the agent loop. Add a `threading.Lock` if dynamic registration is needed.

## R2: HookError must be caught by caller
**File**: `hooks.py:43`
**Risk**: `HookError` is raised inside `run_pre_hooks`. If the caller (`runner._core`) does not catch it, the entire agent run crashes rather than cleanly aborting the single tool call.
**Failure mode**: Uncaught exception terminates agent run.
**Current behavior**: `runner._core` wraps in `try/except HookError` — safe. But any custom runner that omits this catch is at risk.

## R3: PostToolUse hook can return None to "keep original" — but runs_tests_hook raises HookError
**File**: `hooks.py:259-283`
**Risk**: `run_tests_hook` is registered as a `PostToolUseHookFn` but raises `HookError`, which is defined as a PreToolUse veto mechanism. PostToolUse hooks raising `HookError` are not documented as valid.
**Failure mode**: If a caller only catches `HookError` in the pre-hook path, a post-hook test failure may propagate uncaught.

## R4: shell_command_hook timeout fixed at 30s
**File**: `hooks.py:348`
**Risk**: `shell_command_hook` uses `timeout=30` hardcoded. A slow test suite or linter will hit `subprocess.TimeoutExpired`, which is not caught — it propagates as an unhandled exception.
**Failure mode**: Hook raises `TimeoutExpired`, uncaught, crashing the runner.

## R5: lint_check_hook name confusion
**File**: `hooks.py:190-207`
**Risk**: `lint_check_hook` is documented as a post-hook but its name suggests pre-check. It is a direct alias for `post_lint_check_hook`.
**Failure mode**: Confusion for users registering it as a pre-hook.

## R6: mcp_sampling_hook mutates arguments dict
**File**: `hooks.py:488-495`
**Risk**: `mcp_sampling_hook` calls `arguments.setdefault(...)` which mutates the passed-in dict. If the dict is re-used by caller, this adds `_sampling` key permanently.
**Failure mode**: Unexpected `_sampling` field in tool arguments visible to the tool handler.

## Known Limitations
- No built-in rate limiting or circuit breaker for hook failures.
- `context_file_loader_hook` does a synchronous file read at `SessionStart`; large CLAUDE.md files block the event loop.
- No way to unregister hooks at runtime once registered.
