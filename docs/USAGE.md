---
type: documentation
audience: user, agent
status: stable
version: 1.0.0
last_audit: 2026-05-17
---
# TeaAgent Quick Start Guide

A beginner-friendly walkthrough from installation to your first agent run and chat session.

**Docs map:** This file is the guided walkthrough. [README.md](../README.md) is the short golden path. [cli.md](cli.md) is the command reference.

## Golden path

Copy this sequence for a new repository (replace `gpt` with your provider):

```bash
pip install -e .
teaagent setup --root . --provider gpt --permission-mode read-only --write-env
teaagent daily "summarize this repo" --dry-run --root . --human
teaagent run "summarize the test suite" --permission-mode read-only --root .
```

- Use `--human` on `daily` and `setup` for readable summaries; omit it for JSON (automation default).
- After setup, `provider` is optional on `daily`, `run`, and top-level shortcuts when `.teaagent/config.json` exists.

**Advanced paths** (not part of the golden path): `teaagent init`, `teaagent doctor providers --wizard`, manual `providers_env.zsh`, Keychain scripts, per-provider env exports — see [Recovery recipes](#recovery-recipes) and [API Key Setup](#api-key-setup).

## Setup model

TeaAgent matches common agent-setup practice in five layers:

| Layer | What it is | TeaAgent surface |
|-------|------------|------------------|
| Project bearings | Durable repo rules | `AGENTS.md` (created or preserved by `teaagent setup`) |
| Safety boundary | What tools may do | Permission modes: `read-only`, `workspace-write`, `prompt`, `allow` |
| Visibility | Context, cost, readiness | `teaagent daily`, `teaagent preflight`, `--human` summaries |
| Capabilities | Extra tools | Skills, plugins, `teaagent mcp serve`, workspace tools |
| Continuity | What happened last time | Audit log, `teaagent runs`, `teaagent resume` |

Typical progression: **setup → daily (readiness) → read-only run → workspace-write or prompt when editing**.

## Recovery recipes

### Provider missing or wrong

```bash
teaagent setup --root . --provider gpt --write-env
teaagent doctor model gpt
```

### Workspace not configured

```bash
teaagent setup --root . --permission-mode read-only
# or inside TUI: setup write-env
```

### Daily dry-run says not ready

```bash
teaagent daily "readiness" --dry-run --human --root .
```

Read **Blocking** vs **Warning** vs **Info** in the output. Permission errors on `.git` in a sandbox are often informational — retry in a writable temp directory:

```bash
teaagent setup --root /tmp/teaagent-try --provider gpt --api-key "$OPENAI_API_KEY"
teaagent daily "readiness" --dry-run --human --root /tmp/teaagent-try
```

### Need MCP or IDE tools

```bash
teaagent doctor mcp --wizard --root .
teaagent mcp serve --http --port 7330 --root .
```

### Prefer TUI over CLI

```bash
teaagent tui --setup --root .
# then: setup write-env | daily | ask | runs
```

## Table of Contents

- [Golden path](#golden-path)
- [Setup model](#setup-model)
- [Recovery recipes](#recovery-recipes)
- [Installation](#installation)
- [API Key Setup](#api-key-setup)
- [Verify Your Setup](#verify-your-setup)
- [Daily Use](#daily-use)
- [Choose Your Surface](#choose-your-surface)
- [Agent Mode (CLI)](#agent-mode-cli)
- [Chat Mode (TUI)](#chat-mode-tui)
- [Handling Approvals](#handling-approvals)
- [Choosing a Model](#choosing-a-model)
- [Common Problems](#common-problems)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional: install richer TUI line editing/history support:

```bash
pip install -e ".[tui]"
```

Verify it works:

```bash
teaagent --help
```

## API Key Setup

TeaAgent supports 13 LLM providers. Set environment variables for the ones you want to use:

| Provider  | Env Var                | Default Model          | Get Key                                          |
|-----------|------------------------|------------------------|--------------------------------------------------|
| claude    | `ANTHROPIC_API_KEY`    | claude-3-5-sonnet-latest | https://console.anthropic.com/settings/keys     |
| gpt       | `OPENAI_API_KEY`       | gpt-4o-mini            | https://platform.openai.com/api-keys             |
| gemini    | `GEMINI_API_KEY`       | gemini-1.5-flash       | https://aistudio.google.com/apikey                |
| openrouter| `OPENROUTER_API_KEY`   | openai/gpt-4o-mini     | https://openrouter.ai/settings/keys               |
| ollama    | `OLLAMA_API_KEY` (optional) | llama3.2         | Local server (default `http://localhost:11434/v1`) |
| vllm      | `VLLM_API_KEY` (optional) | meta-llama/Llama-3.1-8B-Instruct | Local server (default `http://localhost:8000/v1`) |
| opencodezen | `OPENCODEZEN_API_KEY` | deepseek-v4-flash-free* | https://opencode.ai/settings                      |
| opencodezen-go | `OPENCODEZEN_API_KEY` | deepseek-v4-flash* | https://opencode.ai/settings                      |
| mistral   | `MISTRAL_API_KEY`      | mistral-large-latest | https://console.mistral.ai/api-keys/              |
| deepseek  | `DEEPSEEK_API_KEY`     | deepseek-chat        | https://platform.deepseek.com/api-keys            |
| grok      | `XAI_API_KEY`          | grok-3-latest        | https://console.x.ai/                             |
| workers-ai | `CLOUDFLARE_API_TOKEN` (+ `CLOUDFLARE_ACCOUNT_ID` when `WORKERS_AI_BASE_URL` is unset) | @cf/meta/llama-3.1-8b-instruct | https://dash.cloudflare.com/profile/api-tokens |
| aigateway | `CLOUDFLARE_API_TOKEN` (+ `AIGATEWAY_BASE_URL` optional) | openai/gpt-4o-mini | https://dash.cloudflare.com/profile/api-tokens |

\* `opencodezen` defaults to `deepseek-v4-flash-free`, `opencodezen-go` defaults to `deepseek-v4-flash`. You can still pass `--model` to pick another supported model.

### Lazy Setup (Recommended)

Copy and source the provided key template:

```bash
cp scripts/providers_env.zsh ~/.teaagent/providers_env.zsh
# Edit the file and fill in your keys
${EDITOR:-vi} ~/.teaagent/providers_env.zsh

# Add to your shell profile (~/.zshrc):
echo 'source ~/.teaagent/providers_env.zsh' >> ~/.zshrc
source ~/.zshrc
```

Use `.teaagent/env` for per-project overrides. Load it after global defaults:

```bash
source .teaagent/env
```

### Optional: macOS Keychain Setup

If you use `~/.teaagent/provider_keys_keychain.zsh` for Keychain integration, configure
or rotate saved keys with:

```bash
cp scripts/provider_keys_keychain.zsh ~/.teaagent/provider_keys_keychain.zsh
source ~/.teaagent/provider_keys_keychain.zsh
teaagent_configure_provider_keys
```

Suggested load order:

```bash
source ~/.teaagent/providers_env.zsh
source ~/.teaagent/provider_keys_keychain.zsh
source .teaagent/env
```

Workers AI vs AI Gateway:
- Workers AI is the inference provider endpoint.
- AI Gateway is an optional policy/routing layer in front of Workers AI.
- `WORKERS_AI_BASE_URL` accepts either a direct Workers AI endpoint (`.../ai/v1`) or a Gateway compat endpoint (`https://gateway.ai.cloudflare.com/.../workers-ai/v1`).
- For AI Gateway unified OpenAI-compatible routing, set `AIGATEWAY_BASE_URL=https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/compat` and use model names like `dynamic/default`.

### Manual Setup

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
export OLLAMA_BASE_URL="http://localhost:11434/v1"
export VLLM_BASE_URL="http://localhost:8000/v1"
export WORKERS_AI_BASE_URL="https://api.cloudflare.com/client/v4/accounts/<account_id>/ai/v1"
# Optional when using AI Gateway authenticated mode:
# export WORKERS_AI_EXTRA_HEADERS='{"cf-aig-authorization":"Bearer <gateway_token>"}'
# ... etc
```

Network/TLS environment variables are also supported:

```bash
export HTTPS_PROXY="http://proxy.internal:8080"
export REQUESTS_CA_BUNDLE="/path/to/ca-bundle.pem"
export SSL_CERT_FILE="/path/to/ca-bundle.pem"
export TEAAGENT_TLS_CLIENT_CERT="/path/to/client.crt"
export TEAAGENT_TLS_CLIENT_KEY="/path/to/client.key"
```

### Override Default Models

Set environment variables to change the default model per provider:

```bash
export CLAUDE_MODEL="claude-3-5-sonnet-latest"
export GPT_MODEL="gpt-4o"
export GEMINI_MODEL="gemini-2.0-flash"
export OPENROUTER_MODEL="anthropic/claude-3.5-sonnet"
```

Or override with `--model` on the command line (see below).

## Verify Your Setup

Check that your key is detected:

```bash
teaagent doctor model gpt
teaagent doctor model claude
teaagent doctor model ollama
teaagent doctor model vllm
teaagent doctor model opencodezen
teaagent doctor model opencodezen-go
teaagent doctor model workers-ai
teaagent doctor model gpt --wizard
# Guided Cloudflare AI Gateway + Workers AI check
teaagent doctor aigateway
# Guided provider/project/MCP setup
teaagent doctor providers --wizard
teaagent doctor providers --wizard --provider gpt --provider workers-ai --write-env --root .
teaagent doctor project --wizard --root .
teaagent doctor mcp --wizard --root .
```

Send a test prompt:

```bash
teaagent model smoke gpt --prompt "Reply with exactly: ok"
```

## Daily Use

Use this section as the everyday entry point. Competitive agent products converge on the
same habit: a **simple start ritual**, **visible safety/cost/context state**, **reliable
resume**, and **short task recipes** — not a larger framework.

### Start here every morning

Recommended first command (read-only, no model call):

```bash
teaagent agent daily gpt "what I want to do today" --permission-mode read-only --root .
```

`agent daily` returns harness health, recent runs, pending approvals, token budget
(green/yellow/red pressure), read-only `context_pack` evidence, and `recommendations`
with the next safest command. Follow with `agent preflight` when you need routing and
clarification only, or `agent run` when you are ready to execute.

### Safe defaults

- Default to **`read-only`** for exploration, architecture questions, and code review.
- Use **`workspace-write`** when you intend to edit files but still want shell mutation blocked.
- Use **`prompt`** for day-to-day autonomous work; approve destructive tools explicitly.
- Reserve **`allow`** / **`danger-full-access`** for trusted automation only.
- Prefer **`agent daily`** and **`--context-profile lean`** when token pressure is yellow/red.

### Three everyday modes

| Mode | Permission flag | When to use |
|------|-----------------|-------------|
| **Inspect** | `--permission-mode read-only` | Summaries, diffs, architecture, preflight/daily checks |
| **Edit** | `--permission-mode workspace-write` | Patch files, docs, tests; no shell mutation |
| **Autonomous** | `--permission-mode prompt --heartbeat 5` | Multi-step fixes with approvals and liveness signals |

### Everyday task recipes

| Task | Suggested flow |
|------|----------------|
| **Summarize repo** | `agent daily gpt "summarize repo" --context-profile lean` → `agent run gpt "..." --permission-mode read-only` |
| **Review diff** | `agent daily gpt "review my changes" --context-profile balanced` → `agent run gpt "review unstaged diff" --permission-mode read-only` |
| **Fix failing test** | `agent preflight gpt "fix failing test X"` → `agent run gpt "..." --permission-mode workspace-write` |
| **Write docs** | `agent run gpt "update README for daily workflow" --permission-mode workspace-write` |
| **Inspect architecture** | `agent daily gpt "map auth flow" --context-profile deep` → read-only `agent run` |
| **Resume previous run** | `agent daily gpt "continue auth refactor"` → `agent status <run_id>` → `agent resume gpt <run_id>` |
| **Safe cleanup** | `agent run gpt "list temp files to remove" --permission-mode read-only` → `prompt` only if deletes are needed |

CLI examples:

```bash
teaagent agent daily gpt "review auth flow" --context-profile lean
teaagent agent daily gpt "plan test fix" --context-profile balanced
teaagent agent daily gpt "map subsystem boundaries" --context-profile deep
teaagent agent preflight gpt "fix tests/test_foo.py" --route-model
teaagent agent run gpt "fix tests/test_foo.py" --permission-mode workspace-write
```

### Token balancing (`--context-profile`)

| Profile | Best for | Effect |
|---------|----------|--------|
| `lean` | Quick checks, status, small questions | Fewer memories, no LSP/graph search, smaller output reserve |
| `balanced` | Normal daily work (default) | Standard memory + context pack + recent-run replay |
| `deep` | Architecture / research sessions | More memories, LSP hydration, graph search, larger output reserve |

`token_budget` in daily/preflight JSON shows estimated input tokens, cost, and which
contributors dominate (task, memories, context pack, tools, replay).

### TUI-first interactive loop

```bash
teaagent tui --root . --permission-mode prompt
```

Then at the prompt:

```text
daily what I want to do today
preflight review this patch for regressions
ask summarize the test suite
runs
show <run_id>
resume <run_id>
status <run_id>
```

Order of operations: **`daily`** (cockpit) → **`preflight`** (clarify/route/tools) → **`ask`** (run) → **`runs` / `resume`** (continuity).

### Long-running and background work

```bash
teaagent agent run gpt "long refactor" --permission-mode prompt --heartbeat 5 --root .
teaagent agent status <run_id> --root .
teaagent agent resume gpt <run_id> --root .
```

Heartbeat events land in the run audit log so observers can confirm liveness without
polling the model.

### CLI vs TUI

| Prefer CLI when | Prefer TUI when |
|-----------------|-----------------|
| Scripting, CI, copy/paste recipes | Multi-turn chat, memory, approvals in one session |
| You want JSON from `daily` / `preflight` | You want `daily` → `ask` → `resume` without leaving the terminal |

See [cli.md](cli.md#preflight-and-daily-brief) for flags and JSON fields.

## Choose Your Surface

Pick one entry point for how you work with TeaAgent. Each surface shares the same
tool registry, permission modes, and audit model — only the transport changes.

<!-- SURFACE_RECIPES:START -->

| Surface | Best for | One-command recipe |
|---------|----------|-------------------|
| **CLI agent** | Scripts, CI, single-shot tasks | `teaagent agent run gpt "Summarize tests" --permission-mode read-only --root .` |
| **TUI** | Interactive multi-turn chat in the terminal | `teaagent tui --root . --permission-mode prompt` |
| **VS Code** | Palette commands, integrated terminal, MCP attach | Open `vscode/` in the editor → Command Palette → **TeaAgent: Run Agent** or **TeaAgent: Start MCP Server** (runs `teaagent mcp serve --http`) |
| **MCP (stdio)** | Desktop MCP clients over stdin/stdout | `teaagent mcp serve --root .` |
| **MCP (HTTP)** | Loopback HTTP clients (IDE, browser tools) | `teaagent mcp serve --http --port 7330 --root .` |
| **ACP** | IDE Agent Client Protocol (stdio JSON-RPC lines) | `run_acp_server(...)` emits `session/update` progress (tool calls, text chunks) during `session/prompt`; see `teaagent/acp_adapter.py` |
| **A2A** | Federated discovery + remote task delegation | Python API: `A2ADiscoveryServer(card, port=7331)` serves `/.well-known/agent.json` and `POST /a2a/task` |
| **ANP** | Governed cross-organization federation | Python API: `ANPGovernedService(...)` inbound/outbound with approval + audit — see [ADR 0007](adr/0007-anp-adapter-boundary.md) |
| **Managed runtime** | Provider-hosted agent backends (stubs) | Python API: `ManagedAgentRunner(runtime).run(task, audit_logger=audit)` — see `teaagent/managed_runtime.py` |

Related CLI helpers:

```bash
teaagent agent card --root .          # AgentCard JSON for A2A discovery
teaagent agent preflight gpt "task"   # Clarify/route/tools + read-only context_pack
teaagent agent daily gpt "task"       # Daily readiness + token/cost budget cockpit
teaagent agent run gpt "delegate" --subagent --max-subagent-depth 1 --root .
```

Preflight and daily JSON include `token_budget` with green/yellow/red context
pressure, estimated cost, and contributor breakdown. `agent daily` also rolls up
recent runs, pending approvals, harness warnings, optional index availability, and
the next safest command. `--context-profile lean|balanced|deep` tunes memory,
LSP hydration, graph search, run replay, and output reserve for read-only planning.

Preflight JSON includes `context_pack` (candidate files, memories, optional LSP symbols,
and read-only graph hits). Subagent tools accept `isolation: shared` (default),
`worktree` (detached git worktree), or `container` (workspace snapshot under
`.teaagent/subagent-containers/`).

### Smoke-check (local, no model API)

Verify install and workspace wiring without network calls:

```bash
teaagent model providers
teaagent agent card --root .
teaagent workspace tools
teaagent agent preflight gpt "list workspace tools" --root .
teaagent agent daily gpt "list workspace tools" --root .
```

VS Code extension (local build):

```bash
cd vscode && npm install && npm run compile
# Command Palette → TeaAgent: Run Doctor
```

See also: [CLI reference](cli.md), [architecture](architecture.md), [examples/README.md](../examples/README.md).

<!-- SURFACE_RECIPES:END -->

## Agent Mode (CLI)

Run a single task and get a result:

```bash
# Basic: inspect-only (safest, no file writes)
teaagent agent run gpt "Summarize this repository"
```

### The Most Common Mistake

The task text is a **positional argument**, not a `--task` flag. These are wrong:

```bash
# WRONG: --task is not a valid flag
teaagent agent run gpt --task "do something"

# WRONG: the word "task" becomes the literal task text
teaagent agent run gpt task "do something"
```

This is correct:

```bash
# CORRECT: task text goes directly after the provider name
teaagent agent run gpt "do something"
```

### Using a Specific Model

Use `--model` when you want to override defaults:

```bash
teaagent agent run --model deepseek-v4-flash opencodezen-go "list all Python files"
teaagent agent run --model gpt-4o gpt "explain the architecture"
teaagent agent run --model gemini-2.0-flash gemini "search for TODO comments"
```

## Mode and Safety Comparison Matrix

TeaAgent layers **permission modes** (session policy), **execution lanes** (plan/auto/code),
and **cross-cutting controls** (approvals, audit, rollback). Use this table to pick a safe
default before enabling automation.

<!-- MODE_SAFETY_MATRIX:START -->

### Permission modes (`--permission-mode`)

Session-scoped `ApprovalPolicy` gates destructive workspace tools. Non-destructive reads
and inspect-only shell commands are always allowed unless Plan Mode or Auto Mode adds
extra blocks.

| Mode | File reads | File writes | Shell inspect | Shell mutate | Approvals | Audit | Rollback |
|------|:----------:|:-----------:|:-------------:|:------------:|:---------:|:-----:|:--------:|
| `read-only` | yes | no | yes | no | not needed (blocked) | per-run JSONL | `UndoJournal.restore()` when journal attached |
| `workspace-write` | yes | yes (write/patch/hash-edit) | yes | no | not needed for allowed writes | per-run JSONL | `UndoJournal.restore()` when journal attached |
| `prompt` *(default)* | yes | yes after approval/token | yes | yes after approval/token | HITL or `--approve-call-id` / `--allow-destructive` | per-run JSONL | `UndoJournal.restore()` when journal attached |
| `allow` | yes | yes | yes | yes | session-wide allow destructive | per-run JSONL | `UndoJournal.restore()` when journal attached |
| `danger-full-access` | yes | yes | yes | yes | same as `allow`; trusted automation only | per-run JSONL | `UndoJournal.restore()` when journal attached |

CLI examples:

```bash
teaagent agent run gpt "what does main.py do" --permission-mode read-only
teaagent agent run gpt "create a README" --permission-mode workspace-write
teaagent agent run gpt "run tests and patch failures" --permission-mode prompt --hitl-approval
teaagent agent run gpt "approved automation" --permission-mode allow
```

### Execution lanes (orthogonal to permission mode)

| Lane | Purpose | Workspace file writes | Shell inspect | Shell mutate | Approvals | Audit | Rollback |
|------|---------|:---------------------:|:-------------:|:------------:|:---------:|:-----:|:--------:|
| **Plan Mode** | Read-only exploration before editing; CLI uses `--permission-mode read-only` and sets `run_mode: planning` in run metadata | no | yes | no | destructive tools blocked | per-run JSONL | N/A (no mutations) |
| **Auto Mode** | Fully autonomous runs with hard budgets (`AutoModeConfig` on `ChatAgentConfig` / `AgentRunner`) | follows permission mode; default denies `workspace_run_shell_mutate` | follows permission mode | denied by default | auto-approves allowed tools; no HITL prompts | per-run JSONL + `auto_mode` summary metadata | `UndoJournal` if attached; optional `auto_commit` on success |
| **Code Mode** | Restricted Python execution via `execute_code_mode()` — AST allow-list, no imports; separate from workspace agent tools | no (isolated sandbox) | no | no (not workspace shell) | not applicable (not workspace destructive tools) | `sandbox_profile_selected` / `sandbox_violation` events when `audit_logger` passed | revert sandbox side effects only; does not journal workspace files |

- **Plan Mode** API: `teaagent.plan_mode.PlanMode` blocks writes/shell programmatically; CLI planning lane is `--permission-mode read-only`.
- **Auto Mode** API: enable `AutoModeConfig(enabled=True)` with iteration/tool/cost/time ceilings.
- **Code Mode** API: `execute_code_mode(..., profile=SandboxProfile.LOCAL|CI|PRODUCTION)` with child-process or container backends (see [architecture.md](architecture.md) and ADR 0003).

### Cross-cutting controls

| Control | What it does | When it applies |
|---------|--------------|-----------------|
| **Approvals** | `ApprovalPolicy` + optional HITL handler; destructive tools need `call_id` match in `prompt` mode | All workspace agent runs |
| **Audit** | Hash-chained JSONL under `.teaagent/runs/<run_id>.jsonl` with secret redaction | Every agent run and tool call |
| **Rollback** | `UndoJournal` audit sink captures pre-write bytes; `restore()` reverts touched paths (optional `.teaagent/undo.jsonl` persistence) | Workspace write tools during a run |
| **Subagent** | `subagent` / `subagent_batch` delegate child runs with lineage (`parent_run_id`, `depth`, `batch_index`, `isolation`, optional `worktree_path` / `container_path`); `shared` uses parent root, `worktree` uses a detached git worktree, `container` uses a gitignore-respecting snapshot | Parent runs with `--subagent` and depth budget |
| **Preflight** | `agent preflight` returns read-only `context_pack` evidence (paths, memories, optional LSP symbols, hybrid/knowledge/GraphQLite graph hits) without model calls or workspace writes | Planning and routing before `agent run` |

Inspect audit and forensics:

```bash
teaagent agent show <run_id> --root .
cat .teaagent/runs/<run_id>.jsonl
```

<!-- MODE_SAFETY_MATRIX:END -->

### Permission Modes (quick reference)

See the matrix above for the full comparison. Short defaults:

| Mode | Behavior |
|------|----------|
| `read-only` | Blocks all destructive tools |
| `workspace-write` | Allows file writes; blocks shell mutation |
| `prompt` | Destructive tools pause for HITL approval or require an approval token |
| `allow` | Allows destructive tools for the session |
| `danger-full-access` | Full access; reserve for trusted automation |

## Chat Mode (TUI)

Interactive multi-turn conversation with persistent history.

### Start a Session

```bash
teaagent tui
```

If `prompt-toolkit` is installed (`pip install -e ".[tui]"`), the TUI uses enhanced history/autosuggest. Without it, TUI still works via standard `input()` fallback.

### Enabling Chat Mode

Inside the TUI, type:

```
chat on
```

In chat mode, `ask` commands maintain conversation context across turns. Without chat mode, each `ask` is independent.

When chat mode is on and the agent completes successfully, you see the answer as plain text. Errors are shown as JSON with an `error` field.

### Example Chat Session

```
teaagent> provider opencodezen-go
provider: opencodezen-go

teaagent> model deepseek-v4-flash
model: deepseek-v4-flash

teaagent> chat on
chat: on (session: a1b2c3d4)

teaagent> ask what files are in this project?
[agent lists files...] [tool calls...]

teaagent> ask which ones are test files?
[agent answers using context from previous turn]
```

### TUI Quick Reference

| Command | Description |
|---------|-------------|
| `chat on` / `chat off` | Enable/disable multi-turn context |
| `session new` | Start a fresh chat session |
| `session list` | Show saved sessions |
| `session switch <id>` | Switch to a saved session |
| `ask <task>` | Run an agent task |
| `ask --clarify <task>` | Run with ambiguity check first |
| `provider <name>` | Set LLM provider (gpt, claude, gemini, openrouter, ollama, vllm, opencodezen, opencodezen-go) |
| `model <name>` | Override model name |
| `permission <mode>` | Set permission mode |
| `destructive on/off` | Toggle destructive tool access |
| `route-model on/off` | Toggle automatic model routing |
| `progress on/off` | Toggle audit event streaming (default **on**) |
| `stream on/off` | Stream user-visible final-answer text (not raw decision JSON) |
| `root <path>` | Set workspace root directory |
| `runs` | List persisted agent runs |
| `show <run_id>` | Show a run detail |
| `approve <call_id>` | Approve a pending destructive tool call |
| `memory add <text>` | Add a workspace memory |
| `memory search <text>` | Search memories |
| `doctor` | Diagnose setup issues |
| `exit` | Quit |

## Handling Approvals

When the agent wants to do something destructive (write a file, run a shell command) and you're in `prompt` mode (the default), the run pauses with `status: "pending_approval"`.

### Option 1: Resume with Approval (Recommended)

```bash
# The paused run shows a call_id in the approval payload
teaagent agent resume opencodezen-go <run_id> --approve-call-id 1
```

### Option 2: Allow All Destructive Tools

```bash
teaagent agent run gpt "create a script" --allow-destructive
```

### Option 3: Interactive Approval in TUI

```bash
teaagent tui --hitl-approval
# Then use: ask create a script
# Agent will prompt y/N before destructive operations
```

### Option 4: Pre-approve Specific Call IDs

If you know the call ID the model will use:

```bash
teaagent agent run gpt "create download_file.py" --approve-call-id 1
```

## Choosing a Model

### Provider-Default Models

Each provider has a default model. Without `--model`, the default is used:

```bash
teaagent agent run gpt "task"           # uses gpt-4o-mini
teaagent agent run claude "task"        # uses claude-3-5-sonnet-latest
teaagent agent run gemini "task"        # uses gemini-1.5-flash
```

### Available Models for opencodezen-go

The `opencodezen-go` provider at `https://opencode.ai/zen/go/v1` supports these models:

| Model | Notes |
|-------|-------|
| `deepseek-v4-pro` | |
| `deepseek-v4-flash` | Fast, good for most tasks |
| `kimi-k2.6` | |
| `kimi-k2.5` | |
| `minimax-m2.7` | |
| `minimax-m2.5` | |
| `glm-5.1` | |
| `glm-5` | |
| `qwen3.6-plus` | |
| `qwen3.5-plus` | |
| `mimo-v2-pro` | |
| `mimo-v2-omni` | |
| `mimo-v2.5-pro` | |
| `mimo-v2.5` | |
| `hy3-preview` | |

To pick a specific `opencodezen-go` model explicitly:

```bash
teaagent agent run --model deepseek-v4-flash opencodezen-go "your task"
```

### Automatic Model Routing

Let TeaAgent pick the best model for the task category:

```bash
teaagent agent run gpt "review this patch" --route-model
```

Routes tasks into categories (review, test, code, docs, search, general) and selects a provider-specific model.

### Pluggable Retrieval and Code Parse Backends

TeaAgent now supports adapter-based backend routing for knowledge retrieval and
code navigation:

- `workspace_knowledge_index` / `workspace_knowledge_search` route through
  `KnowledgeSearchBackend` implementations.
- `workspace_code_parse` routes `health`, `overview`, `symbols`, `definition`,
  and `references` actions through `CodeParseBackend` implementations.
- `backend=auto` on knowledge tools enables primary-then-fallback behavior
  (for example, external `qmd` adapter first, local fallback second).

This keeps integrations flexible for qmd/cx/codegraph-like ecosystems without
hard-coding one external tool.

## Common Problems

### "unrecognized arguments: --task"

You wrote `--task "..."` but the task is a positional argument:

```bash
# Wrong
teaagent agent run gpt --task "do something"

# Correct
teaagent agent run gpt "do something"
```

### "opencodezen-go response missing text content"

TeaAgent extracts text from standard `message.content`, content-part lists (`text` / `output_text` types), `choices[0].text`, top-level `output_text`, `message.reasoning_content`, and nested `result.output_text` shapes.

If extraction still fails, use an explicit model when you want one of the higher-capability `opencodezen-go` variants:

```bash
teaagent agent run --model deepseek-v4-flash opencodezen-go "your task"
```

### Status "pending_approval"

The agent paused because it wants to use a destructive tool (file write, shell command) in `prompt` mode. Either:

1. Resume with `--approve-call-id`: `teaagent agent resume <provider> <run_id> --approve-call-id <call_id>`
2. Re-run with `--allow-destructive`
3. Re-run with `--permission-mode workspace-write` (allows file writes but not shell mutation)

### Status "failed:system"

General system errors. Check the audit log for details:

```bash
teaagent agent show <run_id> --root .
```

Or read the JSONL directly:

```bash
cat .teaagent/runs/<run_id>.jsonl
```

Common causes:
- **Empty model response**: Model returned no content. Try a different model or rephrase the task.
- **Tool execution error**: A tool raised an exception. The agent will try to recover automatically; if it cannot, check the error message in the audit log.
- **API key missing or invalid**: Run `teaagent doctor model <provider>`.

### Status "failed:model_logic"

The model produced an invalid response (e.g., malformed JSON). Try:
- A different model with `--model`
- Simplifying the task description
- Using `--clarify` to make the task more specific

### Symlinked Files Not Appearing

The `workspace_list_files` and `workspace_search_text` tools skip symbolic links that point outside the workspace root (e.g., `.venv/bin/python`). This is intentional to prevent path traversal issues.

### Chat Mode Output

In chat mode, successful responses appear as plain text. Non-chat mode and errors always appear as JSON.

```
# Chat mode ON + success:
note read

# Chat mode ON + error:
{"status": "failed:system", "error": "...", ...}

# Chat mode OFF (always JSON):
{"status": "completed", "final_answer": "note read", ...}
```

## Next Steps

- Full CLI reference: [docs/cli.md](cli.md)
- Architecture: [docs/architecture.md](architecture.md)
- Tool authoring: [docs/tool-authoring.md](tool-authoring.md)
- Provider authoring: [docs/provider-authoring.md](provider-authoring.md)
