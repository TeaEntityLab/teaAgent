# Use-case Coverage Matrix

Generated from `docs/acceptance.md` by `scripts/build_use_case_matrix.py`.

| Use Case | Covered | Required Tests | Missing Tests |
|---|---|---|---|
| Project instruction conformance | yes | `test_agents_md_injection_flow.py`, `test_first_run_experience_flow.py` | - |
| Safe autonomous coding run | yes | `test_daily_cli.py`, `test_daily_tui.py`, `test_policy_as_code_flow.py`, `test_workspace_edit_flow.py` | - |
| Destructive-action governance | yes | `test_cancel_flow.py`, `test_daily_cli.py`, `test_policy_as_code_flow.py` | - |
| Tool ecosystem extensibility | yes | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_mcp_client_flow.py` | - |
| Reliability and forensics | yes | `test_audit_chain_integrity_flow.py`, `test_webhook_audit_flow.py`, `test_cost_tracking_flow.py` | - |
| Memory continuity | yes | `test_memory_auto_curation_flow.py` | - |
| IDE-assisted workflows | yes | `test_vscode_extension_mcp_boot_flow.py` | - |
| Product onboarding and provider readiness | yes | `test_first_run_experience_flow.py`, `test_model_smoke_gating_flow.py`, `test_live_provider_conformance_flow.py`, `test_provider_matrix_consistency_flow.py` | - |
| Read-only planning mode | yes | `test_plan_mode_read_only_flow.py` | - |
| End-to-end code-change loop | yes | `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py` | - |
| Reversible change recovery | yes | `test_run_undo_acceptance_flow.py` | - |
| Runtime IDE MCP smoke | yes | `test_vscode_extension_mcp_boot_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py` | - |
| Session resume continuity | yes | `test_session_resume_continuity_flow.py` | - |
| External ecosystem compatibility | yes | `test_external_tool_manifest_compatibility_flow.py` | - |
