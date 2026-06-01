# context — Risk Vectors & Known Issues

## R1: Token estimation is inaccurate
**File**: `context.py:38-45`
**Risk**: `estimate_tokens` uses 3.5-4.0 chars/token approximation. For code-heavy context (more symbols), actual token count may be 20-30% higher. This means `should_compact` may trigger too late, causing context overflow.
**Failure mode**: LLM context window overflow → API error.

> **See also:** [budget/risks.md](../budget/risks.md) — cost estimation limits

## R2: Semantic summarization is heuristic-only
**File**: `context.py:60-65`
**Risk**: `_semantic_summarize` likely uses simple text truncation or local summarization, not an LLM call. For complex multi-step agent histories, the summary may lose critical state.
**Failure mode**: Agent "forgets" earlier decisions after compaction.

## R3: `compacted_summary` grows unboundedly
**File**: `context.py:73-77`
**Risk**: Each compaction appends "Then, ..." to `compacted_summary`. If compaction happens many times, the summary itself becomes large and consumes significant context budget.
**Failure mode**: Summary eventually needs compaction; no mechanism for this.

## R4: Context dict is mutable and unguarded
**File**: `context.py` — `compact()` returns a new dict, but callers may hold references to the old dict.
**Risk**: If a module holds a reference to the pre-compaction context dict, it sees stale observations.
**Failure mode**: Stale data in downstream modules.

## R5: ContextBus subscriptions are not cleaned up
**File**: `context_bus.py`
**Risk**: If a subscriber object is destroyed without calling `unsubscribe`, the bus holds a dangling reference. In long-running sessions, this is a memory leak.

## R6: Session `save()` not atomic
**File**: `session.py`
**Risk**: `session.save()` writes the JSON file directly without a temp-file + rename pattern. On crash mid-write, the session file is corrupted.
**Failure mode**: Session recovery fails; run history lost.
