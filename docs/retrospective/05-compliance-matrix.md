# 05 - AGENTS.md Rule Compliance Matrix

> Rule-by-rule comparison of `/Users/teee/dev/teaagent/AGENTS.md` against evidence from the four audit dimensions. Ratings: **Compliant / Partial / Violated**. Every row includes evidence as `file_path:line_number`.

## Architecture

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Keep the harness thin: orchestration, tool governance, state boundaries, audit, and validation belong here; domain reasoning belongs in the model or skills." | **Partial violation** | Orchestration/governance/audit are in the harness, but domain reasoning has leaked into it: `coordinator.py` (`_classify_task_with_llm`, `_generate_workflow_plan`), `agent_factory.py` (`_generate_evolution_prompt`, `_llm_evolve_prompt`), `workflow_engine.py:1-748` (`_generate_self_correction_prompt`, `_generate_unified_diff`), `issue_intake.py:1-922` (AmbiguityDetector, ChecklistGenerator), and `intent.py` (`clarify_task`). Most severe: `subagents/_approval_queue_hybrid_store.py:113-4884` embeds a 4,771-line approval product in the harness (voting/comments/SLA/templates/compliance/notifications/analytics), violating the thin-harness principle. |
| "Prefer protocol assets over vendor-specific assets: MCP-style tool metadata, Skills, and portable run records." | **Compliant** | MCP: `mcp_server.py:PROTOCOL_VERSION='2024-11-05'`; `mcp_tool_adapter.py:84-158` consumes MCP manifests as `ToolDefinition`; `mcp_client.py:MCPHTTPClient` supports stdio+HTTP; `stateless_mcp.py`. Skills: `skill_loader.py` + `skill_lifecycle.py` + `skill_candidates.py` include provenance. Run records: `run_store.py:RunSummary`, `run_receipt.py`, `run_evidence.py`, `release_evidence.py`. Vendor code is isolated behind optional extras in `llm/_adapters.py` and `managed_runtime.py`. |
| "Do not add a second agent framework without an ADR." | **Compliant (literally)** | ADRs 0019 (federated swarm/consensus), 0022 (centralized approval queue for subagents), 0028 (tournament/swarm), and 0029 (consensus deferred) cover `subagents/_manager.py:205-538`, `swarm.py:370-1010`, `consensus/`, and `tournament/`. **Note**: this is literally compliant, but the thin-harness principle is still violated: two execution frameworks double the surface over which budget/audit/approval correctness must be maintained, and no ADR reconciles the shared invariants of the two execution loops. |

## Tool Governance

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Tools must be registered through `ToolRegistry`." | **Compliant** | `teaagent/tools.py:114` defines `ToolRegistry` as the single registration path. All registrations use `registry.register(...)`: workspace (`_files.py:73-382`), git (`_git.py:213-497`), browser (`browser_tools.py:231-464`), GitHub (`github_integration.py:156-279`), code analysis (`_tools.py:21-280`), subagent (`_tools.py:132-497`), and MCP (`mcp_tool_adapter.py:146-156`). Plugins use `plugin_system.py:466` `load_entry_point_tools(tool_registry, ...)`. |
| "Each tool requires a name, description, input schema, output schema, and annotations." | **Compliant** | The `register()` signature at `teaagent/tools.py:129-141` requires all five fields; lines `142-165` validate that name/description are non-empty; `integration/plugin_governance.py:54-72` blocks incomplete plugins; `governance/tool_lint.py:200-313` performs deeper linting. All 50+ registered tools provide all five fields. |
| "Destructive tools must not run unless an approval token is present for that exact tool call." | **Violated (see 01 G1)** | Normal paths require JIT/store/scoped/payload-digest approval bound to `(call_id, tool_name, argument_digest)` (`approval_manager.py:839-1006`), and exactness tests are comprehensive (`tests/test_approval_token_exactness.py`). However, `AutoModeManager` escalates auto-allowed tools to `DANGER_FULL_ACCESS`, allowing destructive calls without the required exact-call token (`_auto_mode_manager.py:62-66`). The runner still records normal tool lifecycle events, but no dedicated auto-mode authority event identifies the bypass. |
| "Tool errors must be actionable and classified." | **Compliant** | `DenialReasonCode` has 11 values (`errors.py:9-25`); `AgentHarnessError` carries a `hint` (`errors.py:39-60`); `format_denial_message` produces remediation based on reason_code (`approval_manager.py:1222-1270`); `ToolExecutionError` wraps handler failures with a hint (`errors.py:148-156`). |

