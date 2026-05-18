---
type: documentation
audience: user, agent
status: stable
version: 1.0.0
last_audit: 2026-05-17
---
# TeaAgent Quick Start Guide

A beginner-friendly walkthrough from installation to your first agent run and chat session.

## Table of Contents

- [Installation](#installation)
- [API Key Setup](#api-key-setup)
- [Verify Your Setup](#verify-your-setup)
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

TeaAgent supports 11 LLM providers. Set environment variables for the ones you want to use:

| Provider  | Env Var                | Default Model          | Get Key                                          |
|-----------|------------------------|------------------------|--------------------------------------------------|
| claude    | `ANTHROPIC_API_KEY`    | claude-3-5-sonnet-latest | https://console.anthropic.com/settings/keys     |
| gpt       | `OPENAI_API_KEY`       | gpt-4o-mini            | https://platform.openai.com/api-keys             |
| gemini    | `GEMINI_API_KEY`       | gemini-1.5-flash       | https://aistudio.google.com/apikey                |
| openrouter| `OPENROUTER_API_KEY`   | openai/gpt-4o-mini     | https://openrouter.ai/settings/keys               |
| ollama    | `OLLAMA_API_KEY` (optional) | llama3.2         | Local server (default `http://localhost:11434/v1`) |
| vllm      | `VLLM_API_KEY` (optional) | meta-llama/Llama-3.1-8B-Instruct | Local server (default `http://localhost:8000/v1`) |
| opencodezen-go | `OPENCODEZEN_API_KEY` | deepseek-v4-flash* | https://opencode.ai/settings                      |
| mistral   | `MISTRAL_API_KEY`      | mistral-large-latest | https://console.mistral.ai/api-keys/              |
| deepseek  | `DEEPSEEK_API_KEY`     | deepseek-chat        | https://platform.deepseek.com/api-keys            |
| grok      | `XAI_API_KEY`          | grok-3-latest        | https://console.x.ai/                             |
| workers-ai | `CLOUDFLARE_API_TOKEN` (+ `CLOUDFLARE_ACCOUNT_ID` when `WORKERS_AI_BASE_URL` is unset) | @cf/meta/llama-3.1-8b-instruct | https://dash.cloudflare.com/profile/api-tokens |

\* `opencodezen-go` defaults to `deepseek-v4-flash`. You can still pass `--model` to pick another supported model.

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

### Permission Modes

Control what the agent can do:

```bash
# Read-only: inspect files, run safe commands (safest)
teaagent agent run gpt "what does main.py do" --permission-mode read-only

# Workspace-write: can create/edit files, but no shell mutation
teaagent agent run gpt "create a README" --permission-mode workspace-write

# Allow all destructive operations (use with caution)
teaagent agent run gpt "run the tests and fix failures" --allow-destructive
```

| Mode                  | File reads | File writes | Shell inspect | Shell mutate |
|-----------------------|:----------:|:-----------:|:-------------:|:------------:|
| `read-only`           | yes        | no          | yes           | no           |
| `workspace-write`     | yes        | yes         | yes           | no           |
| `prompt` *(default)*  | yes        | needs approval | yes        | needs approval |
| `allow`               | yes        | yes         | yes           | yes          |
| `danger-full-access`  | yes        | yes         | yes           | yes          |

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
| `provider <name>` | Set LLM provider (gpt, claude, gemini, openrouter, ollama, vllm, opencodezen-go) |
| `model <name>` | Override model name |
| `permission <mode>` | Set permission mode |
| `destructive on/off` | Toggle destructive tool access |
| `route-model on/off` | Toggle automatic model routing |
| `progress on/off` | Toggle audit event streaming |
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

Use an explicit model when you want one of the higher-capability `opencodezen-go` variants:

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
