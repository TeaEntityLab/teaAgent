# Competitor Community Feedback Synthesis - 2026-05-31

This synthesis converts mainstream agent-system signals and community feedback
into roadmap pressure for TeaAgent. It is not a popularity contest. The goal is
to identify failure modes that daily users repeatedly notice in coding agents:
slow sessions, unclear state, hidden costs, unsafe extension surfaces, weak
background execution, and poor recovery.

## Research Question

Given TeaAgent's current docs, acceptance coverage, and governance-first product
contract, what future work should be prioritized when compared with mainstream
agent-system products and community feedback?

## Direct Recommendation

TeaAgent should keep its core identity as a governance-first coding-agent
harness, but productize more of the daily user loop:

1. Make context, cost, risk, approvals, and progress visible in one cockpit.
2. Add stronger session rollover, plan binding, and recovery workflows.
3. Turn subagents, background work, MCP, plugins, and automations into
   explainable product journeys rather than scattered primitives.
4. Add explicit eval gates for prompt/runtime changes, long-session quality,
   scope creep, and extension trust.
5. Treat desktop, IDE, gateway, and cloud entry points as state-continuity
   problems, not separate feature silos.

## Evidence Used

### Local TeaAgent Evidence

| Evidence | Local source | Roadmap pressure |
| --- | --- | --- |
| Product contract says TeaAgent is governance-first, local-first, tool-boundary centered, audit-first, and permission-mode enforced. | `docs/product-contract.md` | Future features must strengthen the governance harness instead of drifting into a generic workflow framework. |
| Acceptance catalog has 273 collected tests. | `docs/acceptance.md` | The next gap is journey coherence and evidence packaging, not raw test count. |
| Maturity matrix marks CLI/TUI, first-hour onboarding, VS Code, audit chain, run undo, and governance gates as stable/beta. | `docs/maturity-matrix.md` | Future roadmap should focus on foundation/partial surfaces and day-two operations. |
| Known productization gaps include background/cloud docs, desktop packaging, repo-map benchmark, subagent merge, and automation parity. | `docs/USAGE.md`, `docs/use-cases.md` | These should become roadmap tracks with acceptance tests. |
| Risk audit found hook mutation wiring, graph state scoping, backend timeout, MCP trust, audit privacy wording, plugin strictness, release status, and tool-lint warning gaps. | `docs/analysis/system-transparency-risk-audit-2026-05-31.md` | Risk register and roadmap must include implementation and verification tasks, not only product UX. |
| Ecosystem gap review identified daily cockpit parity, issue-to-plan, evidence summary, guided recovery, background lifecycle, MCP trust onboarding, subagent review/merge, memory review, and release evidence. | `docs/analysis/agent-ecosystem-daily-use-gap-review-2026-05-31.md` | This synthesis should extend those into a larger work list. |

### External Official / Upstream Signals

| ID | Source | Signal |
| --- | --- | --- |
| S-CODEX-001 | `https://developers.openai.com/codex/explore` | Coding agents now span terminal, IDE, app, cloud, PR review, docs upkeep, UI QA, and repeatable workflows. |
| S-CODEX-002 | `https://help.openai.com/en/articles/11096431` | Codex CLI emphasizes terminal execution, approvals, sandboxing, multimodal input, IDE integration, and local control. |
| S-CODEX-003 | `https://github.com/openai/codex` | Open-source issue tracker shows recurring friction around platforms, sandboxing, config, model usage, MCP, and CLI/IDE behavior. |
| S-CLAUDE-001 | `https://code.claude.com/docs/en/features-overview` | Claude Code separates features such as skills, subagents, hooks, MCP, plugins, memory, and background operation. |
| S-CLAUDE-002 | `https://code.claude.com/docs/en/subagents` | Subagents expose tool scope, model, permission mode, MCP server scope, background behavior, hooks, skills, and memory. |
| S-CLAUDE-003 | `https://code.claude.com/docs/en/hooks` | Hooks can run commands, prompts, HTTP calls, or agentic verifiers; background hooks expand the risk surface. |
| S-CLAUDE-004 | `https://www.anthropic.com/engineering/april-23-postmortem?pubDate=20260425` | A product-layer prompt/runtime change can degrade quality even when the base model is unchanged. |
| S-OPENCODE-001 | `https://opencode.ai/` | OpenCode positions terminal, IDE, desktop/app, LSP, and provider breadth as mainstream expectations. |
| S-LANGGRAPH-001 | `https://docs.langchain.com/oss/python/langgraph` | Durable execution, streaming, persistence, and human-in-the-loop are expected when workflows become long-running. |
| S-CREWAI-001 | `https://docs.crewai.com/introduction` | Multi-agent systems often separate collaborative crews from deterministic flows. TeaAgent should document this boundary. |
| S-MCP-001 | `https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization` | Remote MCP access to user data or restricted resources should have explicit authorization and trust handling. |

