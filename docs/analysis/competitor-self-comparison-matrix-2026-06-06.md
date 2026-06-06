# Competitor Self-Comparison Matrix — TeaAgent
# 2026-06-06

> **Status:** Source-backed point-in-time comparison.
> **Scope:** Selected direct and adjacent AI coding-agent competitors whose
> official documentation or upstream pages were checked on 2026-06-06.
>
> This is not a claim to cover every coding assistant in the market. It covers
> the competitors most relevant to TeaAgent's current product thesis: terminal
> agents, IDE agents, remote/cloud coding agents, and governed orchestration
> systems.

---

## Source Map

Official or upstream sources used for this matrix:

- OpenAI Codex help: <https://help.openai.com/en/articles/11369540-getting-started-with-codex>
- OpenAI Codex upgrades: <https://openai.com/index/introducing-upgrades-to-codex/>
- OpenAI Codex broader app/workflow positioning: <https://openai.com/index/codex-for-almost-everything/>
- Anthropic Claude Code extension overview: <https://code.claude.com/docs/en/features-overview>
- Anthropic Claude Code subagents: <https://code.claude.com/docs/en/sub-agents>
- GitHub Copilot cloud agent: <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent>
- GitHub Copilot session entry points: <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/start-copilot-sessions>
- GitHub Copilot model policy: <https://docs.github.com/en/copilot/concepts/models/fallback-and-lts-models>
- OpenCode agents and permissions: <https://opencode.ai/docs/agents/>
- Aider usage and git integration: <https://aider.chat/docs/usage.html>, <https://aider.chat/docs/git.html>
- Cline overview and Plan/Act: <https://docs.cline.bot/cline-overview>, <https://docs.cline.bot/core-workflows/plan-and-act>
- Cursor background agents and API: <https://docs.cursor.com/background-agent>, <https://docs.cursor.com/background-agent/api/overview>
- Cursor modes, permissions, and rules: <https://docs.cursor.com/agent>, <https://docs.cursor.com/cli/reference/permissions>, <https://docs.cursor.com/context/rules-for-ai>
- Kiro autonomous mode, specs, steering, hooks, web, and CLI: <https://kiro.dev/docs/web/autonomous-mode/>, <https://kiro.dev/docs/specs/>, <https://kiro.dev/docs/steering/>, <https://kiro.dev/docs/cli/hooks/>, <https://kiro.dev/docs/web/>, <https://kiro.dev/docs/cli/>
- Devin introduction and release notes: <https://docs.devin.ai/get-started/devin-intro>, <https://docs.devin.ai/release-notes/2026>
- OpenHands sandbox overview: <https://docs.openhands.dev/openhands/usage/sandboxes/overview>
- Google Jules docs and product page: <https://jules.google/docs/>, <https://jules.google/>
- Windsurf/Cascade docs: <https://docs.windsurf.com/windsurf/accounts/usage>, <https://docs.windsurf.com/plugins/cascade/models>, <https://docs.windsurf.com/windsurf/cascade/workflows>, <https://docs.windsurf.com/windsurf/terminal>
- Roo Code docs and shutdown notice: <https://docs.roocode.com/>, <https://roocodeinc.github.io/Roo-Code/basic-usage/using-modes/>, <https://roocodeinc.github.io/Roo-Code/advanced-usage/available-tools/tool-use-overview/>

Local TeaAgent evidence:

- `pyproject.toml` — alpha status, version, extras, scripts.
- `teaagent/runner/_core.py` — run loop, budget checks, approval handling.
- `teaagent/tools.py` — tool registry contract.
- `teaagent/audit.py`, `teaagent/audit_chain.py` — audit log, hash chain, sinks, verification.
- `teaagent/approval_manager.py`, `teaagent/policy.py`, `teaagent/read_only_gate.py` — permission and approval model.
- `teaagent/subagents/*`, `teaagent/swarm.py` — local subagent and swarm orchestration.
- `teaagent/tui/*`, `teaagent/chat_session_controller.py` — interactive conversation surface.

---

## Competitor Matrix

