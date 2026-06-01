# Profiling Guide
# teaagent — 2026-06-02

How to identify CPU, memory, and I/O bottlenecks in teaagent.

---

## 1. Built-in Performance Instrumentation

teaagent already measures elapsed time at several points using `time.perf_counter()`:

| Location | What is measured | How to access |
|----------|-----------------|--------------|
| `teaagent/benchmark.py` | Latency of operations in ms | `latency_ms = (time.perf_counter() - t0) * 1000` |
| `teaagent/swarm.py` | Swarm task execution time in ms | `execution_time = (time.perf_counter() - start_time) * 1000` |
| `teaagent/wasm_runtime.py` | WASM execution time in ms | Same pattern |
| Audit `tool_call_completed.duration_ms` | Per-tool-call latency | `audit.jsonl` |

For most performance questions, start by querying tool-call durations from the audit log before reaching for a profiler.

---

## 2. Quick Performance Triage (No Profiler Needed)

### Step 1 — Find the slow tool calls

```bash
# Sort tool calls by duration for a run
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
rows = []
for line in sys.stdin:
    e = json.loads(line)
    if e['event_type'] == 'tool_call_completed':
        p = e['payload']
        rows.append((p.get('duration_ms', 0), p.get('tool_name', '?')))
rows.sort(reverse=True)
for ms, name in rows:
    print(f'{ms:>8.1f} ms  {name}')
"
```

### Step 2 — Check run iteration count

```bash
# High iteration count = many LLM round-trips = slow and expensive
grep '"event_type": "run_completed"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    p = e['payload']
    print(f\"run={e['run_id'][:8]} iterations={p.get('iterations','?'):>4}  cost={p.get('cost_cents','?')} cents\")
" | sort -k2 -rn | head -20
```

### Step 3 — Identify which phase is slow

```bash
# Time from run_started to first tool_call_started = LLM initial response latency
# Time from tool_call_started to tool_call_completed = tool execution latency
# Time from last tool_call_completed to run_completed = final LLM response latency
python -c "
import json, sys
from datetime import datetime

events = []
run_id = 'YOUR_RUN_ID'
with open('/root/.teaagent/audit.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('run_id') == run_id:
            events.append(e)

events.sort(key=lambda e: e['created_at'])
prev = None
for e in events:
    ts = datetime.fromisoformat(e['created_at'].replace('Z','+00:00'))
    if prev:
        delta = (ts - prev).total_seconds() * 1000
        print(f'{delta:>8.0f} ms  {e[\"event_type\"]}')
    else:
        print(f'{\"\":>8}     {e[\"event_type\"]}')
    prev = ts
"
```

---

## 3. CPU Profiling with cProfile

teaagent does not ship with cProfile hooks. Add them with a wrapper.

### Profile a complete CLI invocation

```bash
python -m cProfile -o teaagent.prof -m teaagent.cli agent run "my task"

# Interactive analysis
python -m pstats teaagent.prof
# Inside pstats:
# sort cumulative
# stats 20
```

Or use `snakeviz` for a browser-based flame graph:

```bash
pip install snakeviz
python -m cProfile -o teaagent.prof -m teaagent.cli agent run "my task"
snakeviz teaagent.prof
```

### Profile a specific function

```python
import cProfile, pstats, io

pr = cProfile.Profile()
pr.enable()

# ... call the suspect function ...

pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
ps.print_stats(30)
print(s.getvalue())
```

---

## 4. Memory Profiling

teaagent does not yet include memory instrumentation. Use `tracemalloc` or `memray`.

### tracemalloc (no install required)

```python
import tracemalloc
tracemalloc.start()

# ... run suspect code ...

snapshot = tracemalloc.take_snapshot()
top = snapshot.statistics('lineno')
for stat in top[:20]:
    print(stat)
```

Wrap the CLI entry:

```python
# mem_profile_runner.py
import tracemalloc, sys, runpy
tracemalloc.start()
runpy.run_module("teaagent.cli", run_name="__main__", alter_sys=True)
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:20]:
    print(stat)
```

### memray (richer, requires install)

```bash
pip install memray
memray run -o output.bin python -m teaagent.cli agent run "my task"
memray flamegraph output.bin      # generates output.html
memray tree output.bin            # text tree
```

---

## 5. I/O Profiling

### Identify file I/O

```bash
# macOS
sudo fs_usage -e -f filesystem -p $(pgrep -f "teaagent") 2>/dev/null | head -50
```

### Identify slow DB queries (context_bus SQLite)

`context_bus.py` uses SQLite for RAG state and thread reconnection. Enable WAL checkpoint logging:

```python
import logging
logging.getLogger("teaagent.context_bus").setLevel(logging.DEBUG)
logging.getLogger("teaagent.schema_migration").setLevel(logging.DEBUG)
```

Look for "WAL checkpoint completion" DEBUG messages — frequent checkpoints indicate high write pressure.

### Identify LLM call latency

LLM calls are the dominant latency source. The `_transport.py` in `teaagent/telemetry/` wraps HTTP transport and can be instrumented. Each LLM round-trip appears as a gap between `tool_call_completed` and the next `tool_call_started` (or `run_completed`) in the audit log.

---

## 6. Context Profile Tuning

teaagent supports context profiles that trade token cost for speed:

| Profile | Token budget | When to use |
|---------|-------------|-------------|
| `lean` | Minimal context | Fastest, least accurate |
| `balanced` | Moderate context | Default |
| `rich` | Full context | Most accurate, slowest |

Profiles are defined in `teaagent/daily.py`. Switch via config to speed up slow runs with large codebases.

Similarly, validation profiles affect tool-call overhead:

| Validation profile | Overhead | When to use |
|-------------------|---------|-------------|
| `fast` | Minimal schema checks | Dev / debugging |
| `standard` | Default | Production |
| `strict` | Full validation | Security-sensitive runs |

---

## 7. Performance Debugging Decision Tree

```
teaagent is slow. Where is the time?
│
├─ Slow to start responding at all
│   └─ Check: initial LLM round-trip latency
│       → audit: gap between run_started and first tool_call_started
│       → try a smaller/faster model
│
├─ Slow during tool calls
│   └─ Check: tool_call duration_ms from audit.jsonl (Section 2 above)
│       ├─ I/O tools (file read/write) slow → check disk I/O, large files
│       ├─ context_bus/RAG tools slow → check SQLite WAL, enable DEBUG logging
│       └─ approval_manager slow → check approval prompt timeouts
│
├─ Many iterations for a simple task
│   └─ Check: run_completed.iterations > 10
│       → task description may be ambiguous → refine the task
│       → context profile 'rich' may be building too much context → switch to 'lean'
│
├─ High memory usage
│   └─ Use tracemalloc or memray (Section 4)
│       → common culprits: large context_pack objects, full file reads into RAM
│
└─ Slow only in TUI but not CLI
    └─ TUI bypasses ChatSessionController (DS-02) and runs a different code path
       → profile teaagent.cli.agent run separately to isolate
```
