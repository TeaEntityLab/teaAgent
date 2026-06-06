# Competitive Claim Audit - TeaAgent
# 2026-06-06

> **Claim class:** Evidence snapshot and claim-hygiene audit.
>
> **Purpose:** Make TeaAgent's competitor comparisons safe to reuse by separating
> stable official-doc evidence from volatile market facts, self-comparison
> inference, and claims that require more proof.
>
> This document complements the
> [Competitor Self-Comparison Matrix](competitor-self-comparison-matrix-2026-06-06.md).
> When the two files disagree, use this file for claim hygiene rules and the
> self-comparison matrix for competitor-by-competitor rows.

---

## Freshness Rule

Competitive positioning must be refreshed from official or upstream sources
before public reuse. Do not treat star counts, pricing, model names, plan
availability, hosted availability, or adoption rankings as stable unless they
were checked on the same date as the claim.

Stable enough to reuse with date:

- Product shape from official docs.
- Documented workflow concepts.
- Documented permission, sandbox, plan, subagent, MCP, hook, and PR surfaces.
- TeaAgent code and tests at the cited commit.

Volatile or unsafe without same-day refresh:

- GitHub stars, install counts, community size, revenue, pricing, plan quotas,
  model defaults, release-channel availability, and exact adoption rankings.
- "Only tool" claims unless the competitor set and source date are explicitly
  bounded.

---

## Source Refresh Ledger

| Competitor | Source type checked on 2026-06-06 | Stable evidence usable from that source | Reuse caution |
| --- | --- | --- | --- |
| OpenAI Codex | OpenAI help and product pages | Codex spans local clients, IDE/cloud/web surfaces, enterprise controls, compliance/API surfaces, and cloud task workflows. | Model defaults, usage limits, and plan access can change quickly. |
| Claude Code | Anthropic Claude Code docs | Extension taxonomy includes CLAUDE.md, skills, code intelligence, MCP, subagents, agent teams, hooks, plugins, permissions, and multiple IDE/web surfaces. | Feature names and scope precedence may change as docs evolve. |
| GitHub Copilot cloud agent | GitHub Docs | Cloud agent researches, plans, edits branches, can open PRs, and runs in GitHub Actions-powered environments with many intake points. | Enterprise metrics and model policy are volatile. |
| OpenCode | Upstream OpenCode docs | Agent and subagent concepts, terminal-first workflow, and permission-oriented agent configuration are relevant comparison axes. | Community size and release velocity should not be copied from old snapshots. |
| Aider | Upstream Aider docs | Terminal pair-programming, file-scoped context, and git-native workflow remain the durable comparison points. | Provider/model and usage details are version-sensitive. |
| Cline | Cline docs | Plan/Act separation is a clear UX benchmark for thinking-before-writing workflows. | Marketplace, provider, enterprise, and pricing details are volatile. |
| Cursor | Cursor docs/search cache | Background agents are remote async agents in isolated machines; modes and CLI permissions provide IDE/remote and permission benchmarks. | Cursor docs were partially rendered through search cache; refresh directly before publication. |
| Kiro | Kiro docs | Specs, steering, and autonomous mode frame a spec-first workflow with clarification, planning, subagents, sandbox, and PR completion. | Web preview and model-selection constraints may change. |
| Devin / Devin Desktop / Cascade | Devin docs | Web/desktop agent workflows, embedded environments, workflows, skills, MCP, team handoff, and enterprise surfaces are relevant benchmarks. | Windsurf/Cascade branding and product structure changed; verify naming before external use. |
| OpenHands | OpenHands docs | Sandbox terminology and Docker/process/remote provider distinctions are direct isolation benchmarks. | Managed deployment details are product-version dependent. |
| Google Jules | Google Jules docs | Hosted GitHub-integrated VM task flow, planning, and notification model are stable comparison axes. | Experimental status and availability should be rechecked. |
| Roo Code | Upstream Roo docs | Modes/custom modes/tool-group customization are useful design references. | Product status, shutdown notices, and successor forks require current verification. |

---

## Claim Audit Table

| Claim candidate | Allowed wording | Disallowed wording | Reason |
| --- | --- | --- | --- |
| TeaAgent has a governance advantage. | "TeaAgent's strongest differentiator in this repo is local-first governance: tool schemas, approval modes, audit records, cost caps, run evidence, and provider flexibility." | "TeaAgent is the most secure coding agent." | Security superiority requires independent audit and complete competitor review. |
| Competitors lead on remote agents. | "Several major competitors now offer hosted or remote async agent workflows." | "Everyone else is remote-first." | Aider/OpenCode and local IDE modes remain relevant local-first or terminal-first options. |
| TeaAgent is remote-agent-ready. | "TeaAgent has local subagent and swarm experiments, but remote-ready claims are blocked by WS2 safety gates." | "TeaAgent already supports production remote multi-agent teams." | Durable queues, budget inheritance, isolation defaults, and crash recovery are not complete. |
| TeaAgent has audit primitives. | "TeaAgent has hash-chained audit logs and exportable run evidence in the codebase." | "TeaAgent is compliance-certified." | Certification and operational controls are not the same as local primitives. |
| TeaAgent has cost controls. | "TeaAgent has hard estimated-cost caps and should label actual/estimated/unknown cost explicitly." | "TeaAgent always prevents overspend." | Provider reports and child-agent inheritance gaps limit the guarantee. |
| Competitor ranking. | "Against the selected source-backed competitor set, TeaAgent's strongest lane is governance-as-a-layer." | "TeaAgent ranks above/below competitor X overall." | Overall rankings require benchmarks, adoption data, and user studies. |
| Star counts. | "Star counts are intentionally omitted from current claims unless refreshed same-day." | "OpenCode has N stars, Aider has N stars..." | Volatile facts become stale quickly and have already appeared in older documents. |
| "Only" claims. | "No selected official docs reviewed here expose the same complete local audit/cost/approval bundle." | "No competitor has audit/cost/approval." | The source set is bounded and competitors may have private or recently added features. |