## Runtime Safety

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Every run must have an iteration limit and a tool-call limit." | **Compliant** | `RunBudget` defaults to `max_iterations=25` and `max_tool_calls=25` (`budget.py:45-47`); `validate()` enforces >=1/>=0 (`:50-75`); the runner enforces the limits (`runner/_core.py:957,1008-1009`); subagents clamp them (`subagents/_manager.py:52-58`); `ChatAgentConfig` defaults to 10/10 (`chat_agent.py:84-86`). |
| "Every tool call and final result must be recorded in the audit log." | **Partial (see 01 G4)** | CLI paths completely record `tool_call_started` (`runner/_core.py:789`), `tool_call_completed`/`_failed` (`:824,877`), `run_completed`/`run_failed` (`:508,916`), and `tool_call_approved`/`tool_call_pending_approval`/`tool_decision_invalid` (`:720-743,1024`). **Gap**: library callers at `chat_agent.py:755` fall back to `AuditLogger()` with `path=None`, producing only in-memory records and no durable trail (see G4 in [01](01-security-risk.md)). |
| "Long-lived state must be externalized; in-memory runner state is temporary only." | **Compliant** | Run state is persisted through RunStore JSONL, `ApprovalPresetStore` (`approvals.json`), `UltraworkStore`, `CheckpointStore`, and audit JSONL. Runner-internal `RunContext`, `JITApprovalState`, and `BudgetMonitor._emitted_levels` are discarded per run (`runner/_core.py:433-478`; `audit.py:130-209`). |

## Skills

| Rule | Rating | Evidence |
| --- | --- | --- |
| "Keep `SKILL.md` short and route details into `REFERENCE.md` or examples." | **Compliant** | `skill_review.py:222` sets `max_skill_md_lines=80`, and lines `203-209` remind authors to use `REFERENCE.md` for skills over 40 lines. All seven Git-tracked `.opencode/skill/*` files are at most 73 lines; `teaagent/skills/builtin/rss-summary/` is 62 lines and includes `REFERENCE.md` plus examples. `.agents/skills` is an ignored local symlink to `/Users/teee/.agents/skills`, not a project asset, and is excluded from the rating. |
| "Treat skills as reviewed supply-chain assets, not casual prompt snippets." | **Compliant** | `skill_loader.py:357-367` skips skills that fail review; `skill_review.py:222` checks frontmatter, line count, external references, blocklist patterns, and AST scans of `*.py` for dangerous imports/calls; `skill_lifecycle.py:45-105` records every transition as a `skill_lifecycle_transition` audit event; `skill_candidates.py` requires provenance + attestation; `skill_candidate_artifacts.py` validates provenance. |

## Cross-Dimension Compliance Summary

| Section | Rules | Compliant | Partial | Violated |
| --- | --- | --- | --- | --- |
| Architecture | 3 | 2 | 1 | 0 (literally) |
| Tool Governance | 4 | 3 | 0 | 1 |
| Runtime Safety | 3 | 2 | 1 | 0 |
| Skills | 2 | 2 | 0 | 0 |
| **Total** | **12** | **9** | **2** | **1** |

## Conclusion

- **One rule is Violated**: auto-mode can run destructive tools without the exact-call approval token required by `AGENTS.md`.
- **The two Partial ratings are systemic gaps**:
  1. **"Keep the harness thin"** - god modules and leaked domain reasoning are the largest debt items (G-CRIT-1 and G-HIGH-1 in [03](03-architecture-quality.md)).
  2. **"Every tool call is audited"** - the library-caller path lacks a durable trail (G4 in [01](01-security-risk.md)).
- **The violation is P0**: `AutoModeManager` silently escalates past the exact-call-token rule and emits no dedicated auto-mode authority event (G1 in [01](01-security-risk.md)).
