# Debugger Setup
# teaagent — 2026-06-02

IDE debugger configuration for teaagent development.

---

## VS Code

### launch.json

Create `.vscode/launch.json` in the repo root:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "teaagent chat (debug)",
      "type": "debugpy",
      "request": "launch",
      "module": "teaagent.cli",
      "args": ["chat", "${input:task}"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      },
      "justMyCode": false,
      "console": "integratedTerminal"
    },
    {
      "name": "teaagent agent run (debug)",
      "type": "debugpy",
      "request": "launch",
      "module": "teaagent.cli",
      "args": ["agent", "run", "${input:task}"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      },
      "justMyCode": false,
      "console": "integratedTerminal"
    },
    {
      "name": "pytest: current file",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v", "-s"],
      "cwd": "${workspaceFolder}",
      "justMyCode": false,
      "console": "integratedTerminal"
    }
  ],
  "inputs": [
    {
      "id": "task",
      "type": "promptString",
      "description": "Task to run"
    }
  ]
}
```

### Remote attach (debugpy)

Start the process with debugpy listening:

```bash
pip install debugpy
python -m debugpy --listen 5678 --wait-for-client -m teaagent.cli agent run "my task"
```

In `.vscode/launch.json`:

```json
{
  "name": "Attach to teaagent",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "localhost", "port": 5678 },
  "justMyCode": false
}
```

---

## PyCharm

1. **Run → Edit Configurations → + → Python**
2. Set **Module name**: `teaagent.cli`
3. Set **Parameters**: `agent run "my task"`
4. Set **Working directory**: repo root
5. Enable **Gevent compatible** if using gevent workers
6. Set **Python interpreter** to your venv

For the TUI: note that the TUI uses `curses`/rich which intercepts stdin. Use **agent run** configurations for interactive debugging; attach breakpoints in `_run_agent_task` before the TUI loop takes over stdin.

---

## pdb in Tests

```bash
# Drop into pdb on first failure
python -m pytest tests/test_tui.py -x --pdb

# Drop into pdb on specific test
python -m pytest tests/test_tui.py::test_cost_display -s --pdb
```

Key spots to set breakpoints for known bugs:

| Bug | File | Approx line | What to inspect |
|-----|------|-------------|----------------|
| DS-01 cost | `tui/__init__.py` | 938 | `result.cost_cents` value |
| DS-03 silent catch | `chat_session_controller.py` | 143 | Exception type and message |
| DS-08 resume | `cli/_handlers/_agent.py` | 217 | `run_id` and `task_for_run` result |
| DS-11 task drop | `cli/_handlers/_chat.py` | 538 | `args.task` value before `run_tui` |
| DS-12 empty path | `approval_manager.py` | rule creation | `path_scope` value |
