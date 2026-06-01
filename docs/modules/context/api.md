# context — Public API Reference

## `CompactionResult` (frozen dataclass)
**Location**: `context.py`

```python
@dataclass(frozen=True)
class CompactionResult:
    context: dict[str, Any]    # compacted context dict
    summary: str               # text summary of compacted observations
    pinned: dict[str, Any]     # preserved memory keys
    tokens_saved: int          # estimated tokens removed
    compression_ratio: float   # summary_tokens / saved_tokens
```

---

## `ContextCompactor` (dataclass)
**Location**: `context.py:17`

```python
@dataclass
class ContextCompactor:
    recent_observations: int = 3         # how many recent observations to keep
    memory_keys: tuple[str, ...] = ()    # keys pinned across compactions
    threshold_low: float = 0.75          # trigger compaction above this usage ratio
    threshold_high: float = 0.92         # emergency compaction threshold
    enable_semantic_compression: bool = True
    max_summary_length: int = 500
```

### `should_compact(token_count: int, max_tokens: int = 200000) -> bool`
Returns `True` if `token_count / max_tokens >= threshold_low`.

### `estimate_tokens(text: str) -> int`
Approximates token count: 3.5 chars/token for text, 4.0 for code-heavy content.

### `compact(context: dict[str, Any]) -> CompactionResult`
- **Pre**: `context` contains `'observations': list[str]`.
- **Post**: Returns new context with `observations` truncated to `recent_observations`, `compacted_summary` updated, `compaction_count` incremented.
- Does not modify the passed-in `context` dict (returns a copy).

---

## `ContextBus`
**Location**: `context_bus.py`

```python
class ContextBus:
    def publish(self, event_type: str, data: dict[str, Any]) -> None
    def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None
    def unsubscribe(self, event_type: str, handler: Callable) -> None
    def clear(self) -> None  # removes all subscriptions
```

---

## `Session`
**Location**: `session.py`

```python
class Session:
    session_id: str
    started_at: str    # ISO 8601
    run_ids: list[str]
    user: Optional[str]

    @classmethod
    def new(cls, user: Optional[str] = None) -> 'Session': ...
    @classmethod
    def load(cls, path: Path) -> 'Session': ...
    def save(self, path: Path) -> None: ...
    def add_run(self, run_id: str) -> None: ...
```

---

## Context Dict Schema (runtime)

The agent context is a plain `dict[str, Any]` with conventional keys:

| Key | Type | Description |
|-----|------|-------------|
| `observations` | `list[str]` | LLM outputs and tool results (compacted over time) |
| `compacted_summary` | `str` | Accumulated summary of compacted observations |
| `compaction_count` | `int` | Number of times compaction has occurred |
| `compression_ratio` | `float` | Latest compaction ratio |
| `memory_keys` | `dict[str, Any]` | Pinned key-value pairs across compactions |
| `plan_contract` | `dict` | Bound plan for write gate (see governance) |
| `project_instructions` | `str` | Loaded CLAUDE.md/AGENTS.md content |
| `run_id` | `str` | Current run UUID |
