# TeaAgent

> **Last reviewed:** 2026-08-26 (permission-mode bullets cover external-effect tools; EFX-002)
> **Review trigger:** README feature claims, golden path, or provider count changes.
> **Direction record:** [Harness-First Direction](docs/strategy/harness-first-direction-2026-06-13.md) (owner-operator harness-first current direction)

A personal, local-first governance harness for autonomous coding tasks — built by and for the owner-operator who maintains, uses, and audits his own runs. Thin orchestration layer with tool governance, state boundaries, audit logging, and destructive-tool approval.

**TeaAgent is not** a generic IDE agent clone, enterprise multi-user platform, or hosted cloud delegate. It is a local-first harness you operate — with explicit permission modes, hash-chained audit logs, and verification commands a security reviewer can run. See [When Not to Use TeaAgent](docs/guides/when-not-to-use-teaagent.md) for honest non-fit cases.

## Governance-first harness

| Pillar | What you get |
| --- | --- |
| **Permission matrix** | `read-only` → `workspace-write` → `prompt` → `allow` — not binary on/off |
| **Audit trail** | Append-only JSONL per run, hash-chained, exportable for compliance review |
| **Bounded runs** | Hard caps on iterations, tool calls, and estimated cost |
| **Human gates** | Destructive tools require approval; subagent queues are durable and inspectable |
| **Verify, don't trust** | `teaagent audit verify`, `doctor config-lint`, run receipts with audit health |

Trust model: [Trust and Audit Whitepaper](docs/governance/trust-and-audit-whitepaper.md). Enterprise NIST mapping: [Security Whitepaper](docs/security-whitepaper.md).

**Getting started:** [Owner-operator quickstart](docs/guides/getting-started-solo-cli.md) · [Tool/plugin author](docs/guides/getting-started-tool-plugin-author.md) · [Security reviewer](docs/guides/getting-started-security-reviewer.md)

## What makes it different

| Feature | TeaAgent | Most agents |
|---|---|---|
| Permission gates | ✅ prompt/read-only/workspace-write/allow/danger-full-access | ❌ binary or none |
| Audit trail | ✅ hash-chained JSONL run logs | ❌ chat history |
| Undo | ✅ `teaagent undo --last` (or git sandbox rollback) | ❌ manual revert |
| Cost cap | ✅ hard budget via `--max-estimated-cost-cents` | ❌ surprise bills |
| Model/provider choice | ✅ multiple adapters | ❌ vendor locked |

Enterprise evaluation artifact: [Trust and Audit Whitepaper](docs/governance/trust-and-audit-whitepaper.md) (NIST detail: [Security Whitepaper](docs/security-whitepaper.md)).

## Golden path (first hour)

One canonical flow for new users. Everything else in this README is **advanced** — see [docs/USAGE.md](docs/USAGE.md) for the full walkthrough and recovery recipes.

