# Use Cases and Acceptance Traceability

This document maps TeaAgent's primary user use cases to acceptance tests and
high-priority next improvements.

Generated matrix: [use-case-matrix.md](use-case-matrix.md)

## Core Use Cases

| Use Case | User Goal | Primary Acceptance Coverage |
|---|---|---|
| Project instruction conformance | Ensure repo-local agent rules are always applied | `test_agents_md_injection_flow.py`, `test_first_run_experience_flow.py` |
| Safe autonomous coding run | Execute coding tasks with policy controls and auditability | `test_daily_cli.py`, `test_daily_tui.py`, `test_policy_as_code_flow.py`, `test_workspace_edit_flow.py` |
| Destructive-action governance | Require approval before risky operations | `test_cancel_flow.py`, `test_daily_cli.py` (pause/resume), `test_policy_as_code_flow.py` |
| Tool ecosystem extensibility | Load skills and remote MCP tools reliably | `test_skill_install_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_mcp_client_flow.py` |
| Reliability and forensics | Preserve run history, webhook delivery, and audit integrity | `test_audit_chain_integrity_flow.py`, `test_webhook_audit_flow.py`, `test_cost_tracking_flow.py` |
| Memory continuity | Reuse successful outcomes across runs without manual logging | `test_memory_auto_curation_flow.py` |
| IDE-assisted workflows | Operate MCP flows and commands from VSCode extension | `test_vscode_extension_mcp_boot_flow.py` |

## Current Gaps and Next Fixes

None currently tracked at the use-case traceability layer.

## Planned Follow-ups

1. Optionally publish rendered HTML dashboard variant from the generated matrix.
