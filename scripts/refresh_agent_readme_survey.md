# Agent Landscape Survey

DeepWiki- and upstream-backed review for TeaAgent competitive positioning. TeaAgent
stays a governance-first harness; this artifact tracks parity, gaps, and backlog
actions — not a second agent framework.

Last reviewed: **2026-05-22**

## Sources reviewed

| Project | DeepWiki / upstream URL | Reviewed signals | TeaAgent parity | Gap / differentiator | Backlog action |
|---------|-------------------------|------------------|-----------------|----------------------|----------------|
| OpenAI Codex | https://deepwiki.com/openai/codex | Multi execution modes, sandboxing, MCP, IDE, cloud surfaces | Tool registry, MCP HTTP/stdio, Code Mode sandbox profiles, VS Code extension | Clearer mode/safety matrix across CLI/TUI/IDE | P1 mode/safety matrix |
| Claude Code | https://deepwiki.com/anthropics/claude-code | Subagents, hooks, MCP, background sessions, permission modes, managed settings | `subagent`/`subagent_batch`, hooks, permission modes, MCP, skills | Parent-child run lineage and isolation modes not yet first-class | P1 subagent lineage |
| OpenCode | https://deepwiki.com/sst/opencode | Provider breadth, client-server, plugins, skills, MCP, desktop, VS Code | 13 providers, plugins/skills, MCP, ACP/VS Code | Multi-surface launch recipes still architecture-heavy | P1 multi-surface recipes |
| OpenHands | https://deepwiki.com/OpenHands/OpenHands | SDK/CLI/GUI/cloud/enterprise, sandbox-decoupled V1 | Managed runtime stubs, MCP, audit, Code Mode | Hosted/cloud surface docs are stub-level only | P2 dashboard refresh |
| Aider | https://deepwiki.com/Aider-AI/aider | Repo-map context, edit strategies, git workflow | Workspace tools, LSP/code-analysis, GraphQLite | No read-only “why this context” pack for planning/preflight | P1 repo-map context pack |
| LangGraph | https://deepwiki.com/langchain-ai/langgraph | Graph state, checkpoints, durable execution | `CheckpointStore`, runner limits, audit chain | No graph-native orchestration (intentional harness boundary) | Document as non-goal |
| CrewAI | https://deepwiki.com/crewAIInc/crewAI | Role-based crews, task delegation | A2A delegation, ANP governed federation | No multi-role crew DSL (intentional harness boundary) | Document as non-goal |

Additional README baselines (prior survey): Claude Code GitHub, Codex CLI GitHub,
Cursor docs, Gemini CLI, Continue — still valid for env/skill conventions.

## Implemented parity (harness core)

- [x] Tool registry with schema validation and destructive approval
- [x] Audit chain with redaction
- [x] MCP stdio + streamable HTTP
- [x] A2A discovery/delegation
- [x] ACP IDE adapter
- [x] ANP governed federation boundary (`ANPGovernedService`)
- [x] OAuth refresh-token rotation (ADR 0004)
- [x] Google managed runtime (`GoogleADKRuntime`, `VertexAgentRuntime`)
- [x] Permission modes, Plan Mode, Auto Mode, Code Mode
- [x] Provider/docs consistency acceptance (`test_provider_matrix_consistency_flow.py`)

## Next differentiators (open)

| Track | Why it matters | Backlog ID |
|-------|----------------|------------|
| Docs/provider drift guard | README/USAGE/architecture/runtime provider registry must stay aligned; shared `CLOUDFLARE_API_TOKEN` / `OPENCODEZEN_API_KEY` must not false-positive validators | P0 |
| Subagent lineage + isolation | Child runs need parent run id, depth, batch index; default shared workspace documented; worktree isolation deferred | P1 |
| Repo-map / context pack | Surfacing candidate files/symbols/memories during planning without writes | P1 |
| Mode and safety matrix | Single doc mapping permission modes, Plan/Auto/Code modes, approvals, rollback | P1 |
| Multi-surface recipes | One-command paths for CLI, TUI, VS Code, MCP, ACP, A2A, ANP, managed runtime | P1 |
| Plugin/skill catalog | Fixture-backed compatibility catalog for skills, hooks, MCP metadata | P2 |
| Use-case dashboard refresh | Regenerate matrix from this survey with review date and open-gap counts | P2 |
| Recurring survey cadence | Re-run before minor releases or new federation/protocol ADRs | P2 |

## Future API note (non-breaking)

`subagent` / `subagent_batch` should record parent-child run lineage and later
accept `isolation = shared | worktree` without breaking current callers.

## Next review trigger

Re-run this survey before the next minor release or when adding a new
federation/protocol ADR. Update `docs/backlog-priority.md` and
`docs/use-cases.md` differentiator sections when signals change.
