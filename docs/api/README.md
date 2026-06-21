# TeaAgent API Reference

This directory contains the complete API and integration specifications for teaagent.

---

## Documents

| Document | Contents |
|----------|----------|
| [cli-api.md](cli-api.md) | All CLI subcommands, arguments, flags, environment variables, exit codes, JSON output shapes |
| [repl-api.md](repl-api.md) | All REPL slash commands with behaviour, expected outputs, and error cases |
| [tui-api.md](tui-api.md) | TUI keybindings, UI layout, state transitions, auto-complete, persistence |
| [mcp-api.md](mcp-api.md) | MCP server JSON-RPC methods, tool schemas, error codes, workspace registry, trust model |
| [python-api.md](python-api.md) | Public Python classes and functions with type signatures, pre/post conditions, exceptions |
| [data-formats.md](data-formats.md) | Audit log JSONL, session JSON, config JSON, suspension state, undo journal, cost tracking |
| [integration-guide.md](integration-guide.md) | How to add LLM providers, register tools, define approval policies, wire CI/CD, embed in apps |

---

## Quick Reference

### Start an interactive session

```bash
teaagent chat
teaagent chat claude "explain the auth flow"
```

### Run a one-shot task

```bash
teaagent run "add pagination to /users endpoint"
teaagent run --permission-mode allow --output-format json "fix lint errors"
```

### Start the MCP server

```bash
teaagent mcp serve
teaagent mcp serve --root /path/to/project --permission-mode workspace-write
```

### Inspect a run

```bash
teaagent runs list
teaagent runs show <run_id>
teaagent audit show <run_id>
```

### Restore after a run

```bash
teaagent undo
teaagent undo <run_id>
```

---

## Stability Tiers

| Tier | Meaning |
|------|---------|
| **Stable** | Will not be removed or incompatibly changed without a deprecation cycle |
| **Experimental** | May change in any release; use at your own risk |

See the [Backwards Compatibility](integration-guide.md#backwards-compatibility) section in the integration guide for a per-surface table.

---

## Key Concepts

**Permission modes** — control which tool calls are allowed without an interactive prompt. From most to least restrictive: `read-only` → `workspace-write` → `prompt` → `allow` → `danger-full-access`. See [cli-api.md § Permission Modes](cli-api.md#permission-modes).

**Approval policy** — the rule engine that decides whether a tool call is allowed. Combines permission mode, pre-approved call IDs, named presets, and optional multi-sig quorum. See [python-api.md § ApprovalPolicy](python-api.md#approvalpolicy) and [integration-guide.md § Defining Approval Policies](integration-guide.md#defining-approval-policies).

**Audit log** — an append-only JSONL file (`.teaagent/runs/<run_id>.jsonl`) recording every tool call, model request, approval decision, and cost checkpoint. HMAC-chained for tamper detection. See [data-formats.md § Audit Log Format](data-formats.md#audit-log-format).

**Tool registry** — central registry of all tools available to the agent and MCP server. Tools declare input/output JSON schemas, security annotations, and optional rate limits. See [python-api.md § ToolRegistry](python-api.md#toolregistry) and [integration-guide.md § Registering a Custom Tool](integration-guide.md#registering-a-custom-tool).

**Workspace root** — the directory the agent treats as its working directory. File paths in tool calls are resolved relative to this root. Set with `--root` or the `root` REPL command.

**Session** — a saved conversation history (`ChatSession`) that persists multi-turn context across REPL invocations. Sessions are stored in `.teaagent/sessions/`. See [data-formats.md § Session JSON Schema](data-formats.md#session-json-schema).

**Git sandbox** — when `--git-sandbox` is set, the agent runs in an isolated branch. Changes are discarded on failure or promoted to the main branch on success. Use `teaagent runs commit <run_id>` to merge a sandbox run.

---

## File Layout

```
.teaagent/
├── config.json              # Workspace config
├── tui_state.json           # Last TUI session state
├── runs/                    # Per-run audit logs (.jsonl)
├── sessions/                # Saved chat sessions (.json)
├── plans/                   # Written plan artifacts (.md)
├── undo/                    # Undo journal snapshots
└── graph.db                 # GraphQLite database (optional)

~/.teaagent/
├── workspace_registry.json  # Global workspace lock registry
└── repl_history             # REPL command history (prompt_toolkit)
```

---

## Source Locations

| Component | Source |
|-----------|--------|
| CLI entry | `teaagent/cli/__init__.py` |
| Agent parsers | `teaagent/cli/_agent_parsers.py` |
| CLI handlers | `teaagent/cli/_handlers/` |
| REPL commands | `teaagent/tui/_commands.py` |
| TUI | `teaagent/tui/__init__.py` |
| Tool registry | `teaagent/tools.py` |
| MCP server | `teaagent/mcp_server.py` |
| Audit logger | `teaagent/audit.py` |
| Approval / policy | `teaagent/approval/manager.py`, `teaagent/policy.py` |
| Session store | `teaagent/session.py` |
| LLM adapters | `teaagent/llm/` |
| Cost tracker | `teaagent/cost_tracker.py` |
| Runner types | `teaagent/runner/_types.py` |
