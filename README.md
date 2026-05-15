# TeaAgent

Governance-first agent harness for autonomous coding tasks. Thin orchestration layer with tool governance, state boundaries, audit logging, and destructive-tool approval.

## Architecture

```
CLI / TUI  →  AgentRunner (decision loop)  →  ToolRegistry  →  Workspace Tools
                  ↕                              ↕
           LLM Adapters                  ApprovalPolicy
           (7 providers)                 (5 permission modes)
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
- **Code Mode**: Restricted Python execution with AST validation and pluggable child-process or container backends.
- **Telemetry**: OpenTelemetry spans plus audit-driven metrics sinks for run and tool lifecycle events.
- **Heartbeat**: Background audit events for run liveness monitoring and hang detection.

See [docs/architecture.md](docs/architecture.md) for component details, data flow, and extension points.

## Install

```bash
pip install -e .
```

On macOS/Homebrew Python (PEP 668), prefer a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -e ".[dev]"
```

Or without the console script:

```bash
python3 -m teaagent.cli --help
```

Requires Python >= 3.10. Optional dependency groups enable non-core integrations:

```bash
pip install -e ".[graphqlite]"
pip install -e ".[oauth]"
pip install -e ".[telemetry]"
pip install -e ".[dev]"
pip install -e ".[release]"
pip install -e ".[security]"
```

- `graphqlite`: GraphQL RAG persistence features.
- `oauth`: OAuth 2.1 / DPoP cryptographic proof validation.
- `telemetry`: OpenTelemetry tracing and metrics exporters.
- `dev`: tests, linting, type checking, and pre-commit.
- `release`: local build and distribution checks.
- `security`: local dependency auditing with `pip-audit`.

## Quick Start

**New to TeaAgent?** See the [Quick Start Guide](docs/USAGE.md) for a step-by-step walkthrough covering API key setup, agent mode, chat mode, approvals, and troubleshooting.

```bash
# 1. Set up API keys (one-time)
cp scripts/provider_keys.zsh ~/.teaagent/provider_keys.zsh
# Edit the file and fill in your keys, then:
echo 'source ~/.teaagent/provider_keys.zsh' >> ~/.zshrc
source ~/.zshrc

# 2. Verify setup
teaagent doctor model gpt

# 3. Run an inspect-only task
teaagent agent run gpt "Summarize the test suite" --permission-mode read-only

# 4. Start interactive TUI
teaagent tui --chat
```

### Environment Variables

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
export OLLAMA_API_KEY=...   # optional for local deployments
export VLLM_API_KEY=...     # optional for local deployments
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

### 5-Minute Walkthrough

Run the self-contained end-to-end example (no API keys needed):

```bash
python3 examples/full_agent_run.py
```

It demonstrates the full lifecycle:
1. **Workspace tools** — registers `read_file`, `write_file`, `apply_patch`, etc.
2. **Audit + metrics** — writes per-run JSONL audit log, collects counters/histograms.
3. **Memory catalog** — adds a workspace memory entry.
4. **Budget + approval** — caps iterations/tool-calls, enforces write-only permission mode.
5. **Agent runner** — a deterministic `decide` function emits two tool calls then finishes.
6. **Run store** — persists the completed run and lists it.
7. **Audit replay** — reads back every recorded event from the run log.
8. **Metrics snapshot** — prints final counter values.

For a real LLM-driven run:
```bash
teaagent agent run gpt "Summarize the tests" --permission-mode read-only
```

## Development

```bash
# Run tests
pytest

# Run user-facing acceptance workflows
python3 -m pytest tests/acceptance

# Lint
ruff check .
ruff format --check .

# Type check
mypy teaagent/
```

See [docs/cli.md](docs/cli.md) for full CLI reference, scope docs for P0/P1/P2 feature delineation, and ADRs for architecture decisions.

Additional references:

- [Audit event reference](docs/audit-events.md)
- [Use-case traceability](docs/use-cases.md)
- [Acceptance coverage](docs/acceptance.md)
- [Tool authoring guide](docs/tool-authoring.md)
- [Provider authoring guide](docs/provider-authoring.md)
- [Top-level API migration note](docs/migration-top-level-api.md)
- [Security model](SECURITY.md)
- [Examples](examples/README.md)
