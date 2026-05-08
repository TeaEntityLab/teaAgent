# TeaAgent

Governance-first agent harness for autonomous coding tasks. Thin orchestration layer with tool governance, state boundaries, audit logging, and destructive-tool approval.

## Architecture

```
CLI / TUI  →  AgentRunner (decision loop)  →  ToolRegistry  →  Workspace Tools
                  ↕                              ↕
           LLM Adapters                  ApprovalPolicy
           (5 providers)                 (5 permission modes)
```

- **AgentRunner**: Iterates between model decisions and tool executions within budget limits.
- **ToolRegistry**: Single point of tool dispatch with schema validation.
- **ApprovalPolicy**: Enforces permission modes before any destructive tool runs.
- **AuditLogger**: Universal event sink — every decision, execution, and error is recorded.
- **ModelDecisionEngine**: Bridges LLM responses into structured decisions via prompt assembly and JSON parsing.
- **Workspace Tools**: File read/write, shell inspect/mutate, glob search, git status, hash-anchored editing.
- **Memory Catalog**: Append-only JSONL store for workspace observations injected into agent prompts.
- **Intent Clarification**: Deterministic ambiguity scoring before model invocation.
- **Run Store**: Persistent JSONL run history with resumable task replay.

## Install

```bash
pip install -e .
```

Or without the console script:

```bash
python3 -m teaagent.cli --help
```

Requires Python >= 3.9. The `graphqlite` dependency is optional — GraphQL RAG features need it.

```bash
pip install -e ".[graphqlite]"
```

## Quick Start

```bash
# Check provider configuration
teaagent doctor model gpt

# Run an inspect-only task
teaagent agent run gpt "Summarize the test suite" --permission-mode read-only

# Start interactive TUI
teaagent tui
```

### Environment Variables

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
export OPENCODEZEN_API_KEY=...
```

## Features

### Permission Modes

| Mode | Behavior |
|------|----------|
| `read-only` | Blocks all destructive tools |
| `workspace-write` | Allows file writes; blocks shell mutation |
| `prompt` | Destructive tools pause for HITL approval or require an approval token |
| `allow` | Allows destructive tools for the session |
| `danger-full-access` | Full access; reserve for trusted automation |

### Tool Governance

- All tools registered through `ToolRegistry` with name, description, input/output schemas, and annotations.
- Destructive tools are blocked unless an approval token is present for that exact call.
- Shell commands are split into `workspace_run_shell_inspect` (safe) and `workspace_run_shell_mutate` (destructive).
- Hash-anchored line editing provides deterministic workspace edits.

### Agent Run

```bash
# Basic run
teaagent agent run gpt "Inspect this repo and summarize the test suite"

# With routing and workspace write
teaagent agent run gpt "Update README" --permission-mode workspace-write --route-model

# With clarification gate
teaagent agent run gpt "Improve this project" --clarify

# List runs
teaagent agent runs

# Resume a run
teaagent agent resume gpt <run_id>
```

### Streaming Progress

The TUI `progress on` command streams audit events (iteration, tool calls, completion) during agent runs. The LLM adapter supports streaming via the `stream` parameter on `LLMRequest`.

### MCP Server

Expose the workspace tool pack to MCP clients over stdio JSON-RPC or Streamable HTTP:

```bash
# stdio (default)
teaagent mcp serve --root /path/to/repo

# Streamable HTTP on loopback (POST /mcp, GET /mcp SSE, DELETE /mcp)
teaagent mcp serve --http --port 7330 --auth-token "$MCP_TOKEN"
```

`initialize` issues a fresh `Mcp-Session-Id` header; every later request must echo it. Pass `--allowed-origin` (repeatable) to restrict browser callers. See [docs/cli.md](docs/cli.md#mcp-server) for full transport details.

## Development

```bash
# Run tests
pytest

# Lint
ruff check .
ruff format --check .

# Type check
mypy teaagent/
```

See [docs/cli.md](docs/cli.md) for full CLI reference, scope docs for P0/P1/P2 feature delineation, and ADRs for architecture decisions.
