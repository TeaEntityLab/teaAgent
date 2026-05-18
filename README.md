# TeaAgent

Governance-first agent harness for autonomous coding tasks. Thin orchestration layer with tool governance, state boundaries, audit logging, and destructive-tool approval.

## Start Here

### 1. Install

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

Install enhanced TUI editing/history support (optional):

```bash
pip install -e ".[tui]"
```

### 2. First Run

```bash
# Verify provider setup
teaagent doctor model gpt

# Safe read-only first task
teaagent agent run gpt "Summarize the test suite" --permission-mode read-only
```

### 3. Permission Modes

- `read-only`: blocks destructive tools
- `workspace-write`: allows file writes, blocks shell mutation
- `prompt`: asks for approval on destructive actions
- `allow`: allows destructive tools for the session
- `danger-full-access`: full access for trusted automation only

### 4. Plan vs Write

- Planning/exploration: use `--permission-mode read-only`
- Editing/implementation: use `--permission-mode workspace-write` or `prompt`

### 5. Extensibility

- MCP server: `teaagent mcp serve`
- Skills/plugins: documented in [docs/tool-authoring.md](docs/tool-authoring.md) and [docs/provider-authoring.md](docs/provider-authoring.md)

### 6. Docs

- Quick start: [docs/USAGE.md](docs/USAGE.md)
- CLI/MCP reference: [docs/cli.md](docs/cli.md)
- Acceptance coverage: [docs/acceptance.md](docs/acceptance.md)
- Use-case traceability: [docs/use-cases.md](docs/use-cases.md)
- Architecture decisions: [docs/adr](docs/adr) (including ANP adapter boundary in ADR 0007)

## Architecture

```
CLI / TUI  →  AgentRunner (decision loop)  →  ToolRegistry  →  Workspace Tools
                  ↕                              ↕
           LLM Adapters                  ApprovalPolicy
           (10 providers)                 (5 permission modes)
```

- **AgentRunner**: Iterates between model decisions and tool executions within budget limits.
- **ToolRegistry**: Single point of tool dispatch with schema validation.
- **ApprovalPolicy**: Enforces permission modes before any destructive tool runs.
- **AuditLogger**: Universal event sink — every decision, execution, and error is recorded.
- **ModelDecisionEngine**: Bridges LLM responses into structured decisions via prompt assembly and JSON parsing.
- **Workspace Tools**: File read/write, shell inspect/mutate, glob search, git status, hash-anchored editing.
- **Memory Catalog**: Three-tier memory system (Project/Personal/Auto-Memory) for persistent context.
- **Intent Clarification**: Deterministic ambiguity scoring before model invocation.
- **Run Store**: Persistent JSONL run history with resumable task replay.
- **Code Mode**: Restricted Python execution with AST validation and pluggable child-process or container backends.
- **Telemetry**: OpenTelemetry spans plus audit-driven metrics sinks for run and tool lifecycle events.
- **Heartbeat**: Background audit events for run liveness monitoring and hang detection.
- **Hook System**: 8-event lifecycle (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, SubagentStop, SessionEnd) for extensibility.
- **Plugin System**: Four extension points (Commands, Agents, Hooks, MCP Servers) compatible with Claude Code.
- **Context Compaction**: Automatic context compression at 75-92% token usage (Claude Code compatible).
- **Plan Mode**: Read-only exploration mode for safe codebase analysis.
- **ACP Adapter**: Agent Client Protocol integration for VS Code, Zed, and JetBrains IDEs.

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
pip install -e ".[tui]"
pip install -e ".[oauth]"
pip install -e ".[telemetry]"
pip install -e ".[dev]"
pip install -e ".[release]"
pip install -e ".[security]"
```

- `graphqlite`: GraphQL RAG persistence features.
- `tui`: `prompt-toolkit`-powered interactive editing/history in `teaagent tui`.
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
export MISTRAL_API_KEY=...
export DEEPSEEK_API_KEY=...
export XAI_API_KEY=...
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

### Plan Mode

Enable read-only exploration mode to analyze codebases without making changes:

```bash
teaagent agent run gpt "Analyze this codebase" --permission-mode read-only
```

This is useful for:
- Understanding unfamiliar code
- Planning refactoring approaches
- Code review without accidental modifications

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

### LSP Code Analysis (P0)

Enable LSP-backed tools for semantic code navigation:

```bash
teaagent agent run gpt "inspect src/app.py" --code-analysis
```

Available tools when enabled:
- `code_definition`
- `code_references`
- `code_diagnostics`
- `code_symbols`

You can also enable this by workspace config:

```json
{
  "code_analysis_enabled": true
}
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

#### MCP Filtering & Sampling

MCP tool calls can be filtered by allow/block lists and configured with sampling parameters:

```python
from teaagent.mcp_client import MCPClientFactory

client = MCPClientFactory.create_http(
    "https://mcp-server.example.com/mcp",
    allowed_tools=["read_file", "search"],
    blocked_tools=["shell", "delete"],
    sampling_max_tokens=4096,
    sampling_temperature=0.7,
)
```

### Skills System

TeaAgent supports skill packages for reusable agent behaviors. Skills are discovered from:

1. Project: `.opencode/skill/`
2. User: `~/.config/opencode/skills/`

Built-in skills:
- `code-review` - Code review and quality analysis
- `git-workflow` - Git operations and branch management
- `testing` - Test writing and execution
- `refactoring` - Code refactoring guidance
- `mcp-integration` - MCP server configuration
- `p0-agent-harness` - P0 harness behavior (built-in)

### Plugin System

Four extension points for customization:

| Type | Description | Example |
|------|-------------|---------|
| Commands | Slash commands | `/commit`, `/review` |
| Agents | Custom subagents | `@code-reviewer`, `@tester` |
| Hooks | Lifecycle events | PreToolUse, PostToolUse |
| MCP Servers | External integrations | GitHub, databases |

### Hook System

8-event lifecycle hooks (Claude Code compatible):

- `SessionStart` - Before session begins
- `UserPromptSubmit` - After user message
- `PreToolUse` - Before tool execution (can veto)
- `PostToolUse` - After tool execution
- `PreCompact` - Before context compaction
- `Stop` - Before session stops
- `SubagentStop` - After subagent completes
- `SessionEnd` - After session ends

```python
from teaagent.hooks import HookRegistry, permission_check_hook, PermissionMode

registry = HookRegistry()
registry.register_pre_hook(permission_check_hook(mode=PermissionMode.AUTO))
```

### Context Compaction

Automatic context compression when token usage exceeds 75-92% (Claude Code traffic light zones):

- Green (0-75%): Normal operation
- Yellow (75-92%): User hints
- Red (92%+): Auto-compaction triggered

### ACP (Agent Client Protocol)

IDE integration for VS Code, Zed, and JetBrains via JSON-RPC over stdio:

```bash
# Run as ACP server
teaagent acp serve
```

 ACP enables TeaAgent to run inside ACP-compatible editors with full tool access.

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
