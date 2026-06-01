# cli — Risk Vectors & Known Issues

## R1: Task passthrough from CLI to TUI
**File**: `cli/_handlers/_chat.py`
**Risk**: The initial task string from `teaagent chat "task"` must be passed through to the TUI REPL. This was the subject of TASK-DD2-001 (recently fixed, commit `47710d9`). Regression risk if the TUI initialization path changes.
**Failure mode**: Initial task silently ignored; user must retype.

## R2: Handlers call sys.exit() in some paths
**File**: Multiple handlers
**Risk**: Some older handlers may call `sys.exit()` directly rather than returning an integer. This bypasses the top-level exit code handler and prevents cleanup.

## R3: argparse `--help` in subcommand exposes internal options
**File**: `cli/__init__.py`
**Risk**: Internal/developer flags (e.g., `--debug-audit`, `--skip-plan-check`) are exposed in `--help` output to all users.
**Failure mode**: Users accidentally use dangerous flags.

## R4: No input sanitization for task strings
**File**: `cli/_handlers/_chat.py`, `cli/_handlers/_agent.py`
**Risk**: The task string from the CLI is passed directly to the agent and LLM. A crafted task string could attempt prompt injection.
**Failure mode**: Prompt injection if task is treated as trusted input.

## R5: Config loading from multiple sources with no precedence documentation
**File**: `cli/execution.py`
**Risk**: Config is loaded from env vars, `~/.teaagent/config.toml`, `.teaagent/config.toml`, and CLI flags. Precedence order is implicit.
**Failure mode**: Unexpected config values; hard to debug.

## R6: `completion_command` may write to stdout, breaking shell integration
**File**: `cli/_handlers/_misc.py`
**Risk**: `completion_command` outputs shell completion scripts to stdout. If any other code in the startup path writes to stdout (e.g., a log message), the completion script is corrupted.