### Community / Feedback Signals

These are used as directional feedback, not as statistical consensus.

| ID | Source | Signal |
| --- | --- | --- |
| S-CURSOR-001 | `https://forum.cursor.com/t/extremely-slow-agent-processing/159187` | Long-running agent sessions can become painfully slow; users ask for easier context transfer and less manual session hygiene. |
| S-CURSOR-002 | `https://forum.cursor.com/t/agent-stuck-in-the-same-loop-stuck-in-updating/62744` | Agents can loop on tool/update states, making progress and recovery hard to judge. |
| S-CURSOR-003 | `https://forum.cursor.com/t/stuck-in-loop-with-agent/94515` | Users experience repeated fix loops and want clearer failure escape paths. |
| S-CODEX-COMM-001 | `https://github.com/openai/codex/issues` | Issue themes include sandbox failures, missing attachments/images, browser/MCP config questions, rate limits, desktop integration, and child-thread/subagent confusion. |
| S-CLAUDE-COMM-001 | `https://news.ycombinator.com/item?id=43735550` | Community discussion around Claude Code quality issues emphasized prompt/runtime changes, context handling, and regression visibility. |
| S-OPENHANDS-001 | `https://github.com/All-Hands-AI/OpenHands/issues` | OpenHands issue patterns include sandbox/runtime setup, task execution reliability, UI/backend integration, and hosted service concerns. |
| S-OPENHANDS-002 | `https://www.all-hands.dev/blog/2026-product-roadmap` | OpenHands roadmap emphasizes durable backend, fixed ports, enterprise control plane, hosted workloads, workflow orchestration, and observability. |
| S-SCOPE-001 | `https://arxiv.org/abs/2604.16128` | Overeager agent behavior can expand beyond user intent; scope control is a measurable agent-system quality dimension. |
| S-CREWAI-COMM-001 | `https://www.reddit.com/r/crewai/comments/1hw9opc/crewai_noob_silent_agent_invocation_is_killing_my/` | Multi-agent systems can hide token usage and action attribution unless observability is local and per-agent. |
| S-LANGGRAPH-COMM-001 | `https://www.reddit.com/r/LangChain/comments/1kk9vjp/langchain_langgraph_are_probably_making_your_code/` | Some users perceive graph frameworks as complexity overhead when workflows do not need explicit state machines. |
| S-SEC-001 | `https://www.wiz.io/blog/langchain-vulnerabilities-overview` | Agent ecosystems inherit ordinary software risks: path traversal, SQL injection, deserialization, and vulnerable integrations. |
| S-CODEX-SC-001 | `https://openai.com/index/response-to-axios-research-on-codex/` | Desktop/CLI distribution and update pipelines need signing, revocation, dependency review, and clear user remediation paths. |

## Version / Date Context

- Current date: 2026-05-31.
- TeaAgent local docs reviewed in this thread were current as of 2026-05-31.
- External signals are point-in-time observations. Community feedback changes
  quickly and should be refreshed before a release, protocol ADR, or public
  maturity claim.

## Evidence vs Inference

### Evidence Observed

- TeaAgent already has strong governance primitives, acceptance tests, audit,
  permission modes, undo, TUI/CLI paths, VS Code smoke coverage, MCP support,
  subagents, automations, and release/documentation gates.
- Local docs explicitly identify productization gaps around background/cloud,
  desktop/client-server, repo-map benchmark, subagent merge, and automation
  parity.
- Competitor docs and roadmaps show that users now expect agent systems to work
  across terminal, IDE, desktop/app, cloud/background, messaging, MCP, skills,
  subagents, and automation.
- Community reports frequently describe confusion around context bloat, slow
  long sessions, tool loops, hidden token use, unclear progress, and difficult
  recovery.
- Official postmortem and security sources show that prompt/runtime changes,
  packaging, update distribution, and dependency risks can damage trust even
  when the core model or agent design is strong.

