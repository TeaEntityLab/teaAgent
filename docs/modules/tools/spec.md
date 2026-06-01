# tools — Behavior Specification

## Purpose

Central tool registry for all agent-callable tools. Manages registration, schema validation, rate limiting, security tier classification, and hook-mediated execution. `ToolRegistry` is the single source of truth for what tools an agent can call.

## Behavior Contract

1. **Schema-validated dispatch** — every tool call validates input against `input_schema` (JSON Schema) before invoking the handler.
2. **Hook interception** — if a `HookRegistry` is attached, `run_pre_hooks` fires before handler and `run_post_hooks` fires after. `HookError` aborts the call before the handler runs.
3. **Rate limiting** — tools with a `ToolRateLimit` are tracked in a sliding-window counter. Exceeding `max_calls` within `window_seconds` raises `ToolExecutionError`.
4. **Security tier** — each tool has a security tier (`Low`, `Medium`, `High`, `Critical`) derived from `ToolAnnotations` or `capability_manifest`. The approval manager uses this tier.
5. **Thread safety** — `ToolRegistry._call_counts` is protected by a per-tool lock.
6. **Idempotency annotation** — `ToolAnnotations.idempotent=True` is purely declarative; the registry does not deduplicate calls.

## Tool Lifecycle

```
tool call request (tool_name, arguments)
  │
  ├── validate tool_name exists → ToolExecutionError if not
  ├── validate input_schema → ToolValidationError if invalid
  ├── check rate limit → ToolExecutionError if exceeded
  ├── run_pre_hooks(tool_name, arguments) → may raise HookError or modify args
  ├── handler(arguments) → dict[str, Any]
  └── run_post_hooks(tool_name, arguments, result) → may modify result
```

## Invariants

- A registered tool's `name` is globally unique within a registry instance.
- `input_schema` must be a valid JSON Schema object (`type: object`).
- `handler` must return a `dict[str, Any]`.
- `ToolAnnotations.destructive=True` implies security tier `High` unless overridden by `capability_manifest`.