```bash
pip install -e .

# 1. Configure workspace (provider + safety defaults)
teaagent setup --root . --provider gpt --permission-mode read-only --write-env

# 2. Inspect readiness without calling a model
teaagent daily "summarize this repo" --dry-run --root . --human

# 3. First read-only task (provider comes from .teaagent/config.json)
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

**Advanced (recovery only):** `teaagent doctor model`, `teaagent doctor providers`, manual `~/.teaagent/providers_env.zsh`, legacy `teaagent init`, Keychain helpers — [docs/USAGE.md#recovery-recipes](docs/USAGE.md#recovery-recipes).

## Daily use (after setup)

Read-only cockpit each session:

```bash
teaagent daily "what I want to do today" --human
teaagent run "summarize the test suite" --permission-mode read-only
```

Edit or autonomous modes, TUI, recipes, and context profiles: [docs/USAGE.md#daily-use](docs/USAGE.md#daily-use).

Interactive loop: `teaagent tui --setup --root .`, then `daily`, `preflight`, `ask`, `runs`, `resume`.

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

Same as the [golden path](#golden-path-first-hour) above. Prefer `--human` on `daily` for readable readiness; omit it when scripting (JSON default).

### 3. Permission Modes

- `read-only`: blocks destructive tools and external-effect tools
- `workspace-write`: allows file writes, blocks shell mutation and external-effect tools
- `prompt`: asks for approval on destructive actions and external-effect tools (GitHub PR mutators, browser actions, remote MCP)
- `allow`: allows destructive tools for the session
- `danger-full-access`: full access for trusted automation only

### 4. Plan vs Write

- Planning/exploration: use `--permission-mode read-only`
- Editing/implementation: use `--permission-mode workspace-write` or `prompt`
- **Plan-before-write enforcement**: workspace-write mode now requires a plan by default for safety
- Use `--skip-plan-check` to override (not recommended for production workflows)

### 5. Extensibility

- MCP server: `teaagent mcp serve`
- Skills/plugins: documented in [docs/tool-authoring.md](docs/tool-authoring.md) and [docs/provider-authoring.md](docs/provider-authoring.md)

### 6. Docs

- Documentation front door: [docs/INDEX.md](docs/INDEX.md)
- Quick start: [docs/USAGE.md](docs/USAGE.md)
- CLI/MCP reference: [docs/cli.md](docs/cli.md)
- Troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md)
- Acceptance coverage: [docs/acceptance.md](docs/acceptance.md)
- Use-case traceability: [docs/use-cases.md](docs/use-cases.md)
- Architecture decisions: [docs/adr](docs/adr) (including ANP adapter boundary in ADR 0007)
- Model capability matrix: [docs/model-capability-matrix.md](docs/model-capability-matrix.md)

### 7. Memory & Context Features

TeaAgent includes persistent memory features to learn from past mistakes and sync with your IDE:

**Failure Experience Loop:**
- Background tasks that fail automatically create "failure cards" capturing error context
- Review those failure cards before retrying similar work via `teaagent memory failures` (surfaced on demand, not auto-injected into new runs)
- Automated invalidation rules prevent memory corruption (file signature changes, test refactors, dependency updates)
- Commands: `teaagent memory failures` (list), `teaagent memory failures auto-invalidate` (apply rules), `teaagent memory failures prune` (cleanup)

**Live Context Anchors:**
- Pin files with `/pin <file>` to watch for changes in your IDE
- The interactive TUI refreshes context when you save pinned files (the file watch runs in the TUI session)
- Commands: `/pin <file>`, `/unpin <file>`, `/pinned` (list)

### 8. Self-Healing Validation (Beta)

Static analysis validation (ruff, mypy, tsc, eslint) is integrated with the agent runner and workflow engine:

**Validation Tools:**
- Auto-detects available tools (ruff, mypy, tsc, eslint)
- Runs the configured validation profile after an agent run (post-run; it does not gate commits)
- Supports Python, TypeScript, and JavaScript projects
- Enable with `--validate` on `agent run` or via workflow self-healing steps

See [maturity-matrix.md](docs/maturity-matrix.md) for surface status and test pointers.

### 9. Tournament Selection (Beta)

Tournament-style parallel execution runs in `SwarmManager` with git worktree isolation,
security-weighted scoring, and centralized approval queue integration:

**Parallel Execution:**
- Create isolated git sandbox branches for multiple approaches
- Auto-generate approach hints based on task keywords
- Execute subagents in parallel with resource limits
- Benchmark correctness, performance, and code quality
- Compare approaches with weighted scoring
- Enable with `--parallel N` on `agent run` (read-only analysis) or swarm/tournament modes

**Status:** Beta — shipped in harness with governance gates; hosted tournament dashboards remain future work. See [maturity-matrix.md](docs/maturity-matrix.md).

### 10. Cognitive Swarm Evolution

TeaAgent includes cognitive evolution features for adaptive multi-agent systems:

Self-healing validation is described in [section 8](#8-self-healing-validation-beta) above.

**Cross-Sandbox Context Bus:**
- Real-time Delta sharing between parallel agents via WAL-mode SQLite (per-thread connections; see `docs/context-bus-and-federated-sync.md`)
- Delta cards for code changes, discoveries, errors, and context updates
- Filtered subscriptions by agent, type, and timestamp
- RAG archival helper (`ContextBus.archive_to_rag`) is available for callers; it is not auto-invoked after runs

**Evolutionary Prompt Tuning:**
- Performance-based agent prompt evolution
- LLM-powered prompt refinement with heuristic fallback
- Success metrics tracking (accuracy, speed, etc.)
- Hot-reload support for iterative improvement

**Remote JIT Approval:**
- SSE-based remote approval server for destructive tool requests
- 3-minute timeout with safe abort
- Approval queue management for multi-agent workflows
- Integration with ToolPermissionManager for enforcement

## Architecture

```
CLI / TUI  →  AgentRunner (decision loop)  →  ToolRegistry  →  Workspace Tools
                  ↕                              ↕
           LLM Adapters                  ApprovalPolicy
           (14 providers)                 (5 permission modes)