### Inference Made

- TeaAgent's next large quality jump should be journey productization:
  "what should the user do next, why, and with what evidence?"
- The highest-leverage roadmap items are cockpit visibility, run evidence,
  guided recovery, scope control, context rollover, per-agent cost attribution,
  extension activation explainability, and durable background lifecycle.
- TeaAgent should avoid becoming a LangGraph/CrewAI replacement. It should offer
  governable execution, audit, HITL, extension trust, and durable run evidence
  around user workflows.
- "Stable" should mean not only tests pass, but the user can diagnose, recover,
  and explain a feature from the daily surfaces.

### Unknowns

- Community reports are not weighted by usage volume or customer segment.
- Some competitor features may have changed after the cited docs or forum
  threads were published.
- TeaAgent's local dogfood adoption and external user telemetry were not
  measured here.
- Full acceptance execution was not run for this synthesis; it relies on prior
  collection evidence and docs consistency checks.

## Feedback Themes

| Theme | External pressure | TeaAgent implication |
| --- | --- | --- |
| Long-session degradation | Users report slow agent processing and stale context in long chats. | Add session rollover, context-health scoring, compaction explain, and freshness gates. |
| Looping and unclear recovery | Agents can repeat failed fixes or get stuck in update/tool loops. | Add loop detection, recovery recommendations, and failure escape UX. |
| Hidden costs | Multi-agent systems can spend tokens in invisible child work. | Add per-agent, per-tool, per-surface token/cost attribution. |
| Scope creep | Agent systems may expand tasks beyond the user's explicit ask. | Add scope budget, intent diff, and "authorized work" checks. |
| Subagent opacity | Subagents are powerful but hard to observe and merge. | Add parent review/merge cockpit, lineage diff, child evidence, and conflict UX. |
| Prompt/runtime regressions | Product-layer changes can degrade quality. | Add prompt/config change eval gates, canaries, and rollback. |
| Surface fragmentation | Terminal, IDE, desktop, cloud, and messaging all carry different state. | Define a shared run-state contract and parity tests. |
| Background durability | Long tasks need attach/resume/cancel/status and fixed service endpoints. | Productize background/cloud lifecycle, not only storage primitives. |
| Extension trust | MCP, hooks, plugins, and skills are supply-chain surfaces. | Require trust review, activation explain, strict profiles, and revocation tests. |
| Packaging trust | Desktop/CLI updates create code-signing and dependency risks. | Add SBOM/signing/update/revocation tasks before desktop packaging claims. |
| Framework complexity | Users push back when graph systems are overkill. | Keep TeaAgent's workflow boundary explicit and thin. |
| Enterprise observability | Teams need cost, audit, policy, RBAC, and fleet views. | Extend control plane as an operator evidence surface. |

## Classification

### Already Present

- Local-first permission modes.
- Tool registry, audit, approval, and run store.
- Acceptance catalog and docs consistency scripts.
- First-hour and daily CLI/TUI paths.
- MCP, plugins, skills, subagents, automations, VS Code, and managed runtime
  foundations.
- Run undo, trace/export/replay, cost tracking, memory, and context pack.

### Adjacent / Missing

- One cockpit contract across CLI, TUI, IDE, dashboard, background, and cloud.
- Long-session quality gates and context rollover.
- Explicit scope budget and overeager-action prevention.
- Subagent review/merge UX and cost attribution.
- Prompt/runtime config evals and staged rollout controls.
- Desktop/client-server package trust, update, and attach UX.
- Background/cloud operator guide with durable execution expectations.
- MCP/plugin/skill activation explain across all extension surfaces.
- Risk register with owner/status/due date/release-blocking flags.

### Recommended Core Additions

- Daily cockpit and evidence bundle.
- Guided recovery wizard and loop detector.
- Scope contract and intent-drift gate.
- Context health and session rollover planner.
- Per-agent cost ledger.
- Extension activation explain and trust revocation.
- Background/cloud lifecycle playbook.
- Subagent parent review/merge.
- Prompt/runtime regression suite.
- Release evidence bundle and public-claim validator.

## Handoff

The companion plan is
`docs/plans/future-roadmap-risk-usability-backlog-2026-05-31.md`.
It turns these signals into roadmap phases, task IDs, risk controls, acceptance
tests, and usability work items.
