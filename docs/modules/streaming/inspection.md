# Streaming Module — Inspection

## Purpose

Converts raw SSE HTTP streams and internal audit events into externally consumable outputs:
- Machine-readable JSON event stream (for programmatic consumers, CI, TUI)
- Human-readable progress on stderr (for interactive CLI sessions)
- Filtered text-only streaming of LLM decision content to stdout (for `--stream` mode)

---

## Files and Responsibilities

| File | Key Exports | Responsibility |
|---|---|---|
| `teaagent/llm/_sse.py` | `iter_sse_data_lines`, `consume_sse_json_chunks` | Parse raw SSE bytes/lines; yield JSON payloads |
| `teaagent/streaming/__init__.py` | Re-exports all public symbols | Package facade |
| `teaagent/streaming/events.py` | `StreamEvent`, `emit_stream_event`, `audit_event_to_stream_event`, `audit_dict_to_stream_event` | AuditEvent → StreamEvent translation + emission |
| `teaagent/streaming/content_filter.py` | `DecisionContentStreamer` | Partial JSON streaming parser for decision content |
| `teaagent/streaming/handlers.py` | `RunStreamHandlers`, `build_run_stream_handlers`, `adapter_supports_streaming` | Wire CLI args → stream pipeline |

---

## Dependencies

### `llm/_sse.py`
- `json`, `collections.abc` (stdlib only)
- No teaagent imports

### `streaming/events.py`
- `teaagent.audit.AuditEvent` — source event type
- `json`, `sys`, `dataclasses` (stdlib)

### `streaming/content_filter.py`
- `re`, `collections.abc` (stdlib only)
- No teaagent imports

### `streaming/handlers.py`
- `teaagent.audit.AuditLogger` — for registering audit sinks
- `teaagent.streaming.content_filter.DecisionContentStreamer`
- `teaagent.streaming.events` (all event utilities)
- `argparse`, `sys`, `dataclasses` (stdlib)

### `streaming/__init__.py`
- Re-exports from `content_filter`, `events`, `handlers`

---

## Exported Symbols

### `streaming/__init__.py` (`__all__`)
- `DecisionContentStreamer`
- `StreamEvent`
- `audit_dict_to_stream_event`
- `audit_event_to_stream_event`
- `build_run_stream_handlers`
- `emit_stream_event`

### Additional symbols in sub-modules (not in `__all__` but public)
- `streaming/events.py`: `format_progress_line`, `audit_sink_for_json_stream`, `audit_sink_for_progress`
- `streaming/handlers.py`: `RunStreamHandlers`, `adapter_supports_streaming`
- `llm/_sse.py`: `iter_sse_data_lines`, `consume_sse_json_chunks`

---

## Entry Points

| Entry Point | Called By |
|---|---|
| `build_run_stream_handlers(args, audit)` | CLI agent run command handlers |
| `consume_sse_json_chunks(lines, on_data=...)` | LLM adapters (OpenAI, Claude, Gemini) when consuming SSE responses |
| `emit_stream_event(event)` | JSON stream mode CLI output path |
| `audit_sink_for_json_stream(emit)` | Registered as an `AuditLogger` sink in JSON stream mode |
| `audit_sink_for_progress(stderr)` | Registered as an `AuditLogger` sink in progress mode |

---

## Call Graph

```
build_run_stream_handlers(args, audit)
  ├── audit.add_sink(audit_sink_for_json_stream(emit))    [json_stream + progress]
  ├── audit.add_sink(audit_sink_for_progress())           [non-json + progress]
  ├── DecisionContentStreamer(text_sink).feed             [stream + text_only]
  └── returns RunStreamHandlers(stream, on_chunk, stream_text_only)

audit_sink_for_json_stream(emit) → Callable[[AuditEvent], None]
  └── audit_event_to_stream_event(event) → StreamEvent | None
        └── emit(stream_event)
              └── emit_stream_event(event)

audit_sink_for_progress(stderr) → Callable[[AuditEvent], None]
  └── format_progress_line(event) → str | None
        └── audit_event_to_stream_event(event)

DecisionContentStreamer.feed(chunk)
  └── _decode_json_string_prefix(raw) → (text, consumed)
        └── _sink(delta)

consume_sse_json_chunks(lines, on_data=callback)
  └── iter_sse_data_lines(lines) → Iterator[str]
        └── json.loads(data_line) → dict
              └── on_data(parsed_dict)

audit_dict_to_stream_event(raw_dict) → StreamEvent | None
  └── AuditEvent(event_type, run_id, payload)
        └── audit_event_to_stream_event(event)
```

---

## AuditEvent to StreamEvent Mapping

| `AuditEvent.event_type` | `StreamEvent.type` | Payload fields |
|---|---|---|
| `iteration_started` | `iteration_started` | `iteration` |
| `tool_call_started` | `tool_call_started` | `tool_name`, `call_id` |
| `tool_call_completed` | `tool_call_completed` | `tool_name`, `call_id` |
| `tool_call_failed` | `tool_call_failed` | `tool_name`, `call_id`, `error` |
| `run_failed` | `run_failed` | `category`, `message` |
| `run_completed` | `run_completed` | `run_id` |
| `approval_required` | `approval_required` | (full payload dict) |
| _anything else_ | — | `None` returned |
