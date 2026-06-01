---
type: guide
audience: user, developer
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# Migration Guide

How to move to TeaAgent from Claude Code, Codex, OpenCode, or Aider,
and how to migrate between TeaAgent versions.

**Related docs:**
- [USAGE.md](../USAGE.md) — golden path quick-start
- [Use cases](use-cases.md) — scenario walkthroughs
- [API migration note](../migration-top-level-api.md) — import path changes

---

## Table of Contents

1. [From Claude Code](#1-from-claude-code)
2. [From Codex CLI](#2-from-codex-cli)
3. [From OpenCode](#3-from-opencode)
4. [From Aider](#4-from-aider)
5. [TeaAgent version upgrades](#5-teaagent-version-upgrades)
6. [Concept mapping](#6-concept-mapping)

---

## 1. From Claude Code

Claude Code and TeaAgent share a close design lineage. Most concepts map directly.

### Instruction files

| Claude Code | TeaAgent | Notes |
|-------------|----------|-------|
| `CLAUDE.md` | `AGENTS.md` | Both loaded automatically. TeaAgent also loads `CLAUDE.md` as a fallback. |
| `.claude/agents/*.md` | Subagent definitions | Declared in `.teaagent/agents/*.md` with same frontmatter format |
| `.claude/settings.json` | `.teaagent/config.json` | Different schema; see below |
| `.claude/hooks/` | `HookRegistry` (Python) | 8 events match exactly |

### Config migration

Claude Code `.claude/settings.json`:
```json
{
  "model": "claude-opus-4-8",
  "permissions": { "allow": ["Bash", "Edit"] }
}
```

Equivalent `.teaagent/config.json`:
```json
{
  "provider": "anthropic",
  "model": "claude-opus-4-8",
  "permission_mode": "workspace-write"
}
```

TeaAgent permission modes map to Claude Code permission settings:

| Claude Code | TeaAgent `permission_mode` |
|-------------|---------------------------|
| Default (prompt) | `prompt` |
| `"allow": ["Bash", "Edit", ...]` (broad) | `allow` |
| Read-only via `deny` rules | `read-only` |
| No restrictions | `danger-full-access` |

### Hooks migration

Claude Code hooks are shell scripts in `.claude/hooks/<event>/`. TeaAgent hooks are Python callables registered at session startup.

Claude Code `PreToolUse` hook (shell):
```bash
#!/bin/bash
# .claude/hooks/PreToolUse/lint.sh
if [[ "$TOOL_NAME" == "Edit" ]]; then
  ruff check "$TOOL_INPUT_PATH" || exit 2
fi
```

TeaAgent equivalent:
```python
from teaagent.hooks import post_lint_check_hook, HookRegistry
from pathlib import Path

hook_reg = HookRegistry()
hook_reg.register_post_hook(post_lint_check_hook(root=Path(".")))
```

For arbitrary shell hooks, use `shell_command_hook`:
```python
from teaagent.hooks import shell_command_hook

hook_reg.register_post_hook(
    shell_command_hook(
        "ruff check .",
        on_tools=frozenset({"workspace_write_file", "workspace_apply_patch"}),
    )
)
```

### MCP servers

Both tools use the same MCP protocol. Servers configured for Claude Code work
unchanged with TeaAgent's MCP client:

```bash
teaagent mcp serve --http --port 7330 --root .
```

### Memory

| Claude Code | TeaAgent |
|-------------|----------|
| `~/.claude/memory/` (personal) | `MemoryCatalog` with `scope="personal"` |
| `.claude/memory/` (project) | `MemoryCatalog` with `scope="project"` |
| Auto-memory | `MemoryCatalog` with `auto=True` |

```python
from teaagent.memory import MemoryCatalog
from pathlib import Path

mem = MemoryCatalog(Path("."))
mem.add("Prefer async patterns in this repo.", tags=("style",), scope="project")
```

---

## 2. From Codex CLI

### Command mapping

| Codex | TeaAgent | Notes |
|-------|----------|-------|
| `codex "task"` | `teaagent run gpt "task"` | |
| `codex -m gpt-4o "task"` | `teaagent run gpt "task" --model gpt-4o` | |
| `codex --approval-mode auto-edit "task"` | `teaagent run gpt "task" --permission-mode workspace-write` | |
| `codex --approval-mode full-auto "task"` | `teaagent run gpt "task" --permission-mode allow` | |
| `codex --quiet "task"` | `teaagent run gpt "task"` | JSON output is default |

### Protected paths

Codex automatically protects `.git/`, `.codex/`. TeaAgent enforces protected
paths via `FilePolicy`. The default policy protects `.git/`, `.teaagent/`, and
paths matching `.gitignore`.

To add custom protected paths:
```json
// .teaagent/config.json
{
  "file_policy": {
    "protected_paths": [".secrets/", "production.env"]
  }
}
```

### Sandboxing

Codex uses a `landlock` sandbox on Linux. TeaAgent supports Docker container
isolation for agent runs:

```bash
teaagent run gpt "task" --sandbox docker --root .
```

Or via `ContainerCodeModeBackend` in Python.

---

## 3. From OpenCode

### Surface mapping

| OpenCode | TeaAgent |
|----------|----------|
| Interactive TUI (`opencode`) | `teaagent tui` |
| `/plan` slash command | `teaagent plan gpt "task"` |
| Read-only plan agent | `--permission-mode read-only` |
| LSP integration | `CodeAnalysisConfig` + `LSPServerManager` |
| Client–server mode | `teaagent mcp serve --http` |

### LSP migration

OpenCode's LSP integration is replicated in TeaAgent via `CodeAnalysisConfig`:

```python
from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.code_analysis import CodeAnalysisConfig, LSPServerConfig
from pathlib import Path

config = ChatAgentConfig(
    root=Path("."),
    code_analysis_config=CodeAnalysisConfig(
        enabled=True,
        lsp_servers=[
            LSPServerConfig(language="python", command=["pylsp"]),
            LSPServerConfig(language="typescript", command=["typescript-language-server", "--stdio"]),
        ],
    ),
)
```

### Plan-before-write

OpenCode's plan/execute separation maps to TeaAgent's `--from-plan` flag:

```bash
# OpenCode: /plan then confirm
# TeaAgent:
teaagent plan gpt "refactor auth module" --root .
teaagent run gpt --from-plan .teaagent/plans/refactor-auth.md --permission-mode workspace-write --root .
```

---

## 4. From Aider

### Command mapping

| Aider | TeaAgent |
|-------|----------|
| `aider --model gpt-4o` | `teaagent tui` (select model in config) |
| `aider --read file.py` | Start session; agent reads files as needed |
| `aider --no-auto-commits` | (default; commit via `git_commit` tool explicitly) |
| `aider --dry-run` | `teaagent plan gpt "task"` |
| `/undo` | `teaagent agent undo --last` |
| `/diff` | `git diff` (TeaAgent writes to git worktree) |

### Key differences

- **Context management:** Aider requires you to `/add` files manually. TeaAgent builds a context pack automatically via `context_pack` preflight and the hybrid search backend.
- **Commit style:** Aider auto-commits each change. TeaAgent accumulates changes in the workspace; you commit when ready (or configure `git_commit` tool with auto-approve).
- **Cost tracking:** TeaAgent tracks session cost in real time in the TUI footer and persists it in `.teaagent/runs/`.

---

## 5. TeaAgent Version Upgrades

### Upgrading the package

```bash
uv pip install --upgrade teaagent
# or
pip install --upgrade teaagent
```

After upgrading, validate your workspace:

```bash
teaagent doctor --root .
teaagent doctor model gpt
```

### Import path changes (0.x → 1.x)

The top-level `teaagent` namespace was narrowed in 1.x. See [migration-top-level-api.md](../migration-top-level-api.md) for the full list.

Quick reference for commonly affected imports:

```python
# Before (star import, 0.x)
from teaagent import KnowledgeGraph, LLMMessage, TelemetryConfig

# After (explicit submodule imports, 1.x)
from teaagent.graph_rag import KnowledgeGraph
from teaagent.llm import LLMMessage
from teaagent.telemetry import TelemetryConfig
```

### Audit log schema migration

If you have existing `.teaagent/runs/*.jsonl` files, run the schema migration tool:

```bash
teaagent db migrate --root .
```

This is idempotent and preserves all existing events.

### Config schema changes

Check for deprecated config keys:

```bash
teaagent config validate --root .
```

Warnings list deprecated keys and their replacements.

---

## 6. Concept Mapping

Quick reference across tools:

| Concept | Claude Code | Codex | OpenCode | Aider | TeaAgent |
|---------|------------|-------|----------|-------|----------|
| Project instructions | `CLAUDE.md` | `AGENTS.md` | — | `.aider.conf.yml` | `AGENTS.md` / `CLAUDE.md` |
| Permission model | Settings `allow/deny` | `--approval-mode` | Plan/Edit split | `--yes` | `PermissionMode` |
| Hooks | `.claude/hooks/` (shell) | — | — | — | `HookRegistry` (Python) |
| Session cost | Footer | — | — | Reported | TUI footer + audit log |
| Undo | `/undo` | — | — | `/undo` | `teaagent agent undo` |
| Memory | Three-tier CLAUDE.md | — | — | — | `MemoryCatalog` |
| Plugin system | Commands/Agents/MCP | — | — | — | `teaagent.tools` entry-points |
| Sub-agents | `.claude/agents/` | Threads | — | — | `.teaagent/agents/` |
| Audit trail | — | — | — | Git history | `.teaagent/runs/*.jsonl` |
| Context pack | Auto | — | Repo-map | `/add` | `context_pack` preflight |
| IDE integration | ACP | — | Client–server | — | `teaagent mcp serve` |

---

## See Also

- [Use cases](use-cases.md) — what TeaAgent can do, with examples
- [Integration guide](integration-guide.md) — connecting new providers and tools
- [Architecture](../architecture.md) — system overview
