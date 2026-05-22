# Use Cases and Acceptance Traceability

This document maps TeaAgent's current acceptance coverage against the common
usage standards visible in mainstream coding-agent READMEs: Hermes Agent,
OpenCode, Claude Code, and Codex. It separates implemented acceptance stories
from market-standard product gaps that still need acceptance tests.

Generated matrix: [use-case-matrix.md](use-case-matrix.md)

Landscape survey (reviewed 2026-05-22):
[scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md)

## Implemented parity (competitive baseline)

Mainstream coding-agent expectations from Codex, Claude Code, OpenCode, OpenHands,
and Aider are largely covered by acceptance flows today. TeaAgent does not need
to replicate framework-native graph/crew orchestration; the harness focuses on
governance, audit, and portable protocol surfaces.

| Area | Status | Primary evidence |
|------|--------|------------------|
| Terminal-first CLI/TUI | Implemented | `test_daily_cli.py`, `test_daily_tui.py` |
| First-run onboarding + provider readiness | Implemented | `test_first_run_experience_flow.py`, `test_provider_matrix_consistency_flow.py` |
| Repo instructions (`AGENTS.md`) | Implemented | `test_agents_md_injection_flow.py` |
| Read-only planning | Implemented | `test_plan_mode_read_only_flow.py` |
| Edit/test/diff loop + undo | Implemented | `test_workspace_edit_flow.py`, `test_run_undo_acceptance_flow.py` |
| Permission modes + policy | Implemented | `test_policy_as_code_flow.py`, `test_cancel_flow.py` |
| MCP + skills/plugins + hooks | Implemented | `test_remote_mcp_consumption_flow.py`, `test_skill_install_flow.py`, `test_hooks.py` |
| Memory + session continuity | Implemented | `test_memory_auto_curation_flow.py`, `test_session_resume_continuity_flow.py` |
| IDE surface (VS Code) | Implemented | `test_vscode_extension_mcp_boot_flow.py` |
| Federation (A2A, ANP) | Implemented | `test_anp_adapter_flow.py`, A2A acceptance flows |

## Next differentiators (roadmap)

These items are intentionally **not** full parity gaps; they sharpen TeaAgent’s
governance-first story against the 2026-05-22 landscape survey. See
[docs/backlog-priority.md](backlog-priority.md) for acceptance targets.

| Differentiator | Priority | Backlog reference |
|----------------|----------|-------------------|
| Docs/provider architecture drift guard | P0 | Open — High |
| Subagent lineage and isolation hardening | P1 | Open — Medium |
| Repo-map / context pack for coding runs | P1 | Open — Medium |
| Mode and safety comparison matrix | P1 | Open — Medium |
| Multi-surface launch recipes | P1 | Open — Medium |
| Plugin/skill compatibility catalog | P2 | Open — Low |
| Competitive use-case dashboard refresh | P2 | Open — Low |
| Periodic mainstream-agent refresh cadence | P2 | Open — Low |

## Requirement Baseline

| Requirement | Mainstream signal | TeaAgent status | Verification evidence |
|---|---|---|---|
| Terminal-first local agent | Codex, Claude Code, and OpenCode all lead with a local CLI/TUI workflow. | Implemented. | `test_daily_cli.py`, `test_daily_tui.py` |
| First-run onboarding | Mainstream READMEs put install, setup, first command, and troubleshooting before architecture. | Implemented. | `test_first_run_experience_flow.py`, `test_model_smoke_gating_flow.py` |
| Project instruction loading | Modern agents rely on repo-local instruction files such as `AGENTS.md` or migration fallbacks. | Implemented. | `test_agents_md_injection_flow.py` |
| Read-only planning/exploration mode | OpenCode exposes a read-only `plan` agent; other tools distinguish explore/plan from edit/build. | Implemented. | `test_plan_mode_read_only_flow.py` |
| Build/edit/test/diff loop | Coding agents are expected to read code, edit files, run tests, inspect diffs, and summarize results. | Implemented. | `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` |
| Approval and hard policy boundaries | Mainstream agents increasingly expose permission modes, approvals, and sandbox profiles. | Implemented. | `test_policy_as_code_flow.py`, `test_cancel_flow.py`, `test_run_undo_acceptance_flow.py` |
| Provider/model flexibility | Hermes and OpenCode emphasize no lock-in and multi-provider operation. | Implemented. | `test_provider_matrix_consistency_flow.py`, `test_live_provider_conformance_flow.py` |
| Tool ecosystem extensibility | MCP, skills/plugins, custom commands, external tools, and semantic code-analysis toolpacks are mainstream extension points. | Implemented. | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_external_tool_manifest_compatibility_flow.py`, `test_code_analysis_prompt_injection_flow.py` |
| Multi-surface operation | Codex and Claude Code support IDE surfaces; Hermes supports messaging gateways; OpenCode supports desktop/client-server surfaces. | Implemented (VSCode surface). | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` |
| Session continuity and memory | Hermes foregrounds learning loops and memory; terminal agents need resumable sessions. | Implemented. | `test_memory_auto_curation_flow.py`, `test_session_resume_continuity_flow.py` |
| Reversible change recovery | Production-grade autonomous edit tools need rollback/undo stories. | Implemented. | `test_run_undo_acceptance_flow.py` |
| Hook lifecycle system | Claude Code and Hermes implement 8-event hooks for extensibility. | Implemented. | `test_hooks.py` |
| Three-tier memory hierarchy | Claude Code implements Project/Personal/Auto-Memory tiers. | Implemented. | `test_memory.py` |
| Context compaction | Claude Code triggers auto-compaction at 75-92% token usage. | Implemented. | `test_preflight.py` |
| Plugin system | Claude Code supports Commands/Agents/Hooks/MCP extension points. | Implemented. | `test_plugins.py` |
| ACP IDE integration | Protocol for VS Code, Zed, JetBrains integration. | Implemented. | `test_vscode_*_flow.py` |

