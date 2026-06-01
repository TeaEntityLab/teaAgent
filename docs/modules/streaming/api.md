# streaming — Public API Reference

## `StreamEvent` (frozen dataclass)
**Location**: `streaming/events.py:12`

```python
@dataclass(frozen=True)
class StreamEvent:
    type: str              # e.g. 'tool_call_started', 'run_completed'
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        # Returns {'type': self.type, **self.payload}
```

---

## Free Functions (`streaming/events.py`)

### `emit_stream_event(event, *, out?) -> None`
```python
emit_stream_event(
    event: StreamEvent | dict[str, Any],
    *,
    out: TextIO | None = None,  # defaults to sys.stdout
) -> None
```
Serializes event to JSON (sort_keys=True) and prints with flush. One line per event.

### `audit_event_to_stream_event(event: AuditEvent) -> Optional[StreamEvent]`
Maps known `event_type` values to `StreamEvent`. Returns `None` for unknown types.

**Mapped event types:**

| `AuditEvent.event_type` | `StreamEvent.type` | Key payload fields |
|---|---|---|
| `iteration_started` | `iteration_started` | `iteration` |
| `tool_call_started` | `tool_call_started` | `tool_name`, `call_id` |
| `tool_call_completed` | `tool_call_completed` | `tool_name`, `call_id` |
| `tool_call_failed` | `tool_call_failed` | `tool_name`, `call_id`, `error` |
| `run_failed` | `run_failed` | `category`, `message` |
| `run_completed` | `run_completed` | `run_id` |
| `approval_required` | `approval_required` | (full payload) |

### `audit_dict_to_stream_event(raw: dict) -> Optional[StreamEvent]`
Same as above but takes raw dict from JSONL line instead of `AuditEvent`.

### `format_progress_line(event: AuditEvent) -> Optional[str]`
Returns a human-readable single-line progress string for stderr display.

### `audit_sink_for_json_stream(emit: Callable) -> Callable[[AuditEvent], None]`
Returns an `AuditLogger` sink that maps events to `StreamEvent` and calls `emit(mapped)`.

### `audit_sink_for_progress(stderr?) -> Callable[[AuditEvent], None]`
Returns an `AuditLogger` sink that writes human progress lines to stderr.

---

## `streaming/handlers.py` — Streaming Handler Chain
Handler classes that wrap `emit_stream_event` for different output modes (JSON stream, progress, hybrid). See `streaming/handlers.py` for `StreamHandler` and `ProgressHandler` classes.

## `streaming/content_filter.py` — Content Filter
`ContentFilter` — configurable filter for blocking specific event types or payload patterns before emission. Used for PII/secret scrubbing in streamed output.
