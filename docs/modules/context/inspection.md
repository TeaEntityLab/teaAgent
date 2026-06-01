# context — Module Inspection

## Source Files

| File | Role |
|------|------|
| `teaagent/context.py` | `ContextCompactor`, `CompactionResult` |
| `teaagent/context_bus.py` | `ContextBus` — pub/sub event bus |
| `teaagent/context_pack.py` | `ContextPack` — serialization/transfer |
| `teaagent/session.py` | `Session` — session lifecycle and persistence |
| `teaagent/scratchpad.py` | `Scratchpad` — ephemeral working memory |

## Key Exports

### `context.py`
- `CompactionResult` — frozen dataclass: `context`, `summary`, `pinned`, `tokens_saved`, `compression_ratio`
- `ContextCompactor` — dataclass with `should_compact()`, `estimate_tokens()`, `compact()` methods

### `context_bus.py`
- `ContextBus` — `publish(event_type, data)`, `subscribe(event_type, handler)`, `unsubscribe()`

### `session.py`
- `Session` — `session_id`, `started_at`, `run_ids`, `user`, `save()`, `load(path)`

### `scratchpad.py`
- `Scratchpad` — ephemeral key-value store, cleared between runs

## Dependencies

```
context.py
  └── stdlib: dataclasses

context_bus.py
  └── stdlib: typing, threading

session.py
  └── stdlib: json, pathlib, uuid, datetime
```

## Entry Points

1. `runner/_core.py` — creates and maintains the agent context dict; calls `compactor.compact()` when needed
2. `chat_agent.py` — builds context from chat history
3. `subagents/_manager.py` — creates sub-contexts for subagent runs

## Call Graph

```
runner._core.AgentRunner
  ├── context = {}  # plain dict
  ├── compactor = ContextCompactor(...)
  └── per iteration:
        context['observations'].append(llm_output)
        if compactor.should_compact(token_count, max_tokens):
          result = compactor.compact(context)
          context = result.context
```