| Competitor | Confirmed Public Shape | Advantage Over TeaAgent | TeaAgent Advantage | Work Direction |
| --- | --- | --- | --- | --- |
| OpenAI Codex | Agent available across ChatGPT plans; CLI/IDE/cloud/GitHub review surfaces; compliance API coverage for Codex usage; cloud tasks can set up environments, use browser feedback, and review PRs. | Much stronger hosted/cloud, IDE, mobile, and GitHub review integration. Stronger public adoption and first-party model/channel integration. | TeaAgent is provider-agnostic and local-first; governance primitives are repo-native and inspectable. | Treat Codex as the benchmark for async task handoff, browser-backed frontend iteration, compliance log surface, and PR review UX. |
| Claude Code | Strong extension model: CLAUDE.md, skills, subagents, agent teams, hooks, MCP, plugins, code intelligence, permission modes. | Richer mature agent ecosystem and clearer feature taxonomy; subagents and teams are better explained as distinct patterns. | TeaAgent's audit chain, budget caps, and policy/governance framing are more explicit in the repo. | Copy the taxonomy clarity, not the product wholesale: split TeaAgent docs into always-on context, skills, hooks, subagents, teams, MCP, and enforcement. |
| GitHub Copilot cloud agent | Autonomous background work in GitHub Actions-powered environments; creates plans, branches, and PRs; many entry points including issues, IDEs, REST API, CLI, Slack, Teams, Jira, Linear, and MCP. | Distribution through GitHub and PR-native workflow is extremely strong. | TeaAgent can run outside GitHub and across providers, with local audit and stricter cost/permission controls. | Do not compete head-on on distribution; build GitHub/PR adapters that preserve TeaAgent governance and audit exports. |
| OpenCode | Terminal-native agent with configurable agents, subagents, and fine-grained permissions for read/edit/bash/task/web/lsp/skill/question and wildcard patterns. | Strong terminal UX and an increasingly mature permission model; likely faster community iteration. | TeaAgent has broader governance/audit/cost/compliance ambitions and a fuller policy vocabulary. | OpenCode is the closest terminal threat. TeaAgent must make governance visible and useful, not just implemented. |
| Aider | Terminal pair programmer; file-scoped context, multi-provider support, diffs, automatic git commits, and `/undo`. | Simpler mental model and excellent git-native reversibility. | TeaAgent handles richer tool governance, audit, approvals, budget, MCP, and multi-agent experiments. | Borrow the simplicity: make "what files will change" and "how to undo" obvious at every step. |
| Cline | Editor and terminal agent; explicit approval per action; Plan/Act separation; SDK, CLI, Kanban, VS Code, JetBrains, checkpoints, browser, MCP, and enterprise controls. | Better daily developer fit through IDE and clear Plan/Act UX; actions are visibly approved. | TeaAgent has more explicit run evidence and local governance depth. | Make TeaAgent's plan-before-write path feel as simple as Plan/Act, with readable approvals and checkpoint receipts. |
| Cursor | IDE agent modes, background agents in isolated remote machines, web/mobile agent entry points, API for background agents, and explicit CLI permissions. | Strongest IDE and async-background-agent UX among the selected tools; remote environment setup is productized. | TeaAgent has no equivalent hosted async agent but has stronger local audit/control primitives. | Treat Cursor as the remote-agent UX target. Do not enable remote multi-agent until isolation, queues, budgets, and progress are durable. |
| Kiro | Spec-driven development, steering files, hooks, CLI, web preview, autonomous mode that clarifies, plans, delegates to subagents, and opens PRs from an isolated sandbox. | Strong requirements/spec/task workflow and remote autonomous loop. | TeaAgent has similar planning/governance instincts but less polished artifact flow. | Build TeaAgent's work-direction docs into machine-checkable spec/task/run evidence rather than more prose. |
| Devin | Conversational web product with embedded IDE, terminal, browser, API, Slack/Teams handoff, CLI-to-cloud handoff, enterprise usage controls, MCP audit logs, and session ACU hard caps. | Most mature "AI teammate" collaboration surface and enterprise-facing admin/usage controls. | TeaAgent is open/local/provider-agnostic and cheaper to adapt internally. | Use Devin as the enterprise UX benchmark: session links, takeover, usage hard caps, enterprise audit events, and team review flow. |
| OpenHands | Open-source agent platform with Docker sandbox recommended, process sandbox marked unsafe, and remote sandbox for managed deployments. | Stronger sandbox-first operating model and clearer isolation vocabulary. | TeaAgent has a broader governance layer but weaker integration of sandboxing into the primary tool path. | Rename weak isolation honestly and make worktree/container isolation the default for multi-agent writes. |
| Google Jules | Experimental autonomous coding agent integrated with GitHub; works autonomously on bugs, docs, and features; hosted/cloud VM positioning. | Lower-friction hosted async task flow. | TeaAgent is more configurable and inspectable. | Use Jules as a reminder that "experimental" can still be simple to try; reduce TeaAgent's first-run ceremony. |
| Windsurf / Cascade | IDE-centric Cascade with in-house SWE models, workflows stored as markdown, web/docs search, terminal integration, usage analytics, and usage-based plans. | Strong IDE workflow packaging and model/product integration. | TeaAgent is not bound to one IDE or model family. | Convert TeaAgent workflows and skills into compact, discoverable, repo-native artifacts with visible runtime receipts. |
| Roo Code | Open-source VS Code agent with modes, custom modes, tool groups, MCP, and powerful customization; official docs now indicate shutdown of Roo Code products on May 15, 2026. | Historical strength in custom modes and mode-specific tool access; less current market threat after shutdown notice. | TeaAgent remains active in this workspace and can learn from Roo's mode system without inheriting its product risk. | Classify Roo as a design reference, not a primary strategic threat, unless a successor fork regains traction. |

