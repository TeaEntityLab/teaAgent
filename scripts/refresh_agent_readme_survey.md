# Agent Landscape Survey

DeepWiki- and upstream-backed review for TeaAgent competitive positioning. TeaAgent
stays a governance-first harness; this artifact tracks parity, gaps, and backlog
actions — not a second agent framework.

Last reviewed: **2026-05-24**

## Sources reviewed

| Project | DeepWiki / upstream URL | README URL | Reviewed signals | TeaAgent parity | Gap / differentiator | Backlog action | Local doc ref |
|---------|------------------------|------------|------------------|-----------------|----------------------|----------------|---------------|
| OpenAI Codex | https://deepwiki.com/openai/codex | https://github.com/openai/codex | Multi execution modes, sandboxing, MCP, IDE, cloud surfaces | Tool registry, MCP HTTP/stdio, Code Mode sandbox profiles, VS Code extension, USAGE mode/safety matrix | Hosted/cloud surface docs remain thin | P2 maintenance | `docs/architecture.md`, `docs/use-cases.md` |
| Claude Code | https://deepwiki.com/anthropics/claude-code | https://github.com/anthropics/claude-code | Subagents, hooks, MCP, background sessions, permission modes, managed settings | `subagent`/`subagent_batch` with lineage + `shared`/`worktree`/`container` isolation, hooks, permission modes, MCP, skills | Background session cloud docs remain thin | P2 maintenance | `docs/architecture.md`, `docs/use-cases.md` |
| OpenCode | https://deepwiki.com/sst/opencode | https://github.com/anomalyco/opencode | Provider breadth, client-server, plugins, skills, MCP, desktop, VS Code | 13 providers, plugins/skills, MCP, ACP/VS Code, USAGE surface recipes | Client-server/desktop hosted docs remain thin | P2 maintenance | `docs/architecture.md`, `docs/use-cases.md` |
| Hermes | https://deepwiki.com/NousResearch/hermes-agent | https://github.com/nousresearch/hermes-agent | Persistent digital employee, long-term memory loop, agent-created skills, multi-platform messaging gateway, sandbox backends, cron scheduling | Memory curation, skills/plugins, subagent isolation, Plan/Auto modes, CI workflows | Cross-platform resident entry, self-generated skills, persistent automation use case not yet covered | P2 maintenance | `docs/architecture.md`, `docs/use-cases.md` |
| OpenHands | https://deepwiki.com/OpenHands/OpenHands | https://github.com/All-Hands-AI/OpenHands | SDK/CLI/GUI/cloud/enterprise, sandbox-decoupled V1 | Managed runtime stubs, MCP, audit, Code Mode, use-case dashboard | Hosted/cloud surface docs are stub-level only | P2 maintenance | `docs/use-cases.md` |
| Aider | https://deepwiki.com/Aider-AI/aider | https://github.com/Aider-AI/aider | Repo-map context, edit strategies, git workflow | Workspace tools, LSP/code-analysis, GraphQLite, preflight `context_pack` with LSP + hybrid/knowledge/GraphQLite read-only hits | Whole-repo map heuristics still thinner than Aider's dedicated repo-map UX | P2 maintenance | `docs/use-cases.md` |
| LangGraph | https://deepwiki.com/langchain-ai/langgraph | https://github.com/langchain-ai/langgraph | Graph state, checkpoints, durable execution | `CheckpointStore`, runner limits, audit chain | No graph-native orchestration (intentional harness boundary) | Document as non-goal | `docs/use-cases.md` |
| CrewAI | https://deepwiki.com/crewAIInc/crewAI | https://github.com/crewAIInc/crewAI | Role-based crews, task delegation | A2A delegation, ANP governed federation | No multi-role crew DSL (intentional harness boundary) | Document as non-goal | `docs/use-cases.md` |

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
- [x] Everyday usage docs: `agent daily` start ritual, task recipes, context profiles, TUI loop (README + USAGE + cli)

## Competitive differentiators (implemented / maintenance)

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

## Current API note (non-breaking)

`subagent` / `subagent_batch` record parent-child run lineage and accept
`isolation = shared | worktree | container` (filesystem snapshot under
`.teaagent/subagent-containers/`). Keep these fields additive-compatible for
future subagent tooling.

## Future research / P2 maintenance

- Hosted/cloud surface docs for managed-runtime deployments.
- Background-session story across CLI/TUI/IDE surfaces.
- Desktop/client-server packaging guidance.
- Repo-map quality evaluation against larger real-world repositories.

## Next review trigger

Re-run this survey before the next minor release or when adding a new
federation/protocol ADR. Update `docs/backlog-priority.md` and
`docs/use-cases.md` differentiator sections when signals change.
