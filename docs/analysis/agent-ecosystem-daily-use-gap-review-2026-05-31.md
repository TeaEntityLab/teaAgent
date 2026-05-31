# Agent Ecosystem and Daily-Use Gap Review - 2026-05-31

This review asks a product question rather than an implementation question:
what would TeaAgent still be missing if evaluated as a modern agent-system
participant and as a daily tool for an end user?

## Review Mode

- Primary mode: Plan/spec review.
- Secondary checks: product traceability, acceptance coverage integrity, ecosystem
  fit, and daily-use failure modes.
- Evidence base: local Markdown, acceptance catalog, CLI surface, `cx overview
  teaagent`, and current external reference signals from Codex, Claude Code,
  OpenCode, LangGraph, CrewAI, and MCP documentation.

## External Reference Signals

These sources are not treated as requirements by themselves. They are used to
identify ecosystem expectations that TeaAgent may choose to support, document as
non-goals, or test against.

| Ecosystem signal | Source | Implication for TeaAgent |
| --- | --- | --- |
| Coding agents now span terminal, IDE, desktop/app, cloud tasks, Slack/message entry, goals, skills, PR review, docs upkeep, UI QA, and repeatable workflows. | `https://developers.openai.com/codex/explore` | Daily-use planning should include more than local CLI edit loops. |
| Codex CLI emphasizes local terminal execution, approvals, multimodal input, IDE/desktop/cloud variants. | `https://help.openai.com/en/articles/11096431`, `https://github.com/openai/codex` | Packaging and surface continuity matter as much as core agent loop correctness. |
| Claude Code positions CLAUDE.md, skills, subagents, hooks, MCP, plugins, and background automation as distinct extension surfaces. | `https://code.claude.com/docs/en/features-overview` | TeaAgent should make its equivalent extension boundaries obvious and testable. |
| Claude subagents expose tool scope, MCP server scope, memory, background, isolation, model, permission mode, hooks, and skills. | `https://code.claude.com/docs/en/subagents` | TeaAgent subagent definitions should have parity tests for every supported field and explicit non-parity docs. |
| Claude hooks can run scripts, HTTP, prompts, or agentic verifiers, including background hooks. | `https://code.claude.com/docs/en/hooks` | TeaAgent hooks need real execution-path tests, not only direct HookRegistry tests. |
| OpenCode markets terminal, IDE, desktop, LSP, and broad provider support. | `https://opencode.ai/` | Repo-map quality and multi-surface packaging are product expectations, not luxuries. |
| LangGraph emphasizes durable execution, streaming, and human-in-the-loop. | `https://docs.langchain.com/oss/python/langgraph` | TeaAgent should make run persistence, checkpoints, streaming, and HITL gates measurable across surfaces. |
| CrewAI separates collaborative crews from structured event-driven flows. | `https://docs.crewai.com/introduction` | TeaAgent should not become a second workflow framework, but should document where deterministic workflow state begins and ends. |
| MCP HTTP authorization is optional but expected for restricted resources and user data. | `https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization` | Remote MCP trust and authorization must be treated as release-critical when exposed beyond loopback. |

## Current Strengths

| Strength | Evidence |
| --- | --- |
| Governance-first product identity is clear. | `docs/product-contract.md` defines local-first, provider-adapter, tool-boundary, audit-first, permission-mode enforced outcomes. |
| First-hour and daily CLI paths are documented. | `README.md` golden path and `docs/USAGE.md` daily path. |
| Acceptance catalog is broad and user-story oriented. | `docs/acceptance.md` lists 273 collected acceptance tests across P0/P1/P2. |
| Multi-surface foundation exists. | CLI, TUI, VS Code, MCP stdio/HTTP, ACP, A2A, ANP, managed runtime are documented in `docs/USAGE.md`. |
| Tool governance is a differentiator. | `ToolRegistry`, `ApprovalPolicy`, audit hash chain, tool lint, file policy, and permission modes are central surfaces. |
| Ecosystem compatibility is intentionally tracked. | `docs/use-cases.md`, `docs/use-case-matrix.md`, `docs/plugin-skill-catalog.md`, and `docs/architecture.md`. |

## Findings

### F-ECO-001 - Product surface is broader than the canonical daily journey

Severity: High

TeaAgent exposes many advanced surfaces: cloud, gateway, ACP, A2A, ANP, managed
runtime, control plane, sandbox, consensus, skill marketplace, automations, and
subagents. The canonical daily path remains mostly local CLI/TUI. This is good
for first use, but it creates a gap for users who begin in Slack, GitHub, VS
Code, a browser dashboard, or background/cloud tasks.

Required fix: define productized journeys for the top cross-surface entry
points, then add acceptance tests that prove a task can move across surfaces
without losing identity, permissions, audit, status, or recovery.

