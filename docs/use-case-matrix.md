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