## Current Core Use Cases

| Use Case | User Goal | Blast Radius | Rollback Path | Audit Criticality | Primary Acceptance Coverage | Status |
|---|---|---|---|---|---|---|
| Project instruction conformance | Ensure repo-local agent rules are always applied. | high | git revert AGENTS.md | medium | `test_agents_md_injection_flow.py`, `test_first_run_experience_flow.py` | Implemented |
| Safe autonomous coding run | Execute coding tasks with policy controls and auditability. | high | teaagent agent undo | high | `test_daily_cli.py`, `test_daily_tui.py`, `test_policy_as_code_flow.py`, `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` | Implemented |
| Destructive-action governance | Require approval before risky operations. | critical | teaagent agent undo | critical | `test_cancel_flow.py`, `test_daily_cli.py` (pause/resume), `test_policy_as_code_flow.py`, `test_run_undo_acceptance_flow.py` | Implemented |
| Tool ecosystem extensibility | Load skills and remote MCP tools reliably. | medium | remove skill/MCP config | medium | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_mcp_client_flow.py` | Implemented baseline |
| Reliability and forensics | Preserve run history, webhook delivery, and audit integrity. | high | N/A (read-only verification) | critical | `test_audit_chain_integrity_flow.py`, `test_webhook_audit_flow.py`, `test_cost_tracking_flow.py` | Implemented baseline |
| Memory continuity | Reuse successful outcomes across runs without manual logging. | low | clear .teaagent/memory/ | low | `test_memory_auto_curation_flow.py`, `test_session_resume_continuity_flow.py` | Implemented |
| IDE-assisted workflows | Operate MCP flows and commands from VSCode extension. | low | restart VSCode | low | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` | Implemented |
| Hook lifecycle management | Execute custom logic on tool events (PreToolUse, PostToolUse, etc.). | medium | disable hooks config | medium | `test_hooks.py` | Implemented |
| Three-tier memory system | Use Project/Personal/Auto-Memory for context persistence. | low | clear memory files | low | `test_memory.py` | Implemented |
| Context auto-compaction | Automatically compress context when approaching token limits. | low | N/A | low | `test_preflight.py` | Implemented |
| Plan mode exploration | Explore codebases in read-only mode without modifications. | low | N/A | low | `test_plan_mode_read_only_flow.py` | Implemented |
| Plugin extensibility | Add custom Commands, Agents, or MCP integrations. | medium | remove plugin | low | `test_plugins.py` | Implemented |

## Planned Market-Standard Use Cases

| Use Case | User Goal | Blast Radius | Rollback Path | Audit Criticality | Required Acceptance Coverage | Priority | Status |
|---|---|---|---|---|---|---|---|
| Product onboarding and provider readiness | Install, initialize, verify providers, and start a safe first run without reading architecture docs. | `test_first_run_experience_flow.py`, `test_model_smoke_gating_flow.py`, `test_live_provider_conformance_flow.py`, `test_provider_matrix_consistency_flow.py` | P0 | Implemented |
| Read-only planning mode | Explore an unfamiliar repo and produce a plan without file edits or shell mutation. | `test_plan_mode_read_only_flow.py` | P0 | Implemented |
| End-to-end code-change loop | Ask the agent to fix a small failing test, apply a scoped edit, rerun tests, inspect diff, and report the result. | `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` | P0 | Implemented |
| Reversible change recovery | Undo or recover from an agent-authored workspace edit using a user-facing command. | `test_run_undo_acceptance_flow.py` | P1 | Implemented |
| Runtime IDE MCP smoke | Start the workspace MCP endpoint from the VSCode command and verify an MCP client can attach. | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` | P1 | Implemented |
| Session resume continuity | Resume a paused or completed run and preserve task, observations, memory, and audit context. | `test_session_resume_continuity_flow.py` | P1 | Implemented |
| External ecosystem compatibility | Validate representative MCP manifests, skill metadata, and tool annotations against TeaAgent's registry contract. | `test_external_tool_manifest_compatibility_flow.py` | P2 | Implemented |

## Todo Plan

1. Completed (P0): Provider/docs consistency acceptance (`test_provider_matrix_consistency_flow.py`).
2. Completed (P0): Read-only planning acceptance (`test_plan_mode_read_only_flow.py`).
3. Completed (P0): End-to-end repair loop acceptance (`test_agent_fix_test_review_flow.py`).
4. Completed (P1): Reversible change recovery acceptance (`test_run_undo_acceptance_flow.py`).
5. Completed (P1): VSCode runtime MCP smoke acceptance (`test_vscode_mcp_runtime_smoke_flow.py`).
6. Completed (P1): Session resume continuity acceptance (`test_session_resume_continuity_flow.py`).
7. Completed (P2): External ecosystem compatibility acceptance (`test_external_tool_manifest_compatibility_flow.py`).
8. Completed (P2): Published rendered dashboard at `docs/use-case-matrix.html`.

## Evidence Commands

Use these commands as the default claim-verification workflow before updating docs:

1. `python3 scripts/build_acceptance_status.py`
2. `python3 scripts/build_use_case_matrix.py`
3. `python3 scripts/validate_docs_consistency.py`
4. `python3 -m pytest tests/acceptance --collect-only -q`