---

## Cross-Competitor Pattern Comparison

| Pattern | Market Direction | TeaAgent Current Position | Implication |
| --- | --- | --- | --- |
| Remote async agents | Codex, Copilot, Cursor, Kiro, Devin, Jules all move work into isolated cloud or hosted environments. | Local-first; remote/server paths exist mostly as docs or partial surfaces. | Keep local-first as a principle, but do not market remote multi-agent until durable queues, budgets, and isolation exist. |
| IDE-native UX | Cursor, Windsurf, Cline, Copilot, Kiro, Devin all reduce friction by living inside editors or PRs. | CLI/TUI first; VS Code/MCP exists but is not the main onboarding path. | The terminal can remain the power-user surface, but daily adoption needs editor/PR receipts. |
| Plan/spec before write | Cline Plan/Act, Kiro specs, Claude planning/subagents, OpenCode permissioned agents all encode planning separation. | TeaAgent has plan-before-write enforcement, but the UX is less legible. | Keep enforcement; add readable plan receipts, file targets, tests, and approval diffs. |
| Tool permissions | OpenCode, Cline, Cursor, Kiro, Roo, Claude all expose permissions or hooks. | TeaAgent has strong policy internals. | The differentiator must move from "we have permissions" to "we can prove every action, cost, and approval." |
| Multi-agent orchestration | Claude agent teams, Kiro autonomous subagents, Cursor background agent API, Cline Kanban, Codex parallel agents. | Subagent and swarm layers exist but are local/in-process and partially divergent. | Unify orchestration before scaling it. Remote multi-agent without durable state is a credibility risk. |
| Audit/compliance | Codex has Compliance API; Devin has enterprise audit logs; GitHub has PR/session logs. | TeaAgent has hash-chained audit and signed/exportable run records. | This is TeaAgent's best strategic lane. It should become the primary product story. |
| Cost caps and usage visibility | Devin release notes mention session ACU hard caps; GitHub/Windsurf/Codex have usage surfaces; many tools still rely on plan billing. | TeaAgent has hard estimated-cost caps but cost estimation can be inaccurate by provider. | Make cost state honest: actual, estimated, unavailable, or local-provider non-billable. |

---

## Strategic Positioning

TeaAgent should not position itself as the fastest IDE agent or the most polished
hosted teammate. Competitors already own those lanes. TeaAgent's credible lane is:

> A local-first, provider-agnostic governance harness for agentic coding work,
> designed to make every model decision, tool call, approval, cost estimate,
> file write, and recovery path auditable.

This positioning is narrow but defensible. It appeals to:

- Security-conscious engineering teams.
- Platform engineers running agents in CI or controlled workspaces.
- Regulated or compliance-sensitive environments that need evidence, not just
  productivity claims.
- Power users who want multi-provider flexibility without surrendering audit
  and approval control.

It does not appeal first to:

- Beginners who want an IDE-first assistant.
- Teams that want hosted async PRs today.
- Users who value speed over governance.
- Organizations requiring multi-tenant SaaS, SOC 2 evidence, SSO/RBAC, and a
  polished admin dashboard immediately.

---

## Competitive Risks

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| OpenCode closes the permission gap. | It is closest to TeaAgent's terminal lane and already documents fine-grained permissions. | Move up-stack into audit, cost, compliance export, and evidence receipts. |
| Claude Code normalizes skills/subagents/hooks taxonomy. | Users may expect Claude's vocabulary everywhere. | Align TeaAgent docs with the same conceptual distinctions while preserving local semantics. |
| GitHub/Codex/Cursor own async work. | Remote PR workflows become the default expectation for "agent." | Make local governance + PR adapter the wedge; defer hosted until local safety is strong. |
| TeaAgent overclaims alpha/beta features. | Competitors are polished enough that doc drift will be punished quickly. | Add freshness labels, claim classes, and CI docs consistency guards. |
| Governance is a niche, not a mass-market hook. | Most developers may choose speed. | Aim for regulated, security, platform, and CI personas first. |

---

## Claims Not Made

- No exact GitHub star ranking is asserted in this file.
- No pricing comparison is asserted beyond official usage/cost-control shapes.
- No benchmark quality ranking is asserted.
- No claim is made that TeaAgent is enterprise-ready today.
- No claim is made that the selected competitor set is exhaustive.
