# Use-case Coverage Matrix

Generated from `docs/acceptance.md` by `scripts/build_use_case_matrix.py`.

| Use Case | Covered | Blast Radius | Rollback Path | Audit Criticality | Required Tests | Missing Tests |
|---|---|---|---|---|---|---|
| Project instruction conformance | yes | high | git revert AGENTS.md | medium | `test_agents_md_injection_flow.py`, `test_first_run_experience_flow.py` | - |
| Safe autonomous coding run | yes | high | teaagent agent undo | high | `test_daily_cli.py`, `test_daily_tui.py`, `test_policy_as_code_flow.py`, `test_workspace_edit_flow.py` | - |
| Destructive-action governance | yes | critical | teaagent agent undo | critical | `test_cancel_flow.py`, `test_daily_cli.py`, `test_policy_as_code_flow.py`, `test_p0_slo_flow.py` | - |
| Tool ecosystem extensibility | yes | medium | remove skill/MCP config | medium | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_mcp_client_flow.py` | - |
| Reliability and forensics | yes | high | N/A (read-only verification) | critical | `test_audit_chain_integrity_flow.py`, `test_webhook_audit_flow.py`, `test_cost_tracking_flow.py` | - |
| Memory continuity | yes | low | clear .teaagent/memory/ | low | `test_memory_auto_curation_flow.py` | - |
| IDE-assisted workflows | yes | low | restart VSCode | low | `test_vscode_extension_mcp_boot_flow.py` | - |
| Product onboarding and provider readiness | yes | low | re-run teaagent init | low | `test_first_run_experience_flow.py`, `test_model_smoke_gating_flow.py`, `test_live_provider_conformance_flow.py`, `test_provider_matrix_consistency_flow.py` | - |
| Read-only planning mode | yes | low | N/A (no mutations) | low | `test_plan_mode_read_only_flow.py` | - |
| End-to-end code-change loop | yes | high | git checkout -- . | high | `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` | - |
| Reversible change recovery | yes | medium | teaagent agent undo | medium | `test_run_undo_acceptance_flow.py` | - |
| Runtime IDE MCP smoke | yes | low | restart MCP server | medium | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` | - |
| Session resume continuity | yes | medium | re-run original task | high | `test_session_resume_continuity_flow.py` | - |
| External ecosystem compatibility | yes | low | fix manifest/schema | low | `test_external_tool_manifest_compatibility_flow.py` | - |
