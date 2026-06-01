# context — Behavior Specification

## Purpose

Manages the agent's working memory within a single run: the conversation history, compacted summaries, pinned observations, and session state. Also provides a pub/sub context bus for cross-module communication.

## Behavior Contract

### `ContextCompactor` (`context.py`)
1. **Threshold-based** — compaction triggers when `token_count / max_tokens >= threshold_low` (default 0.75).
2. **Semantic summarization** — when `enable_semantic_compression=True`, summarizes old observations using LLM-style text compression.
3. **Pinned values** — memory keys in `context['memory_keys']` are preserved across compactions.
4. **Incremental** — each compaction appends to `compacted_summary` with "Then, ..." prefix.
5. **Compression ratio tracked** — `context['compression_ratio']` and `context['compaction_count']` are updated.

### `ContextBus` (`context_bus.py`)
1. **Pub/sub** — modules publish events; subscribers receive them synchronously.
2. **Decoupled** — modules don't need direct references to each other.

### `ContextPack` (`context_pack.py`)
1. **Serialization** — packages context for cross-agent transfer or persistence.
2. **Selective inclusion** — only serializes non-sensitive keys.

### `Session` (`session.py`)
1. **Session lifecycle** — tracks session ID, start time, user, run history.
2. **Persistence** — serialized to JSON in the run directory.

## State Machine (ContextCompactor)

```
[context dict]
  └── observations: list[str]  ← appended each iteration

should_compact(token_count, max_tokens)?
  └── YES if token_count/max_tokens >= 0.75

compact(context)
  ├── split observations: old[:-recent_observations], recent[-recent_observations:]
  ├── summarize(old) → summary string
  ├── context['observations'] = recent
  ├── context['compacted_summary'] += '\nThen, ' + summary
  └── context['compaction_count'] += 1
```

## Invariants

- `compaction_count` is monotonically increasing.
- `recent_observations` most recent items are always preserved.
- `memory_keys` are copied verbatim across compactions.
- Token estimation is approximate (3.5-4.0 chars/token); actual token count may differ.