### F-ECO-002 - Acceptance coverage is strong but not yet organized as journey maps

Severity: High

`docs/acceptance.md` lists strong individual stories. What is missing is a
journey-level map: setup -> inspect -> plan -> execute -> approve -> verify ->
recover -> remember -> report. Without that map, a release can have many green
tests but still leave a daily user unsure which path to take.

Required fix: add a journey-to-acceptance matrix with required P0/P1/P2 flows
per persona and surface.

### F-ECO-003 - Background/cloud surfaces are acceptance-covered but not productized

Severity: High

The docs explicitly call background/cloud task docs thin. There are tests for
background attach/resume/notify, automation parity, and managed cloud task
stubs, but the operator guide is not yet a full daily workflow.

Required fix: create a background/cloud operator guide and add an end-to-end
acceptance story for "start task from message or CLI, detach, receive status,
attach, inspect audit, approve if needed, resume or cancel."

### F-ECO-004 - Desktop/client-server packaging is still a product gap

Severity: High

MCP HTTP and session listing exist, and there is a VS Code extension surface.
The docs still mark desktop/client-server packaging as partial. Mainstream
coding agents increasingly meet users in IDEs, app shells, and desktop bridges.

Required fix: either package a minimal desktop/client-server workflow or state
that TeaAgent intentionally remains CLI-first with documented attach recipes.

### F-ECO-005 - Repo-map quality lacks an external benchmark dataset

Severity: Medium

TeaAgent has large-repo SLO acceptance. The remaining gap is external benchmark
credibility: representative repos, target-file tasks, top-K hit rate, latency,
and failure classification.

Required fix: create a repo-map benchmark corpus and turn it into a release gate
or nightly quality gate.

### F-ECO-006 - Subagent parent review and merge needs a complete daily workflow

Severity: Medium

Worktree isolation and lineage are tested. What is still thin is the human
workflow after children finish: compare results, inspect diffs, resolve
conflicts, apply one patch, reject others, and record rationale.

Required fix: define `subagent review` as a first-class journey and test the
parent review -> patch apply -> conflict path.

### F-ECO-007 - Hook/plugin/skill ecosystem needs "explainability of activation"

Severity: Medium

TeaAgent supports hooks, plugins, and skills, and has install/security tests.
Daily users need to know why a hook fired, why a skill was loaded, which plugin
registered a tool, and how to disable one surface without breaking the session.

Required fix: add unified extension activation explain output and acceptance
tests across hooks, skills, plugins, and MCP tools.

### F-ECO-008 - MCP authorization and trust should be a journey, not only a feature

Severity: High

MCP is an ecosystem trust boundary. TeaAgent has MCP client/server/trust pieces,
but daily user stories should cover OAuth/bearer setup, trust review, tool
listing, scoped approval, audit, revoke, and failure recovery.

Required fix: define an MCP trust onboarding journey and add remote-MCP
acceptance tests for unknown tools, expired tokens, revoked trust, and
authorization-required resources.

### F-ECO-009 - Model/provider operations need a full "provider day two" flow

Severity: Medium

Provider setup and smoke gates exist. Missing daily-user stories include model
degradation, fallback routing, cost cap warnings, model capability mismatch, and
provider outage recovery.

Required fix: add provider-resilience acceptance: detect outage, suggest
fallback, preserve permission mode and audit lineage, and avoid silently using a
more dangerous model/tool profile.

### F-ECO-010 - Observability is present but not packaged as an operator dashboard

Severity: Medium

Audit viewer, control plane, telemetry, status, traces, and export exist. The
gap is a single operational view that answers: what is running, what is blocked,
what changed, what cost is accumulating, what needs approval, what can be undone?

Required fix: define an operator cockpit contract, then test CLI/TUI/dashboard
parity for the same run state.

### F-ECO-011 - User-facing verification and evidence bundles are incomplete

Severity: Medium

TeaAgent has acceptance tests, trace/export/replay, and audit bundles. End users
still need a simple "what did the agent prove?" artifact after a task.

Required fix: create a run completion evidence summary that includes changed
files, commands run, tests passed/failed, approvals, known gaps, and rollback
path.

### F-ECO-012 - Automation needs stronger owner intent and lifecycle controls

Severity: Medium

Automations include provenance gates, quarantine, templates, budgets, and
status. Missing daily stories include recurring task review, stale automation
cleanup, owner transfer, missed-run remediation, and safe "no-op" reporting.

Required fix: add automation lifecycle acceptance beyond creation and tick:
review, renew, pause, resume, promote, transfer, expire, and explain skip.

### F-ECO-013 - Security posture is strong but spread across many docs

Severity: Medium

Threat model, product contract, use cases, maturity matrix, and risk audit all
hold security facts. A user choosing a mode or integration needs a single
"what risk am I accepting?" guide.

