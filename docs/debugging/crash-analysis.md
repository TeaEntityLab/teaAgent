# Crash Analysis
# teaagent — 2026-06-02

Post-mortem debugging: finding what went wrong after a crash, hang, or silent failure.

---

## 1. Crash vs. Silent Failure

teaagent has two distinct failure modes:

| Type | How it presents | Where to look |
|------|----------------|--------------|
| **Crash** (exception propagates) | Python traceback in stderr; process exits non-zero | stderr / log file |
| **Silent failure** | Process exits 0, or continues running, but result is wrong | audit.jsonl gaps; missing events |

Most of teaagent's known bugs (DS-01, DS-02, DS-05, DS-09, DS-11) are silent failures. See [Bug Catalog](bug-catalog.md) for per-defect detail.

---

## 2. Immediate Steps After Any Crash

```bash
# 1. Capture the run_id (if you have one)
teaagent agent list --format json | python -m json.tool | head -40

# 2. Check the last events in audit.jsonl
tail -50 ~/.teaagent/audit.jsonl | python -m json.tool

# 3. Check for suspension files (if REPL was in use)
ls -lt ~/.teaagent/suspension-*.json 2>/dev/null | head -10

# 4. Check git status before doing anything that might affect state
git status
git stash list

# 5. Replay the run's audit trail
teaagent agent show <run_id> 2>/dev/null || grep '"run_id": "<run_id>"' ~/.teaagent/audit.jsonl
```

---

## 3. Reading Python Tracebacks

teaagent crashes produce standard Python tracebacks. Key things to look for:

### Common crash patterns

**JSON decode error in audit chain**

```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
  File "teaagent/audit_chain.py", line ...
```

Cause: partial write to `audit.jsonl` (process killed mid-write). Fix: truncate the last malformed line.

```bash
# Find and remove the last partial line
python -c "
import sys
with open('/root/.teaagent/audit.jsonl') as f:
    lines = f.readlines()
good = []
for line in lines:
    try:
        import json; json.loads(line); good.append(line)
    except Exception:
        print('Skipping bad line:', line[:80])
with open('/root/.teaagent/audit.jsonl', 'w') as f:
    f.writelines(good)
"
```

**AttributeError / TypeError swallowed by controller**

If a run appears to succeed (no traceback) but the undo journal or run store has no record of it, the error was silently caught at `chat_session_controller.py:143-159`. Enable DEBUG and watch for any exception that would normally surface.

```python
# Temporary diagnostic: patch the bare except to log
# chat_session_controller.py:143-159
try:
    store.logger_for_result(result)
    undo_journal.save_to(result)
except (AttributeError, TypeError) as exc:
    import logging
    logging.getLogger(__name__).error("SILENT_CATCH: %s", exc, exc_info=True)  # add this
```

**OSError on approval or file write**

```
OSError: [Errno 13] Permission denied: '/path/to/file'
  File "teaagent/approval/ui.py", line ...
```

Check file permissions and whether the target path is inside the workspace.

**RuntimeError in approval_manager**

```
RuntimeError: approval_manager is not running
  File "teaagent/approval/manager.py", line ...
```

Means `approval_manager` was not started before a tool call needed it. Typically a startup ordering issue in tests or CLI handlers.

---

## 4. Analyzing a Hung Process

If `teaagent` is running but producing no output:

```bash
# Find the PID
pgrep -f "teaagent"

# Show Python stack for a running process (no debugger needed)
python -c "import os, signal; os.kill(PID, signal.SIGUSR1)"  # may not be enabled
# or:
kill -SIGTERM PID   # see if it gracefully shuts down

# Get a Python stack trace with py-spy (install separately)
pip install py-spy
sudo py-spy dump --pid PID
```

### Common hang causes

