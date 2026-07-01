# CLI API Specification

**Entry point:** `teaagent` (module: `teaagent.cli`)  
**Config file:** `.teaagent/config.json` (or `--config PATH`)  
**Status:** Stable unless marked `[experimental]`

---

## Global Flags

| Flag | Type | Description |
|------|------|-------------|
| `--config PATH` | string | Path to JSON config file |
| `--profile NAME` | string | Named profile within config |
| `--version` | flag | Print version and exit |
| `--verbose` | flag | Enable debug logging to stderr |
| `--quiet` | flag | Suppress all non-error output |
| `--output-format {json,text}` | string | Output format (default: `text`) |

---

## Subcommands

### `run` / `ask`

Run a model-driven agent task to completion.

```
teaagent run [provider] [task] [options]
teaagent ask [provider] [task] [options]
```

Alias: `run` and `ask` are identical.

#### Positional Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `provider` | no | LLM provider name (claude, gpt, gemini, etc.) |
| `task` | no | Task description (if omitted, read from stdin or `--from-plan`) |

#### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--from-plan PATH` | string | — | Load task from plan artifact |
| `--allow-external-plan` | flag | false | Allow plan files outside `.teaagent/plans/` |
| `--root PATH` | string | `.` | Workspace root directory |
| `--model NAME` | string | provider default | Override model name |
| `--route-model` | flag | false | Enable task-based model routing |
| `--max-iterations N` | int | 10 | Max agent loop iterations |
| `--max-tool-calls N` | int | 10 | Max tool calls per run |
| `--max-estimated-cost-cents N` | int | 0 (no cap) | Cost cap in cents |
| `--clarify` | flag | false | Run ambiguity scoring before model call |
| `--allow-destructive` | flag | false | Allow write/patch/shell tools |
| `--git-sandbox` | flag | false | Run in isolated git branch |
| `--git-sandbox-auto-stash` | flag | false | Auto-stash dirty state before sandbox |
| `--parallel N` | int | — | Run N parallel approaches (tournament) |
| `--approach HINT` | string | — | Hint for parallel approach (repeatable) |
| `--no-benchmark` | flag | false | Skip performance benchmarking |
| `--approve-call-id ID` | string | — | Deprecated/inert compatibility flag; grants nothing. Use `--approve-scoped TOOL:SHA256` |
| `--hitl-approval` | flag | false | Prompt before every destructive tool |
| `--permission-mode MODE` | enum | `prompt` | See [Permission Modes](#permission-modes) |
| `--subagent` | flag | false | Expose `subagent` delegation tool |
| `--max-subagent-depth N` | int | 1 | Max subagent nesting depth |
| `--heartbeat SECS` | int | 0 | Emit heartbeat every N seconds (0=off) |
| `--code-analysis` | flag | false | Enable LSP-backed code analysis tools |
| `--validate` | flag | false | Run post-run validation suite |
| `--validation-profile PROFILE` | enum | `standard` | `fast`, `standard`, `strict` |
| `--no-validate` | flag | false | Disable validation |
| `--require-plan` | flag | false | Block writes unless `--from-plan` is set |
| `--skip-plan-check` | flag | false | Skip plan enforcement (not recommended) |
| `--telemetry-otlp-endpoint URL` | string | — | OTLP HTTP endpoint for traces |
| `--telemetry-service-name NAME` | string | `teaagent` | OTel service name |
| `--telemetry-console` | flag | false | Print OTel spans to stderr |
| `--checkpoint-store PATH` | string | — | SQLite path for checkpoint storage |
| `--dry-run` | flag | false | Plan without calling the model |
| `--human` | flag | false | Human-friendly dry-run output |
| `--background` | flag | false | Run in background mode |
| `--progress` | flag | false | Stream progress lines to stderr |
| `--no-stream` | flag | false | Disable token streaming |
| `--stream-model-output` | flag | false | Stream output token-by-token |

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Task completed successfully |
| 1 | Task failed or model returned error |
| 2 | Argument or configuration error |
| 3 | Cost cap exceeded |
| 4 | Iteration or tool-call limit hit |
| 5 | Approval denied |
| 6 | Validation failed |

#### Output (JSON mode)

```json
{
  "run_id": "string",
  "status": "completed | failed | approval_denied | limit_exceeded",
  "final_answer": "string",
  "iterations": 0,
  "tool_calls": 0,
  "cost_cents": 0.0,
  "input_tokens": 0,
  "output_tokens": 0,
  "error_message": "string | null"
}
```

---

### `chat`

Start an interactive multi-turn chat session (opens TUI REPL).

```
teaagent chat [provider] [initial_task] [options]
```

All options from `run` apply, plus:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--session-id ID` | string | new UUID | Resume specific session |

The TUI REPL is documented separately in [repl-api.md](repl-api.md) and [tui-api.md](tui-api.md).

---

### `tui`

Start the interactive TUI directly (same as `chat` with no initial task).

```
teaagent tui [options]
```

---

### `resume`

Re-run a task from a persisted run ID.

```
teaagent resume <run_id> [options]
```

All `run` options apply. The run state (messages, tool history) is replayed up to the checkpoint.

---

### `plan`

Write a read-only plan artifact without calling the model.

```
teaagent plan [provider] [task] [options]
```

Writes to `.teaagent/plans/<timestamp>-<slug>.md`. All `run` options apply.

---

### `preflight`

Show routing, memory, and tool plan without calling the model.

```
teaagent preflight [provider] [task] [options]
```

---

### `daily`

Show agent readiness, recent runs, harness health, and token budget.

```
teaagent daily [task]
```

---

### `undo`

Restore workspace files from the undo journal of a run.

```
teaagent undo [run_id]
```

If `run_id` is omitted, uses the most recent run.

---

### `runs`

Manage persisted runs.

```
teaagent runs <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `list` | List all persisted runs |
| `show <run_id>` | Show run details |
| `trace <run_id>` | Show full tool-call trace |
| `export <run_id>` | Export run as JSON |
| `replay <run_id>` | Replay run step-by-step |
| `commit <run_id>` | Commit git-sandbox branch |

---

### `approval`

Manage tool-call approvals.

```
teaagent approval <subcommand>
```

| Subcommand | Arguments | Description |
|-----------|-----------|-------------|
| `list` | — | List approval presets |
| `pending` | — | Show pending approval requests |
| `approve <call_id>` | call ID | Approve one in-flight pending call via JIT/session state |
| `deny <call_id>` | call ID | Deny a specific pending call |
| `next` | — | Show the next pending request |
| `audit` | — | Show full approval audit log |
| `explain <call_id>` | call ID | Explain which rule matched |
| `check <call_id>` | call ID | Check if a call is approved |
| `grant` | — | Grant blanket permission |
| `revoke` | — | Revoke a blanket permission |
| `preset` | — | Manage named approval presets |
| `doctor` | — | Diagnose approval configuration |
| `why-denied` | — | Explain most recent denial |
| `subagents list` | — | List subagent approval queue |
| `subagents approve <id>` | subagent ID | Approve a subagent |
| `subagents deny <id>` | subagent ID | Deny a subagent |
| `subagents approve-all` | — | Approve all queued subagents |
| `subagents deny-all` | — | Deny all queued subagents |
| `subagents prune` | — | Remove stale entries |

---

### `audit`

Manage the audit log.

```
teaagent audit <subcommand>
```

| Subcommand | Arguments | Description |
|-----------|-----------|-------------|
| `list` | — | List audit events |
| `show <run_id>` | run ID | Show all events for a run |
| `export` | — | Export audit log as JSON |
| `prune` | — | Delete old log files |
| `serve` | — | Start HTTP server streaming events |
| `verify` | — | Verify HMAC chain integrity |

---

### `memory`

Manage the agent memory store.

```
teaagent memory <subcommand>
```

| Subcommand | Arguments | Description |
|-----------|-----------|-------------|
| `add <text>` | text | Add a memory entry |
| `list` | — | List recent entries |
| `search <query>` | query | Full-text search |
| `show <id>` | memory ID | Show entry details |
| `failures list` | — | List failure cards |
| `failures show <id>` | failure ID | Show failure details |
| `failures invalidate <id>` | failure ID | Mark as invalid |
| `failures prune` | — | Delete old failures |
| `failures review` | — | Interactive failure review |
| `failures auto-invalidate` | — | Auto-invalidate stale failures |
| `team-memory list` | — | List team-scoped memories |
| `team-memory add <text>` | text | Add a team memory |
| `decisions list` | — | List captured decisions |
| `decisions add <text>` | text | Record a decision |

---

### `mcp`

MCP server management.

```
teaagent mcp <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `serve` | Start MCP server (stdin/stdout JSON-RPC) |
| `trust list` | List trusted MCP servers |
| `trust allow <server>` | Allow an MCP server |
| `trust deny <server>` | Block an MCP server |
| `trust inspect <server>` | Inspect server trust config |

---

### `session`

Manage saved chat sessions.

```
teaagent session <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `list` | List all sessions |
| `show <id>` | Show session details and messages |
| `resume <id>` | Resume a session in TUI |

---

### `skill`

Manage agent skills.

```
teaagent skill <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `candidate propose` | Propose a new skill |
| `candidate eval` | Evaluate a skill candidate |
| `candidate list` | List candidates |
| `candidate show` | Show candidate details |
| `candidate review` | Interactive review |
| `candidate install` | Install a skill |
| `explain` | Explain a skill |
| `publish` | Publish a skill |
| `search <query>` | Search registered skills |
| `marketplace-list` | List marketplace skills |
| `install-from-marketplace` | Install from marketplace |

---

### `tool`

Inspect registered tools.

```
teaagent tool <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `list` | List all registered tools |
| `inspect <name>` | Show tool schema and annotations |
| `lint` | Lint tool definitions for issues |

---

### `model`

Model configuration and testing.

```
teaagent model <subcommand>
```

| Subcommand | Description |
|-----------|-------------|
| `route <task>` | Show which model would be selected |
| `smoke` | Smoke test all configured models |
| `conformance` | Run provider conformance tests |
| `providers` | List available providers |
| `capabilities` | Show model capabilities |

---

### `doctor`

Diagnose system health.

```
teaagent doctor [component]
```

| Subcommand | Description |
|-----------|-------------|
| `all` | Check all systems |
| `graphqlite` | Check embedded database |
| `model` | Check LLM connectivity |
| `aigateway` | Check AI gateway |
| `providers` | Check all LLM providers |
| `project` | Check project configuration |
| `mcp` | Check MCP server setup |
| `env-order` | Check environment variable precedence |
| `git-sandbox` | Check git sandbox |
| `migration` | Check pending migrations |
| `selftest` | Run internal self-tests |

---

### `init`

Initialize a teaagent workspace in the current directory.

```
teaagent init
```

Creates `.teaagent/` directory with default config.

---

### `setup`

Interactive guided setup wizard.

```
teaagent setup
```

---

### `cost`

Show cost reports.

```
teaagent cost report [--days N] [--by model|label|day]
```

---

## Permission Modes

| Mode | Description |
|------|-------------|
| `read-only` | Only read-only tools are allowed |
| `workspace-write` | Read and workspace-write tools allowed; shell blocked |
| `prompt` | Prompt before each destructive tool call |
| `allow` | Allow all tools without prompting (trusted environment) |
| `danger-full-access` | No restrictions; allow all tool calls silently |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for Claude provider |
| `OPENAI_API_KEY` | API key for GPT provider |
| `GEMINI_API_KEY` | API key for Gemini provider |
| `OPENROUTER_API_KEY` | API key for OpenRouter |
| `TEAAGENT_CONFIG` | Path to config file (overrides `--config`) |
| `TEAAGENT_PROFILE` | Profile name (overrides `--profile`) |
| `TEAAGENT_PROVIDER` | Default provider |
| `TEAAGENT_MODEL` | Default model override |
| `TEAAGENT_PERMISSION_MODE` | Default permission mode |
| `TEAAGENT_ROOT` | Default workspace root |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Standard OTLP endpoint |
| `OTEL_SERVICE_NAME` | Standard OTel service name |
