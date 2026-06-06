# Command Snippet Registry
# 2026-06-06

> **Owns:** Which high-value guide command prefixes are smoke-tested vs manual-only.
>
> **Review trigger:** Golden-path commands, CLI flags, or snippet inventory changes.

This registry backs [command-snippet-inventory.md](../generated/command-snippet-inventory.md).
Prefixes match exact commands or any command that starts with the prefix plus a space.

| Prefix | Coverage | Verification |
| --- | --- | --- |
| `teaagent setup` | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent daily` | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent approval pending` | smoke | tests/test_approval_selectors.py |
| `teaagent approval approve` | smoke | tests/test_approval_selectors.py |
| `teaagent approval list` | smoke | tests/test_cli_ergonomics_handlers.py |
| `teaagent agent status` | smoke | tests/test_run_progress.py |
| `teaagent run` | manual | Operator golden-path smoke before release |
| `teaagent plan` | manual | Operator plan artifact smoke before release |
| `teaagent chat` | manual | Operator REPL smoke before release |
| `teaagent tui` | manual | Operator TUI smoke before release |
| `teaagent memory failures` | manual | Operator memory hygiene smoke |
| `teaagent doctor model` | manual | Provider-dependent local smoke |
| `teaagent doctor providers` | manual | Provider-dependent local smoke |
| `teaagent doctor mcp` | manual | MCP wizard smoke when MCP enabled |
| `teaagent doctor aigateway` | manual | AI gateway doctor smoke |
| `teaagent doctor project` | manual | Project doctor wizard smoke |
| `teaagent mcp serve` | manual | MCP server smoke when MCP enabled |
| `teaagent agent daily` | smoke | tests/acceptance/test_daily_cli.py |
| `teaagent agent run` | manual | Agent run smoke with configured provider |
| `teaagent agent resume` | manual | Resume smoke with paused run fixture |
| `teaagent agent undo` | manual | Undo smoke after mutating run |
| `teaagent agent preflight` | manual | Preflight smoke with configured provider |
| `teaagent agent attach` | manual | Attach/follow smoke with running run |
| `teaagent approval grant` | manual | Scoped grant smoke in prompt mode |
| `teaagent approval check` | manual | Scoped grant check smoke |
| `teaagent approval subagents list` | manual | Subagent queue smoke when enabled |
| `teaagent model providers` | manual | Provider list smoke |
| `teaagent workspace tools` | manual | Tool registry list smoke |
| `teaagent acp serve` | manual | ACP adapter smoke when enabled |
| `teaagent --help` | manual | CLI help smoke |
| `teaagent --config` | manual | Alternate config path smoke |
| `teaagent model smoke` | manual | Provider smoke with configured credentials |
| `teaagent agent show` | manual | Run inspection smoke |
| `teaagent agent card` | manual | AgentCard JSON smoke |
| `teaagent approval revoke` | manual | Revoke grant smoke |
| `teaagent agent runs` | manual | Run list smoke |

Regenerate inventory: `python3 scripts/generate_command_snippet_inventory.py`