Required fix: add a risk-mode decision table and verify docs mention the same
constraints for CLI, TUI, automation, MCP, cloud, and gateway paths.

### F-ECO-014 - Multi-agent ecosystem positioning needs explicit non-goals

Severity: Medium

TeaAgent has subagents, swarm, tournament, consensus, A2A, ANP, and workflow
engine surfaces, but the product contract says it is not a generic no-code
agent builder or a LangGraph/CrewAI replacement.

Required fix: add a "when to use TeaAgent vs workflow framework" guide and
acceptance tests that preserve the harness boundary: tool governance and audit
stay central, domain workflow logic stays outside the core.

## Daily User Journey Gaps

| Journey Step | Works Today | Missing or Thin |
| --- | --- | --- |
| Install/setup | `setup`, `doctor`, provider tables | One command that validates provider, workspace, git, shell, MCP, IDE, and cost profile together. |
| Morning cockpit | `daily`, TUI daily, status | Single shared cockpit contract across CLI/TUI/dashboard/IDE. |
| Task intake | `clarify`, `preflight`, `plan` | Prioritized task queue from GitHub/Slack/issue text with ambiguity scoring. |
| Planning | Plan artifacts and plan-before-write | Plan review checklist and plan diff between iterations. |
| Execution | `agent run`, workspace tools, approval modes | Live progress UX parity across CLI/TUI/desktop/cloud. |
| Approval | prompt mode, JIT approval, scoped grants | Approval explanation that includes why now, blast radius, rollback, and similar past approvals. |
| Verification | tests, validation profiles, trace/export | End-user evidence summary artifact. |
| Recovery | undo, resume, run store | Guided recovery wizard for failed/partial runs. |
| Background | background store, attach/resume/notify | Full background/cloud playbook and hosted packaging. |
| Collaboration | A2A, ANP, consensus, gateways | Team/tenant identity story across messages, remote peers, and audit. |
| Memory | failure cards, memory catalog, pinned files | Memory review inbox: accept, edit, reject, expire. |
| Reporting | audit viewer, exports | "Sendable summary" for PRs, managers, compliance, and future agents. |

## Ecosystem Capability Gap Map

| Capability Area | TeaAgent Status | Missing Flow or Feature |
| --- | --- | --- |
| Terminal agent | Strong | Simplify top-level command set and reduce alias confusion. |
| TUI | Strong | More parity for approvals, run evidence, and background attach. |
| IDE | Foundation/stable pieces | First-class install/update guide and command parity tests. |
| Desktop/app | Partial | Packaged app shell or explicit non-goal. |
| Cloud/background | Foundation/partial | Hosted guide, auth, attach/resume UX, notification lifecycle. |
| Messaging gateway | Present | Full Slack/Telegram task intake to audited run flow. |
| MCP server/client | Strong base | OAuth/trust/revoke journey and resource/prompt support decisions. |
| Skills/plugins | Strong base | Activation explain, versioning, rollback, marketplace trust. |
| Subagents | Strong base | Parent review/merge workflow and delegation policy guide. |
| Workflow orchestration | Present | Boundary guide versus LangGraph/CrewAI-style frameworks. |
| Evals/benchmarks | Present | Repo-map benchmark corpus and model/provider regression scorecards. |
| Observability | Many components | One cockpit contract and evidence bundle. |
| Governance/security | Strong | Mode-specific risk guide and release profile enforcement. |

## Traceability

| Review Requirement | Evidence | Test Evidence | Status |
| --- | --- | --- | --- |
| Evaluate ecosystem fit | `docs/architecture.md`, external references | `test_external_tool_manifest_compatibility_flow.py`, `test_remote_mcp_consumption_flow.py` | Partial |
| Evaluate daily usage | `README.md`, `docs/USAGE.md` | `test_daily_cli.py`, `test_daily_tui.py`, `test_first_hour_e2e_flow.py` | Strong |
| Identify missing flows | `docs/use-cases.md`, `docs/backlog-priority.md` | Productization gap tests listed in `docs/use-cases.md` | Partial |
| Identify missing acceptance tests | `docs/acceptance.md` | 273 collected acceptance tests | Strong base, missing journey-level matrix |
| Plan new work | This review plus roadmap doc | New roadmap artifact | New |

## Decision

Request changes before claiming ecosystem-complete daily-agent maturity.

TeaAgent has an unusually strong governance and acceptance foundation. The next
quality jump is not "add more primitives"; it is to productize cross-surface
journeys, make trust and activation explainable, and package operator evidence
so a daily user can understand what happened without reading ten subsystem docs.

## Residual Risks

- This review did not run full acceptance tests; it relied on existing
  acceptance collection and docs.
- External ecosystem references change quickly; rerun the competitive survey
  before release claims.
- Some gaps may be conscious non-goals. If so, the plan should capture the
  non-goal and its user-facing replacement path.
