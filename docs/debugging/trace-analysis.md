# Trace Analysis
# teaagent — 2026-06-02

How to follow a single request, run, or session end-to-end through logs, audit events, and spans.

---

## 1. The Three Tracing Surfaces

| Surface | Granularity | Location | Best for |
|---------|-------------|----------|---------|
| Audit events (`audit.jsonl`) | Per-run, per-tool-call | `~/.teaagent/audit.jsonl` | Run lifecycle, cost, approvals |
| Python `logging` | Per-code-path | stderr / log file | Why a code branch was taken |
| `TraceRecorder` spans | Per-run + per-tool-call | In-process memory | Span timing, nested tool calls |
| W3C traceparent | Cross-agent delegation | A2A headers | Agent-to-agent chains |

---

## 2. Finding Your Run ID

Every investigation starts here. `run_id` is the primary correlation key.

```bash
# List recent runs
teaagent agent list

# List with timestamps and status
teaagent agent list --format json | python -m json.tool

# Show a specific run's events
teaagent agent show <run_id>
teaagent agent show <run_id> --format json
```

The `run_id` is also printed to stderr at run start when log level is INFO or DEBUG:

```
2026-06-02T14:23:01Z INFO  teaagent.coordinator  run started run_id=a3f9c12b-...
```

---

## 3. Tracing a Single Run Through audit.jsonl

`~/.teaagent/audit.jsonl` is append-only. Every event for every run is in one file.

```bash
# All events for one run, chronologically
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"

# Just event types (fast summary)
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "import sys,json; [print(json.loads(l)['event_type']) for l in sys.stdin]"
```

### What a normal run looks like

```
run_started           ← task accepted, model + permission_mode recorded
tool_call_started     ← tool invoked (call_id links to completion)
tool_call_completed   ←    result returned, duration_ms recorded
tool_call_started     ← (more tool calls...)
tool_call_completed
run_completed         ← iterations, cost_cents, result_summary
```

### What a failed run looks like

```
run_started
tool_call_started
tool_call_completed
run_failed            ← error field, cost_cents (spend up to failure point)
```

### What a suspended session looks like

```
session_suspended     ← NOT run_started/run_completed — this is the REPL path
                         payload: run_id, observations_count, suspension_file
```

Note: `teaagent resume <id>` will error on this because `agent_resume_command` looks for `run_started`, not `session_suspended`. See DS-08 in [Bug Catalog](bug-catalog.md).

---

## 4. Tracing a Tool Call

Tool calls have their own correlation via `call_id`.

```bash
# Get all tool_call events for a run
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if 'tool_call' in e['event_type']:
        print(f\"{e['event_type']:30s} {e['payload'].get('tool_name',''):20s} {e['payload'].get('call_id','')} \")
"

# Timing for all tool calls in a run
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if e['event_type'] == 'tool_call_completed':
        p = e['payload']
        print(f\"{p.get('tool_name',''):20s} {p.get('duration_ms','?'):>8} ms  {p.get('status','')}\")
"
```

---

## 5. Tracing Approval Decisions

```bash
# All approval events
grep '"event_type": "approval' ~/.teaagent/audit.jsonl | python -m json.tool

# Approvals for one run
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "import sys,json; [print(l.strip()) for l in sys.stdin if 'approval' in l]"
```

Look for `approval_requested` → `approval_granted` or `approval_denied` pairs. If a `requested` has no following `granted`/`denied`, the prompt was interrupted.

Watch for the DS-12 pattern: `approval_granted` with `"path_scope": ""` or `"path_scope": null` — this is an accidental global grant.

---

## 6. Tracing Across the TUI / REPL Code Paths

The TUI and REPL are on **different execution paths** (DS-02). To identify which path a run used:

```bash
# From audit.jsonl — check if run_started appears (agent/REPL runs) or session_suspended (REPL background)
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "import sys,json; [print(json.loads(l)['event_type']) for l in sys.stdin]" | sort -u
```

If you see `run_started` + `run_completed/run_failed` — this was a full agent run (REPL or agent CLI).
If you see only `session_suspended` — this was a REPL background suspension; no `run_started` exists.

TUI runs currently go through `run_chat_agent` directly (`tui/__init__.py:890`), bypassing `ChatSessionController`. Their audit events look the same from the outside, but the in-process state (cost accumulator, undo journal) is handled by the TUI's own code rather than the controller.

---

## 7. Tracing A2A (Agent-to-Agent) Delegation

When a parent agent delegates to a sub-agent, a W3C traceparent is generated:

```python
# teaagent/a2a_trace.py
tp = generate_traceparent()   # '00-{32hex trace_id}-{16hex parent_id}-01'
```

The `trace_id` is the same across the entire delegation chain. The `parent_id` changes at each hop.

```bash
# Extract traceparent from run attributes
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    tp = e.get('payload', {}).get('traceparent') or e.get('attributes', {}).get('traceparent')
    if tp:
        print('traceparent:', tp)
        parts = tp.split('-')
        print('  trace_id:', parts[1])
        print('  parent_id:', parts[2])
"

# Search all sub-agent logs for the same trace_id
TRACE_ID=4bf92f3577b34da6a3ce929d0e0e4736
grep "$TRACE_ID" ~/.teaagent/audit.jsonl | python -m json.tool
```

---

## 8. In-Process Span Inspection

`TraceRecorder` accumulates spans in memory during a run. To inspect them at the end of a run in a script or test:

```python
from teaagent.trace import TraceRecorder
from teaagent.audit import AuditBus

recorder = TraceRecorder()
bus = AuditBus()
bus.add_sink(recorder)

# ... run agent ...

for span in recorder.spans:
    print(f"{span.name:20s} {span.run_id} {span.started_at} → {span.ended_at}")
    print(f"  attributes: {span.attributes}")
```

Spans with `ended_at=None` are open (tool call started but not yet completed — indicates a hang).

---

## 9. Trace Analysis Decision Tree

```
I need to trace something. Start here:
│
├─ "What happened in run X?"
│   └─ grep run_id from audit.jsonl → read event_type sequence
│
├─ "Why did tool Y fail / behave oddly?"
│   └─ grep call_id from tool_call_started → check tool_call_completed.status and duration_ms
│       └─ if no tool_call_completed → tool call hung or process crashed mid-run
│
├─ "Why was my approval granted too broadly?"
│   └─ grep approval_granted for run_id → check path_scope field
│       └─ if path_scope is "" or null → DS-12 empty-path grant (see bug-catalog.md)
│
├─ "My suspended session won't resume"
│   └─ grep run_id from audit.jsonl → look for session_suspended (not run_started)
│       └─ agent resume expects run_started → this is DS-08, use interactive-review instead
│
├─ "Did the sub-agent continue from where the parent left off?"
│   └─ extract traceparent.trace_id from parent run → grep all logs for that trace_id
│
└─ "There's a gap in the audit trail — an event I expected is missing"
    └─ Check chat_session_controller.py:143-159 for the bare except (DS-03)
        if the missing event is run_completed → the save was swallowed silently
```
