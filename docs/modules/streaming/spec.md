# Streaming Module — Behavior Contract & Spec

## Overview

The streaming module handles three distinct concerns:

1. **SSE parsing** (`llm/_sse.py`) — parses raw Server-Sent Events HTTP stream lines into JSON payloads
2. **Event mapping** (`streaming/events.py`) — translates internal `AuditEvent` objects into external `StreamEvent` objects for CLI consumers
3. **Content filtering** (`streaming/content_filter.py`) — extracts only user-visible text from partial decision JSON blobs
4. **Handler wiring** (`streaming/handlers.py`) — connects CLI arguments to the appropriate stream pipeline (JSON stream vs. plain progress vs. text-only)

---

## Behavior Contract

### `iter_sse_data_lines` / `consume_sse_json_chunks` (`llm/_sse.py`)

- **Guarantees**: `iter_sse_data_lines` yields only the data payload of `data: <payload>` lines. It stops iteration immediately when `data: [DONE]` is encountered.
- **Guarantees**: `consume_sse_json_chunks` always calls `lines.close()` in its `finally` block if the iterator has a `close` method — even if JSON parsing fails on individual lines.
- **Silently skips**: Lines that cannot be parsed as JSON are skipped without raising.
- **Encoding**: Bytes lines are decoded as UTF-8 with `errors='replace'`. Non-decodable bytes produce replacement characters, not exceptions.

### `StreamEvent` (`streaming/events.py`)

- **Guarantees**: `StreamEvent.to_dict()` always returns a dict with at least a `type` key equal to `StreamEvent.type`.
- **Immutable**: `StreamEvent` is a `frozen=True` dataclass.

### `audit_event_to_stream_event` (`streaming/events.py`)

- **Guarantees**: Returns `None` for any `AuditEvent.event_type` that is not in the handled set: `iteration_started`, `tool_call_started`, `tool_call_completed`, `tool_call_failed`, `run_failed`, `run_completed`, `approval_required`.
- **No side effects**: Pure function; reads from `event.payload` and returns a new `StreamEvent` or `None`.

### `emit_stream_event` (`streaming/events.py`)

- **Guarantees**: Every call produces exactly one newline-terminated JSON line to `out` (default `sys.stdout`). Output is flushed after each write.
- **Guarantees**: Output is JSON-serialized with `ensure_ascii=False` and keys sorted alphabetically.

### `DecisionContentStreamer` (`streaming/content_filter.py`)

- **Guarantees**: Only emits text that was not already emitted. The `_emitted` counter tracks characters forwarded to `_sink`. Each `feed()` call emits at most the delta between newly decoded characters and previously emitted characters.
- **Precondition for emission**: The streamer does not call `_sink` until it has seen both a `"type": "final"` marker and a `"content": "` key marker in the accumulated buffer.
- **Monotonic forwarding**: `_emitted` only ever increases; content is never re-sent.
- **Partial JSON handling**: The internal JSON string decoder (`_decode_json_string_prefix`) handles escape sequences (`\n`, `\t`, `\r`, `\"`, `\\`) and stops at an unescaped closing `"`. It tolerates truncated escape sequences at end of buffer.

### `build_run_stream_handlers` (`streaming/handlers.py`)

- **Guarantees**: Always returns a `RunStreamHandlers` instance; never raises.
- **Routing logic**:
  - `json_stream=True, stream=True, stream_text_only=True` → JSON events on stdout + `DecisionContentStreamer` fed `text_delta` events
  - `json_stream=True, stream=True, stream_text_only=False` → JSON events + raw chunk stdout
  - `json_stream=True, stream=False` → JSON events only (no chunk handler)
  - `json_stream=False, stream=True, stream_text_only=True` → plain text filtered through `DecisionContentStreamer`
  - `json_stream=False, stream=True, stream_text_only=False` → raw text directly to stdout
  - `json_stream=False, stream=False` → progress only (if enabled), no text chunks

---

## Invariants

1. `DecisionContentStreamer._emitted` never decreases.
2. `DecisionContentStreamer._buffer` only grows until the first `feed()` that locates `_content_start`; after that point, the buffer still grows (new feed appends), but only characters after `_content_start` are re-decoded.
3. `emit_stream_event` always writes valid JSON per call.
4. `iter_sse_data_lines` terminates when `[DONE]` is seen; callers must not rely on the generator continuing after that.
5. `audit_event_to_stream_event` is stable: the same `AuditEvent` always maps to the same `StreamEvent` (or `None`).

---

## State Machines

### DecisionContentStreamer internal state

```
[INITIAL]
    │  feed(chunk): _FINAL_TYPE_RE not found in buffer
    │  (keep buffering)
    ▼
[WAITING_FOR_FINAL_TYPE]
    │  _FINAL_TYPE_RE found in buffer
    │  + _CONTENT_KEY_RE found → _content_start set
    ▼
[STREAMING]
    │  feed(chunk): decode buffer from _content_start
    │  emit delta to _sink if decoded len > _emitted
    └──► (loops back to STREAMING for each subsequent feed)
```

### build_run_stream_handlers routing

```
args.json_stream ?
  ├── YES:
  │     progress enabled? → audit.add_sink(audit_sink_for_json_stream(emit))
  │     args.stream?
  │       ├── YES + stream_text_only → on_chunk = DecisionContentStreamer(text_sink).feed
  │       └── YES + raw             → on_chunk = text_sink (direct)
  └── NO:
        progress enabled? → audit.add_sink(audit_sink_for_progress())
        args.stream?
          ├── YES + stream_text_only → on_chunk = DecisionContentStreamer(text_stdout).feed
          └── YES + raw             → on_chunk = text_stdout
```
