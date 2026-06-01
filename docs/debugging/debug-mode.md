# Debug Mode Guide
# teaagent — 2026-06-02

How to enable and use debug output for teaagent development and incident investigation.

---

## 1. Enabling Debug Logging

teaagent uses the standard Python `logging` module throughout. Every module registers with `logging.getLogger(__name__)`. There is no built-in `--debug` CLI flag; log level must be set at process startup via environment variable or a wrapper script.

### Via environment variable (recommended)

```bash
# All modules at DEBUG level
PYTHONPATH=. python -m teaagent.cli chat "my task"   # env set externally

# Preferred: use the helper below
export LOG_LEVEL=DEBUG
teaagent chat "my task"
```

teaagent does not yet call `logging.basicConfig()` internally. If no handler is configured, all Python logging defaults to the last-resort handler (stderr, WARNING+). To capture DEBUG output you must configure a handler before the CLI runs:

```bash
# One-liner wrapper that configures logging then delegates to the CLI
python - <<'EOF'
import logging, sys, runpy
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    stream=sys.stderr,
)
runpy.run_module("teaagent.cli", run_name="__main__", alter_sys=True)
EOF
```

Or add a small `debug_runner.py` to the repo root:

```python
# debug_runner.py — not committed, local dev only
import logging, sys
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    stream=sys.stderr,
)
from teaagent.cli import main
main()
```

Then: `python debug_runner.py chat "my task"`

### Selective module debug

To avoid log spam from unrelated modules, target specific packages:

```python
import logging
# Only debug the budget monitor and context bus
logging.getLogger("teaagent.budget_monitor").setLevel(logging.DEBUG)
logging.getLogger("teaagent.context_bus").setLevel(logging.DEBUG)
```

Put this in `debug_runner.py` before calling `main()`.

---

## 2. Verbose Output per Subcommand

| Surface | How to get more output |
|---------|----------------------|
| `teaagent agent run` | Add `-v` / `--verbose` if supported by your build; otherwise use LOG_LEVEL=DEBUG |
| `teaagent tui` | Open the TUI then run the `/debug` intent keyword — routed to the DEBUGGING coordinator task type |
| `teaagent agent show <run_id>` | Prints stored audit events; pass `--format json` for machine-readable output |
| Approval prompts | Set `TEAAGENT_APPROVAL_TRACE=1` (if supported) to echo each approval decision |

---

## 3. Log File Capture

```bash
# Capture stderr to file while still seeing it in terminal
teaagent chat "task" 2> >(tee teaagent-debug.log >&2)

# Redirect both stdout and stderr (loses terminal colour)
teaagent chat "task" > teaagent.log 2>&1
```

---

## 4. Interactive Debugging (pdb / debugpy)

### pdb breakpoints

Insert a breakpoint in the module you want to inspect:

```python
# In teaagent/tui/__init__.py around line 890
import pdb; pdb.set_trace()   # or just: breakpoint()
```

Run from the terminal (not via TUI, which intercepts stdin):

```bash
python -m pdb -m teaagent.cli agent run "my task"
```

Useful pdb commands:

```
n      — next line (step over)
s      — step into
c      — continue
l      — list source
p <expr> — print expression
pp     — pretty-print
b <file>:<line>  — set breakpoint
bt     — backtrace
```

### debugpy (VS Code / PyCharm remote attach)

See [Debugger Setup](../debugging/debugger-setup.md).

---

## 5. Audit Event Stream as Debug Proxy

Since teaagent has rich audit events, the audit log is often the fastest debug surface:

```bash
# Follow audit events live during a run
teaagent agent run "task" &
tail -f ~/.teaagent/audit.jsonl | python -m json.tool
```

Audit events carry: `event_type`, `run_id`, `event_id`, `created_at`, `payload`. See [Logging Architecture](logging-architecture.md) for the full event taxonomy.

---

## 6. Decision Tree: "I need more information"

```
What are you investigating?
│
├─ A wrong value displayed (cost, undo scope) ──→ Enable DEBUG on teaagent.tui
│
├─ A failing approval ───────────────────────────→ Enable DEBUG on teaagent.approval_manager
│
├─ A run that errors or produces no output ──────→ teaagent agent show <run_id>
│                                                   then enable DEBUG on teaagent.coordinator
│
├─ A suspend/resume failure ─────────────────────→ Inspect ~/.teaagent/suspension-<id>.json
│                                                   enable DEBUG on teaagent.cli._handlers._agent
│
├─ A tool call that was not approved ────────────→ Enable DEBUG on teaagent.tool_permissions
│
└─ A cost/budget discrepancy ────────────────────→ Enable DEBUG on teaagent.budget_monitor
                                                    and teaagent.cost_tracker
```
