# cli — Behavior Specification

## Purpose

The command-line interface and entry point for TeaAgent. Parses arguments, dispatches to handlers, and bridges user input to the runner, TUI, and other subsystems. All user-facing commands originate here.

## Behavior Contract

1. **Subcommand dispatch** — `main()` builds an `argparse` parser tree; each subcommand maps to a handler function.
2. **Handler isolation** — CLI handlers are pure functions receiving the parsed `argparse.Namespace`; they never share state.
3. **Output formatting** — `_output.py` provides consistent JSON, table, and human-readable output functions.
4. **Error presentation** — unhandled exceptions from handlers are caught at the top level and formatted as error messages with exit code 1.
5. **Exit codes** — 0 for success, 1 for errors, 2 for usage errors (argparse default).

## Command Groups

| Group | Commands |
|-------|---------|
| `agent` | `run`, `plan`, `status`, `undo`, `resume`, `attach`, `card` |
| `chat` | `chat` (interactive TUI), `completion`, `clarify` |
| `audit` | `audit list`, `audit show`, `audit verify`, `audit export`, `audit serve` |
| `approval` | `approval list`, `approval approve`, `approval deny`, `approval grant`, etc. |
| `skill` | `skill list`, `skill run`, `skill install`, `skill publish` |
| `mcp` | `mcp add`, `mcp list`, `mcp serve` |
| `memory` | `memory list`, `memory pin`, `memory unpin` |
| `sandbox` | `sandbox create`, `sandbox merge`, `sandbox cleanup` |
| `cloud` | `cloud submit`, `cloud list`, `cloud show`, `cloud cancel` |
| `automation` | `automation add`, `automation list`, `automation run`, etc. |

## Entry Point

```
teaagent → cli/__main__.py → cli/__init__.main() → argparse dispatch → handler()
```

## Invariants

- `main()` always returns an integer exit code.
- Handlers must not call `sys.exit()` — they return or raise; the top level handles exit.
- Sensitive flags (API keys) are read from environment variables, never from positional args.
