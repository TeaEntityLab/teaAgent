# Agent Landscape Survey

DeepWiki- and upstream-backed review for TeaAgent competitive positioning. TeaAgent
stays a governance-first harness; this artifact tracks parity, gaps, and backlog
actions — not a second agent framework.

Last reviewed: **2026-05-22**

## Sources reviewed

| Project | DeepWiki / upstream URL | Reviewed signals | TeaAgent parity | Gap / differentiator | Backlog action |
|---------|-------------------------|------------------|-----------------|----------------------|----------------|
| OpenAI Codex | https://deepwiki.com/openai/codex | Multi execution modes, sandboxing, MCP, IDE, cloud surfaces | Tool registry, MCP HTTP/stdio, Code Mode sandbox profiles, VS Code extension, USAGE mode/safety matrix | Hosted/cloud surface docs remain thin | P2 maintenance |
| Claude Code | https://deepwiki.com/anthropics/claude-code | Subagents, hooks, MCP, background sessions, permission modes, managed settings | `subagent`/`subagent_batch` with lineage + `shared`/`worktree`/`container` isolation, hooks, permission modes, MCP, skills | Background session cloud docs remain thin | P2 maintenance |
| OpenCode | https://deepwiki.com/sst/opencode | Provider breadth, client-server, plugins, skills, MCP, desktop, VS Code | 13 providers, plugins/skills, MCP, ACP/VS Code, USAGE surface recipes | Client-server/desktop hosted docs remain thin | P2 maintenance |
| OpenHands | https://deepwiki.com/OpenHands/OpenHands | SDK/CLI/GUI/cloud/enterprise, sandbox-decoupled V1 | Managed runtime stubs, MCP, audit, Code Mode, use-case dashboard | Hosted/cloud surface docs are stub-level only | P2 maintenance |
| Aider | https://deepwiki.com/Aider-AI/aider | Repo-map context, edit strategies, git workflow | Workspace tools, LSP/code-analysis, GraphQLite, preflight `context_pack` with LSP + hybrid/knowledge/GraphQLite read-only hits | Whole-repo map heuristics still thinner than Aider’s dedicated repo-map UX | P2 maintenance |
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
- [x] Preflight read-only `context_pack` (hybrid, `.teaagent/knowledge`, GraphQLite DB hits; `test_context_pack_read_only_flow.py`)
- [x] Subagent delegation with `shared` / `worktree` / `container` isolation and lineage audit (`test_subagent_*_isolation_flow.py`)

## Next differentiators (open)

| Track | Why it matters | Backlog ID |
|-------|----------------|------------|
| Docs/provider drift guard | README/USAGE/architecture/runtime provider registry aligned; shared credential env vars handled | Done |
| Subagent lineage + isolation | Parent run id, depth, batch index; `isolation: shared`, `worktree`, or `container` snapshot | Done (maintenance) |
| Repo-map / context pack | Preflight `context_pack` surfaces candidate files/memories without writes | Done (maintenance) |
| Mode and safety matrix | Permission modes, Plan/Auto/Code lanes, approvals, rollback | Done (maintenance) |
| Multi-surface recipes | CLI, TUI, VS Code, MCP, ACP, A2A, ANP, managed runtime | Done (maintenance) |
| Plugin/skill catalog | `docs/plugin-skill-catalog.md` + fixtures | Done (maintenance) |
| Use-case dashboard refresh | Matrix/HTML include survey date and open-gap counts | Done (maintenance) |
| Recurring survey cadence | `docs/release-checklist.md` | Done (maintenance) |

## Future API note (non-breaking)

`subagent` / `subagent_batch` should record parent-child run lineage and later
accept `isolation = shared | worktree | container` (filesystem snapshot under `.teaagent/subagent-containers/`).

## Next review trigger

Re-run this survey before the next minor release or when adding a new
federation/protocol ADR. Update `docs/backlog-priority.md` and
`docs/use-cases.md` differentiator sections when signals change.
