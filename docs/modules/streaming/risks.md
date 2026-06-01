# streaming — Risk Vectors & Known Issues

## R1: audit_event_to_stream_event returns None for unknown event types
**File**: `streaming/events.py:63-101`
**Risk**: Only a fixed set of `event_type` values produce `StreamEvent`. Any new event type added to the runner is silently dropped.
**Failure mode**: Consumers expecting all events only see a filtered subset.

## R2: emit_stream_event writes to stdout by default
**File**: `streaming/events.py:20-31`
**Risk**: `emit_stream_event` defaults to `sys.stdout`. If other code also writes to stdout (e.g., print statements), JSON stream is corrupted.
**Failure mode**: JSON parse errors in stream consumers.

## R3: No backpressure in `audit_sink_for_json_stream`
**File**: `streaming/events.py:125-133`
**Risk**: The sink calls `emit(mapped)` synchronously. If the consumer is slow (e.g., network), the audit-record thread is blocked on flush.
**Failure mode**: Slow consumers block agent progress.

## R4: content_filter.py — filter state is per-instance
**File**: `streaming/content_filter.py`
**Risk**: If a `ContentFilter` instance is shared across runs, state from the previous run may affect the next.
**Mitigation**: Create a fresh `ContentFilter` per run.

## R5: StreamEvent.to_dict spreads payload
**File**: `streaming/events.py:17`
**Risk**: `{'type': self.type, **self.payload}` — if `payload` has a `type` key, it overwrites the `type` field.
**Failure mode**: Event type appears wrong to consumers.
