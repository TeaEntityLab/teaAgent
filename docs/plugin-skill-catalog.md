# Plugin and Skill Compatibility Catalog

Fixture-backed reference for TeaAgent extension surfaces. Examples live under
`tests/fixtures/plugin_skill_catalog/`.

Last reviewed: **2026-05-22**

## Skill discovery paths

Default profile (first match wins by skill name):

| Order | Path | Notes |
|-------|------|-------|
| 1 | `<workspace>/.config/agent/skills/` | Project agent config |
| 2 | `<workspace>/.claude/skills/` | Claude-compatible project skills |
| 3 | `<workspace>/.opencode/skill/` | OpenCode project skills |
| 4 | `<workspace>/.opencode/skills/` | OpenCode project alias |
| 5 | `~/.config/agent/skills/` | User agent config |
| 6 | `~/.claude/skills/` | User Claude-compatible skills |
| 7 | `~/.config/opencode/skills/` | User OpenCode skills |

Extended profile adds: `.codex/skills`, `.gemini/skills`, `.hermes/skills` (project)
and matching user-global dirs. Callers may pass `preferred_dirs` for custom search roots.

Each skill package is a directory containing `SKILL.md` with YAML frontmatter
(`name`, `description` required). `REFERENCE.md` and examples are encouraged
for progressive disclosure.

## Plugin discovery paths

| Order | Path | Manifest |
|-------|------|----------|
| 1 | `<workspace>/.teaagent/plugins/` | `plugin.json` per plugin |
| 2 | `~/.config/teaagent/plugins/` | User plugins |
| 3 | `teaagent/plugins/builtin/` | Bundled plugins |

Supported `plugin.json` types: `command`, `agent`, `hook`, `mcp_server`.

## Hook events (8-event lifecycle)

Compatible with Claude Code hook names:

- `SessionStart`
- `UserPromptSubmit`
- `PreToolUse` (may veto tool calls)
- `PostToolUse`
- `PreCompact`
- `Stop`
- `SubagentStop`
- `SessionEnd`

## MCP tool metadata assumptions

TeaAgent registers MCP tools through `ToolRegistry` with:

- `name`, `description`, `input_schema`, `output_schema`
- `annotations`: `readOnlyHint`, `destructiveHint`, `idempotentHint` (optional vendor hints preserved)
- Destructive tools require approval tokens at execution time

Representative external manifests are validated in
`tests/acceptance/test_external_tool_manifest_compatibility_flow.py` and
`tests/fixtures/plugin_skill_catalog/external_mcp_tools.json`.

## Subagent delegation and isolation

Built-in tools: `subagent`, `subagent_batch` (when `--subagent` is enabled on the parent run).

| Field / arg | Meaning |
|-------------|---------|
| `isolation` | `shared` (default) or `worktree` (`container` rejected until implemented) |
| `worktree_path` | Relative path under `.teaagent/subagent-worktrees/` when `isolation=worktree` |
| Lineage | `parent_run_id`, `def_name`, `depth`, `batch_index`, `isolation` on tool results and child audit |

Worktree isolation requires a git repository; the worktree is removed when the child run completes.

## Preflight context pack

`teaagent agent preflight` embeds a read-only `context_pack` in JSON output:

| Block | Source |
|-------|--------|
| `candidate_files` | Task and `AGENTS.md` path mentions |
| `memories` | `.teaagent/memory/` catalog search |
| `symbols` | LSP document symbols when code analysis is enabled, else file stats |
| `graph_rag.sources` | Hybrid index, `.teaagent/knowledge` collection marker, `.teaagent/graphqlite.db` (read-only queries) |

`graph_rag.hits` is the deduped union across sources. No workspace writes occur while building the pack.

## Fixture examples

| Fixture | Purpose |
|---------|---------|
| `tests/fixtures/plugin_skill_catalog/sample_skill/SKILL.md` | Valid minimal skill package |
| `tests/fixtures/plugin_skill_catalog/sample_plugin/plugin.json` | Valid command plugin manifest |
| `tests/fixtures/plugin_skill_catalog/external_mcp_tools.json` | External MCP annotation compatibility |

## Known non-goals

- No CrewAI/LangGraph role DSL or graph-native orchestration in the harness
- No automatic execution of third-party hook scripts without explicit configuration
- No guarantee that every Claude Code/Codex plugin manifest field maps 1:1 (TeaAgent validates required registry fields only)