```

- **AgentRunner**: Iterates between model decisions and tool executions within budget limits.
- **ToolRegistry**: Single point of tool dispatch with schema validation and lint checks.
- **ApprovalPolicy**: Enforces permission modes before any destructive or external-effect tool runs.
- **AuditLogger**: Universal event sink — every decision, execution, and error is recorded.
- **ModelDecisionEngine**: Bridges LLM responses into structured decisions via prompt assembly and JSON parsing.
- **Workspace Tools**: File read/write, shell inspect/mutate, glob search, git status, hash-anchored editing.
- **Memory Catalog**: Three-tier memory system (Project/Personal/Auto-Memory) for persistent context with automated invalidation.
- **Intent Clarification**: Deterministic ambiguity scoring before model invocation.
- **Run Store**: Persistent JSONL run history with resumable task replay.
- **Code Mode**: Restricted Python execution with AST validation and pluggable child-process or container backends.
- **Telemetry**: OpenTelemetry spans plus audit-driven metrics sinks for run and tool lifecycle events.
- **Heartbeat**: Background audit events for run liveness monitoring and hang detection.
- **Daily Brief**: Read-only readiness cockpit with recent runs, pending approvals, harness warnings, and token/cost budget.
- **Hook System**: 8-event lifecycle (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop, SubagentStop, SessionEnd) for extensibility.
- **Plugin System**: Four extension points (Commands, Agents, Hooks, MCP Servers) compatible with Claude Code.
- **Context Compaction**: Automatic context compression at 75-92% token usage (Claude Code compatible).
- **Plan Mode**: Read-only exploration mode for safe codebase analysis with plan-before-write enforcement.
- **ACP Adapter**: Agent Client Protocol integration for VS Code, Zed, and JetBrains IDEs.
- **Multi-Agent Coordination**: TaskCoordinator for classification/routing, AgentFactory for dynamic agent generation with evolutionary prompt tuning, ToolPermissionManager for safety control, WorkflowEngine for multi-step execution with self-healing validation, ContextBus for cross-sandbox Delta sharing, JITApprovalServer for remote approval with timeout, and CentralizedApprovalQueue for aggregated subagent approvals.

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
pip install -e ".[crypto]"
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
- `security`: local dependency auditing with `pip-audit`; see
  `docs/security/dependency-audit-policy.md` for the base/dev/optional-extra
  audit split.

## Quick Start

**New to TeaAgent?** See the [Full Walkthrough](docs/USAGE.md) for step-by-step
coverage of API key setup, agent mode, TUI, approvals, and troubleshooting.

The [golden path](#golden-path-first-hour) above is the recommended first-5-minutes
flow. For deeper sessions: `teaagent daily`, `teaagent tui --setup`, `teaagent run`,
`teaagent agent resume`.

### Provider keys

Set environment variables for the providers you use:

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
export CLOUDFLARE_API_TOKEN=...
export FAKE_API_KEY=...
```

For persistent setup, copy and edit the template:

```bash
cp scripts/providers_env.zsh ~/.teaagent/providers_env.zsh
echo 'source ~/.teaagent/providers_env.zsh' >> ~/.zshrc
source ~/.zshrc
```

### Optional: Keychain Mode

For macOS Keychain integration, keep using
`~/.teaagent/provider_keys_keychain.zsh`:

```bash
cp scripts/provider_keys_keychain.zsh ~/.teaagent/provider_keys_keychain.zsh
source ~/.teaagent/provider_keys_keychain.zsh
teaagent_configure_provider_keys
```

Recommended load order:

```bash
source ~/.teaagent/providers_env.zsh
source ~/.teaagent/provider_keys_keychain.zsh
source .teaagent/env
```

### Workers AI vs AI Gateway

- Workers AI is the model inference endpoint.
- AI Gateway is an optional routing/policy layer in front of Workers AI.
- `WORKERS_AI_BASE_URL` can point to either direct Workers AI (`.../ai/v1`) or AI Gateway workers-ai provider route (`https://gateway.ai.cloudflare.com/.../workers-ai/v1`).
- For AI Gateway unified OpenAI-compatible routing, set `AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/compat` and use model names like `dynamic/default`.

## Features

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

# Daily readiness + token/cost budget
teaagent agent daily gpt "Summarize the tests" --permission-mode read-only

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

### Streaming (live feedback)

TeaAgent exposes two live streams:

1. **Agent progress** — iteration and tool-call lines (`progress on` in TUI; `teaagent agent run … --progress` on CLI; default on when stderr is a TTY).
2. **Model text** — user-visible answer text only (`stream on` in TUI; `--stream` on CLI; filters out structured decision JSON).

For scripts and IDE integrations, use **`--json-stream`** to emit normalized NDJSON events (`text_delta`, `tool_call_started`, …) on stdout, then attach with `teaagent agent attach <run_id> --follow --json-stream`.

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

1. Project: `.config/agent/skills/` (highest priority)
2. Project: `.claude/skills/`
3. Project: `.opencode/skill/`
4. Project (legacy/plural alias): `.opencode/skills/`
5. User: `~/.config/agent/skills/`
6. User: `~/.claude/skills/`
7. User: `~/.config/opencode/skills/`

You can override the discovery order in `.teaagent/config.json`:

```json
{
  "skill_search_dirs": [
    ".config/agent/skills",
    ".claude/skills",
    ".opencode/skill"
  ]
}
```

You can also choose a source profile:

```json
{
  "skill_source_profile": "default"
}
```

- `default`: `.config/agent`, `.claude`, `.opencode`
- `extended`: `default` plus `.codex`, `.gemini`, `.hermes`
- `custom`: requires `skill_search_dirs` and only uses that list

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

`teaagent agent preflight` and `teaagent agent daily` expose a `token_budget`
payload before any model call. The report estimates task, memory, context-pack,
tool-metadata, recent-run replay, and output-reserve tokens, then labels the
planned context as green/yellow/red when the model context window is known.

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
mypy teaagent/ tests/ --explicit-package-bases
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