---

## Competitor-to-Self Pressure Map

| Competitor | Pressure on TeaAgent | TeaAgent response | Required proof before claiming parity |
| --- | --- | --- | --- |
| OpenAI Codex | Async task handoff, IDE/cloud continuity, compliance API, browser-backed workflows. | Treat Codex as a benchmark for cross-surface continuity and compliance export UX. | Run receipt, IDE/PR adapter evidence, compliance export docs, and same-day source refresh. |
| Claude Code | Clear taxonomy for context, skills, hooks, MCP, subagents, teams, and plugins. | Align TeaAgent vocabulary while preserving local governance semantics. | Taxonomy docs, plugin/subagent trust boundaries, and matching tests. |
| GitHub Copilot cloud agent | PR-native branch workflow and GitHub Actions-powered environments. | Build adapters that export TeaAgent evidence into PR workflows instead of copying GitHub distribution. | PR adapter spec, branch isolation, run evidence attached to PR, and audit export. |
| OpenCode | Terminal-native speed and permission-oriented agent model. | Make governance visible and low-friction in terminal/TUI flows. | Human-first TUI output, approval selectors, progress summaries, and run receipts. |
| Aider | Git simplicity, explicit files, and easy undo mental model. | Make file targets, diffs, and undo scope obvious at every risky step. | Approval diff preview and undo receipt tests. |
| Cline | Plan/Act UX makes thinking-before-doing understandable. | Convert strict plan-before-write from an internal gate into a readable plan receipt. | Plan receipt command, file target validation output, and UX acceptance tests. |
| Cursor | Remote background agents, IDE takeover, isolated machines, API-managed async work. | Use Cursor as the remote UX benchmark while keeping remote claims gated. | Durable queue, isolated workspaces, budget inheritance, status streaming, and takeover semantics. |
| Kiro | Spec-first autonomous workflow with clarification, plan, subagents, sandbox, and PR output. | Turn TeaAgent work directions into machine-checkable specs and acceptance artifacts. | Spec/task/run linkage and automated acceptance gates. |
| Devin / Cascade | Teammate-like web/desktop flow, workflows, skills, MCP, enterprise handoff. | Compete through local evidence and governance, not broad teammate polish. | Session handoff receipts, audit dashboards, usage caps, and enterprise claim gates. |
| OpenHands | Sandbox-first vocabulary and Docker default posture. | Name weak isolation honestly and make safe isolation the multi-agent default. | Default/gated isolation change and concurrent-write regression tests. |
| Jules | Simple hosted GitHub task flow with plan approval and notifications. | Reduce first-run ceremony and show task state clearly. | Setup smoke, notifications/status plan, and readable task receipt. |
| Roo Code | Mode/custom-mode vocabulary and tool grouping. | Treat modes as a design reference, not a strategic threat unless maintained successors regain traction. | Permission-mode explanation and tool-group policy docs. |

---

## Current Safe Positioning

Safe concise positioning:

> TeaAgent is a local-first, provider-agnostic governance harness for agentic
> coding work. Its near-term advantage is not polished remote delegation; it is
> making model decisions, tool calls, approvals, cost estimates, file changes,
> run evidence, and recovery paths inspectable.

Unsafe positioning:

- "TeaAgent is enterprise-ready."
- "TeaAgent is a hosted autonomous teammate."
- "TeaAgent has production-grade remote multi-agent orchestration."
- "TeaAgent is more secure than Codex, Claude Code, Cursor, Devin, or Copilot."
- "TeaAgent is the only agent with governance."

Conditionally safe after proof:

| Claim | Required evidence |
| --- | --- |
| "Remote-safe local delegation" | WS2 timeout, isolation, budget, depth, approval durability, and crash-recovery tests. |
| "Compliance mode" | Fatal audit durability behavior, strict chain verification, documented operator controls. |
| "Daily-driver conversation trust" | Run receipt, progress summaries, readable approvals, accurate cost state, UX acceptance tests. |
| "Plugin governance" | Plugin load rejection tests, schema/annotation enforcement, trust-boundary documentation. |
| "PR workflow integration" | GitHub adapter or documented export flow with run evidence attached. |

---

## Older Landscape Corrections

The [Competitive Landscape and Positioning](competitive-landscape-and-positioning-2026-06-06.md)
file contains strategic material and some volatile market facts. Treat the
following as historical unless refreshed:

- Exact star counts.
- Pricing and plan tables.
- Model-family defaults.
- Community adoption rankings.
- "Only" claims that are not bounded to the selected source set.

The durable conclusions remain useful:

- TeaAgent should avoid competing head-on as a hosted IDE-first assistant.
- Governance, audit, cost, approval, provider flexibility, and local evidence are
  the strongest product wedge.
- Remote/cloud workflows are a market expectation but should remain gated by
  safety and observability work.

---

## Refresh Procedure

1. Refresh official or upstream docs first.
2. Record the source date in the matrix or claim audit.
3. Avoid exact volatile metrics unless they are the point of the analysis.
4. Compare every competitor on the same axis before making a comparative claim.
5. Label every TeaAgent-side assertion as code evidence, inference, plan, or unknown.
6. Update this file when a public claim moves from unsafe to conditionally safe.

