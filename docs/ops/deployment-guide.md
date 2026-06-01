# Deployment Guide

## Overview

TeaAgent is a governance-first AI agent harness. It runs as a local CLI/TUI process with no mandatory service dependencies beyond Python and at least one LLM provider API key. All state is stored in a `.teaagent/` subdirectory of the workspace root.

---

## System Requirements

### Python

| Requirement | Minimum | Tested |
|-------------|---------|--------|
| Python | 3.10 | 3.10, 3.11, 3.12 |

### Operating System

Linux, macOS, and Windows (WSL2 recommended on Windows) are supported. File permission hardening (0o700/0o600) requires a POSIX-compatible filesystem.

### Hardware

TeaAgent itself is lightweight; capacity is dominated by the tasks it delegates:

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 256 MB | 1 GB+ (TUI + large context) |
| Disk | 500 MB | 5 GB+ (audit logs, session history) |
| Network | Required | Stable egress to LLM provider API |

### LLM Provider

At least one of the following API keys must be available at runtime:

- `ANTHROPIC_API_KEY` — Claude (recommended)
- `OPENAI_API_KEY` — GPT models
- `GEMINI_API_KEY` — Google Gemini
- `OPENROUTER_API_KEY` — OpenRouter (multi-provider gateway)
- `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`
- No key required for local Ollama or vLLM (see [Configuration Reference](configuration-reference.md))

---

## Installation

### 1. From PyPI (standard)

```bash
pip install teaagent
```

Install optional feature groups as needed:

```bash
# Minimal — core + TUI
pip install "teaagent[tui]"

# Full-featured (recommended for daily driver use)
pip install "teaagent[tui,code-analysis,graphqlite,telemetry]"

# TOML config support (required on Python <3.11)
pip install "teaagent[config]"
```

### 2. From source

```bash
git clone https://github.com/TeaEntityLab/teaagent
cd teaagent
pip install -e ".[tui,code-analysis,graphqlite,telemetry]"
```

### 3. Verify installation

```bash
teaagent --version
teaagent doctor all
```

---

## Workspace Initialization

Each project (workspace) requires its own `.teaagent/` directory.

```bash
cd /path/to/your/project

# Interactive guided setup
teaagent setup

# Or non-interactive with explicit flags
teaagent setup \
  --provider claude \
  --permission-mode prompt \
  --write-env
```

`teaagent setup` creates:

```
.teaagent/
├── config.json          # Workspace configuration
├── audit.jsonl          # Global audit trail (created on first run)
├── runs/                # Per-run JSONL audit logs
├── sessions/            # Session focus-stack state
├── undo/                # Undo checkpoint data
└── plans/               # Stored plans
```

Directory permissions are set to `0o700`; file permissions to `0o600`.

---

## Configuration Quickstart

Create `.teaagent/config.json` manually or via `teaagent setup`:

```json
{
  "permission_mode": "prompt",
  "provider": "claude",
  "model": "claude-3-5-sonnet-latest",
  "max_iterations": 10,
  "max_tool_calls": 10
}
```

Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

See [Configuration Reference](configuration-reference.md) for the full schema.

---

## First-Run Checklist

Run these steps after installation and workspace init:

```bash
# 1. Doctor check — verifies provider reachability, config validity, git sandbox
teaagent doctor all

# 2. Model smoke test — sends a minimal prompt to your configured provider
teaagent model smoke

# 3. Tool list — confirms tool registry loaded correctly
teaagent tool list

# 4. Approval policy check — verifies permission mode is sane
teaagent approval doctor

# 5. Audit log verify — confirms audit writes work
teaagent audit list --limit 5
```

Expected output from `doctor all` when healthy:

```
[OK] graphqlite
[OK] model
[OK] providers
[OK] project
[OK] env_order
[OK] git_sandbox
```

Fix any `[FAIL]` items before proceeding.

---

## Deployment Patterns

### Developer workstation (default)

```bash
# Interactive TUI session
teaagent chat "describe your task"

# Or non-interactive one-shot
teaagent run "refactor the auth module to use JWT"
```

### CI pipeline (headless)

Set environment variables in CI secrets:

```bash
ANTHROPIC_API_KEY=...
TEAAGENT_PERMISSION_MODE=workspace-write
TEAAGENT_INTERACTIVE=0
TEAAGENT_NO_SUMMARY=0
```

Run:

```bash
teaagent run "run tests and fix any failures" \
  --permission-mode workspace-write \
  --max-iterations 20
```

### Server / daemon mode

TeaAgent is not a daemon itself. To expose it as a service:

1. Use the MCP server: `teaagent mcp serve`
2. Use the automation webhook: configure `TEAAGENT_AUTOMATION_WEBHOOK_URL` and `teaagent automation serve`
3. Use the cloud gateway: `teaagent gateway start`

For each mode, run the process under a process supervisor (systemd, supervisord, or Docker).

### Docker

```dockerfile
FROM python:3.12-slim
RUN pip install "teaagent[tui,code-analysis]"
WORKDIR /workspace
ENV TEAAGENT_INTERACTIVE=0
ENV TEAAGENT_PERMISSION_MODE=workspace-write
ENTRYPOINT ["teaagent"]
```

Mount the workspace:

```bash
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $(pwd):/workspace \
  teaagent run "your task"
```

---

## Upgrading

```bash
pip install --upgrade teaagent

# Verify
teaagent --version
teaagent doctor migration   # Check for schema migrations required
```

---

## Uninstalling

```bash
pip uninstall teaagent

# Remove workspace state (irreversible — back up first)
rm -rf /path/to/project/.teaagent

# Remove user-level state
rm -rf ~/.teaagent
```

---

## See Also

- [Configuration Reference](configuration-reference.md)
- [Operations Manual](operations-manual.md)
- [Security Hardening](security-hardening.md)
- [Troubleshooting](troubleshooting.md)
