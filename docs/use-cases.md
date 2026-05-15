# Use Cases and Acceptance Traceability

This document maps TeaAgent's current acceptance coverage against the common
usage standards visible in mainstream coding-agent READMEs: Hermes Agent,
OpenCode, Claude Code, and Codex. It separates implemented acceptance stories
from market-standard product gaps that still need acceptance tests.

Generated matrix: [use-case-matrix.md](use-case-matrix.md)

## Requirement Baseline

| Requirement | Mainstream signal | TeaAgent status | Next planning action |
|---|---|---|---|
| Terminal-first local agent | Codex, Claude Code, and OpenCode all lead with a local CLI/TUI workflow. | Covered by CLI/TUI workflows and quick-start docs. | Keep `test_daily_cli.py` and `test_daily_tui.py` as P0 smoke coverage. |
| First-run onboarding | Mainstream READMEs put install, setup, first command, and troubleshooting before architecture. | Covered by `init`, model smoke gating, and first-run acceptance. | Add a docs-consistency check for README/USAGE provider counts and defaults. |
| Project instruction loading | Modern agents rely on repo-local instruction files such as `AGENTS.md` or migration fallbacks. | Covered by hierarchical `AGENTS.md`, `AGENT.md`, and `CLAUDE.md` loading. | Keep as a compatibility requirement, not just an internal prompt feature. |
| Read-only planning/exploration mode | OpenCode exposes a read-only `plan` agent; other tools distinguish explore/plan from edit/build. | Partially covered by `read-only` permission mode, but not as a named planning use case. | Add `test_plan_mode_read_only_flow.py`. |
| Build/edit/test/diff loop | Coding agents are expected to read code, edit files, run tests, inspect diffs, and summarize results. | Partially covered by `test_workspace_edit_flow.py`; current flow uses a deterministic fake adapter. | Add `test_agent_fix_test_review_flow.py` for a full user-facing repair loop. |
| Approval and hard policy boundaries | Mainstream agents increasingly expose permission modes, approvals, and sandbox profiles. | Strong coverage: permission modes, prompt approval, policy-as-code, audit, and sandbox tests. | Promote undo/revert from integration to acceptance-level product recovery. |
| Provider/model flexibility | Hermes and OpenCode emphasize no lock-in and multi-provider operation. | Partially covered by provider adapters and gated conformance. README/USAGE provider count is inconsistent. | Add provider matrix docs consistency and live conformance report coverage. |
| Tool ecosystem extensibility | MCP, skills/plugins, custom commands, and external tools are mainstream extension points. | Covered by skills, MCP server/client, remote MCP registration, and plugin integration. | Add a compatibility fixture for external MCP manifests and skill metadata. |
| Multi-surface operation | Codex and Claude Code support IDE surfaces; Hermes supports messaging gateways; OpenCode supports desktop/client-server surfaces. | Partially covered by VSCode manifest/source checks. | Add runtime VSCode MCP boot smoke coverage. |
| Session continuity and memory | Hermes foregrounds learning loops and memory; terminal agents need resumable sessions. | Partially covered by memory auto-curation and checkpoint integration. | Add acceptance coverage for session resume continuity across CLI/TUI. |
| Reversible change recovery | Production-grade autonomous edit tools need rollback/undo stories. | Covered at integration level through run undo tests, not as a user-facing acceptance story. | Add `test_run_undo_acceptance_flow.py`. |

## Current Core Use Cases

| Use Case | User Goal | Primary Acceptance Coverage | Status |
|---|---|---|---|
| Project instruction conformance | Ensure repo-local agent rules are always applied. | `test_agents_md_injection_flow.py`, `test_first_run_experience_flow.py` | Implemented |
| Safe autonomous coding run | Execute coding tasks with policy controls and auditability. | `test_daily_cli.py`, `test_daily_tui.py`, `test_policy_as_code_flow.py`, `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` | Implemented |
| Destructive-action governance | Require approval before risky operations. | `test_cancel_flow.py`, `test_daily_cli.py` (pause/resume), `test_policy_as_code_flow.py`, `test_run_undo_acceptance_flow.py` | Implemented |
| Tool ecosystem extensibility | Load skills and remote MCP tools reliably. | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_mcp_client_flow.py` | Implemented baseline |
| Reliability and forensics | Preserve run history, webhook delivery, and audit integrity. | `test_audit_chain_integrity_flow.py`, `test_webhook_audit_flow.py`, `test_cost_tracking_flow.py` | Implemented baseline |
| Memory continuity | Reuse successful outcomes across runs without manual logging. | `test_memory_auto_curation_flow.py`, `test_session_resume_continuity_flow.py` | Implemented |
| IDE-assisted workflows | Operate MCP flows and commands from VSCode extension. | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` | Implemented |

## Planned Market-Standard Use Cases

| Use Case | User Goal | Required Acceptance Coverage | Priority | Status |
|---|---|---|---|---|
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