| Symptom | Likely cause | Where to look |
|---------|-------------|--------------|
| Hangs at approval prompt | No terminal attached, or TUI lost focus | Kill and use `--permission-mode auto-approve` for debugging |
| Hangs after tool call | Tool call waiting for external process (e.g., WASM runtime) | Check `teaagent.wasm_runtime` DEBUG logs |
| Hangs at DB operation | SQLite locked by another process | `lsof ~/.teaagent/*.db` |
| Hangs in consensus | Federated sync waiting for a quorum | Check `teaagent.federated_sync` WARNING logs |

---

## 5. Post-Mortem: "The Run Disappeared"

A run that is not in `teaagent agent list` and not in `audit.jsonl`.

### Flowchart

```
Run is missing from the audit log.
│
├─ Was the process killed mid-run?
│   └─ Check: is the last line of audit.jsonl a run_started with no matching run_completed?
│       grep '"event_type": "run_started"' ~/.teaagent/audit.jsonl | tail -5
│       grep '"event_type": "run_completed\|run_failed"' ~/.teaagent/audit.jsonl | tail -5
│       → If started > completed: process died between start and finish
│
├─ Was it a TUI run?
│   └─ Check: TUI runs DO produce audit events; if missing, check if audit sink was registered
│       → Enable INFO logging and look for "audit sink" messages at startup
│
├─ Did the store save throw silently?
│   └─ Check: DS-03 — chat_session_controller.py:143-159 swallows AttributeError/TypeError
│       → The run ran but the result event was never written
│       → Add logging (see Section 3 above) and re-run
│
└─ Was it an agent run with --background that used a run_id as its task?
    └─ DS-09: the UUID was run as a literal task, not a resume
       → Look for a run whose task field is a UUID-shaped string
       grep '"event_type": "run_started"' ~/.teaagent/audit.jsonl \
         | python -c "import sys,json; [print(json.loads(l)['payload']['task']) for l in sys.stdin]"
```

---

## 6. Post-Mortem: "The Undo Damaged My Files"

```bash
# Check git stash list for checkpoint stashes
git stash list

# Inspect what the stash contains before popping
git stash show -p stash@{0}

# If TUI /undo was used and it reverted too much (DS-05):
# The stash pop reverted to the checkpoint, not just the last run's files.
# Manual recovery:
git stash show -p stash@{0} > /tmp/recovered.patch
# Apply only the hunks you need from /tmp/recovered.patch with patch -p1 -R
```

---

## 7. Stack Trace Interpretation Quick Reference

| Pattern in traceback | Likely cause |
|---------------------|-------------|
| `...tui/__init__.py` → `_run_agent_task` | TUI execution path (bypasses controller) |
| `...chat_session_controller.py` → `execute_task` | REPL/controller execution path |
| `...run_store.py` → `task_for_run` → `ValueError` | resume/agent-show used on a REPL suspension run_id |
| `...approval/manager.py` → `EOFError` | Approval prompt without a terminal (piped input) |
| `...context_bus.py` → `sqlite3.OperationalError` | Database locked or corrupt |
| `...workflow_engine.py` → `ValidationError` | Skill/workflow schema mismatch |
| `...anp_adapter.py` → fallback warning | ANP routing unavailable; degraded mode |

---

## 8. Collecting a Full Incident Report

When filing a bug or escalating an incident, collect:

```bash
# Run context
teaagent --version 2>/dev/null || python -c "import teaagent; print(teaagent.__version__)"
python --version
uname -a

# Run audit trail
teaagent agent show <run_id> --format json > incident-audit.json

# Last 200 audit events
tail -200 ~/.teaagent/audit.jsonl > incident-audit-tail.jsonl

# Suspension file (if REPL)
cp ~/.teaagent/suspension-<id>.json incident-suspension.json

# Git state at time of incident
git status > incident-git-status.txt
git stash list >> incident-git-status.txt

# Redact before sharing
# suspension files may contain source code snippets and LLM observations
```

See also: [Run Evidence and Audit Guide](../run-evidence-and-audit-guide.md).
