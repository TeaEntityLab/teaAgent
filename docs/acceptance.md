# Acceptance Coverage

TeaAgent acceptance tests live under `tests/acceptance/` and verify
user-facing workflows rather than isolated primitives. Integration tests live
under `tests/integration/` and verify cross-component interactions.

Run acceptance tests:

```bash
python3 -m pytest tests/acceptance
```

Run integration tests:

```bash
python3 -m pytest tests/integration
```

Some acceptance and integration tests start loopback HTTP servers and the TUI
acceptance flow writes the user TUI state file. In sandboxed environments, run
them with permission to bind localhost ports and write the TeaAgent state
directory.

## Acceptance Flows

| File | Story | Key assertions |
|---|---|---|
| `test_a2a_federation_flow.py` | A2A federation | Remote discovery, partial endpoint failure, capability routing, delegation, context forwarding, agent trace metadata |
| `test_agent_fix_test_review_flow.py` | End-to-end code-change loop | Baseline test failure, scoped hash-anchored edit, pytest rerun, diff inspection, and final repair summary |
| `test_agents_md_injection_flow.py` | Hierarchical instruction injection | Parent/child instruction merge order, fallback filename support (`AGENT.md`, `CLAUDE.md`) |
| `test_audit_chain_integrity_flow.py` | Audit log integrity | JSONL parseability, unique event IDs, redaction, disk/in-memory event parity, restricted file permissions |
| `test_cancel_flow.py` | Graceful cancel | Thread-safe cancel token stops runs cleanly and keeps audit state intact |
| `test_cost_tracking_flow.py` | Cost and token tracking | Terminal results and `run_completed` audit events carry token and cost fields |
| `test_daily_cli.py` | Daily CLI workflow | `agent preflight`, `agent run`, `agent show`, audit persistence, run-level audit summary |
| `test_daily_tui.py` | Daily TUI workflow | Chat mode, memory injection, progress streaming, answer persistence in session history |
| `test_error_remediation_flow.py` | Error remediation hints | Core errors include actionable default hints and custom hint override support |
| `test_external_tool_manifest_compatibility_flow.py` | External ecosystem compatibility | External MCP manifests and community skill packages remain compatible; invalid schemas fail with clear validation errors |
| `test_first_run_experience_flow.py` | First-run onboarding | `init` bootstraps `.teaagent/config.json`, creates `AGENTS.md` when missing, preserves existing `AGENTS.md`, and returns actionable onboarding checklist |
| `test_provider_matrix_consistency_flow.py` | Provider/docs consistency | Runtime provider registry matches README/USAGE provider count, API key env vars, default model table, and CLI `model providers` output |
| `test_live_provider_conformance_flow.py` | Live provider conformance | Live checks are skipped unless an explicit environment gate is set |
| `test_managed_runtime_flow.py` | Managed runtime | Tool metadata context, workspace/request forwarding, managed-task audit events, trace metadata |
| `test_mcp_client_flow.py` | MCP client compatibility | Bearer auth, session lifecycle, `tools/list`, `tools/call`, session close |
| `test_memory_auto_curation_flow.py` | Memory auto-curation | Completed runs append curated memory with task/outcome/last-tool context, deduplicate identical summaries, and skip pending-approval runs |
| `test_model_smoke_gating_flow.py` | Hosted-provider smoke gating | Live smoke calls are skipped unless CI explicitly sets the gate |
| `test_plan_mode_read_only_flow.py` | Read-only planning mode | Read-only runs complete with planning metadata for inspect tasks and block file writes/shell mutation |
| `test_policy_as_code_flow.py` | Policy-as-code deny rules | Workspace `policy.yaml`, deny enforcement, non-match pass-through, `danger-full-access` independence, argument matching |
| `test_remote_mcp_consumption_flow.py` | Remote MCP tool consumption | Remote tool registration, annotation propagation, prefix filtering, shared rate limits, proxied calls |
| `test_run_undo_acceptance_flow.py` | Reversible change recovery | Undo journal captures pre-write state and restores modified/new files to pre-run workspace state |
| `test_session_resume_continuity_flow.py` | Session resume continuity | Pending-approval resume replays observations from checkpoint/store, preserves audit lineage, and auto-curates memory on completion |
| `test_skill_install_flow.py` | Skill discovery and injection | Skill discovery, prompt injection, multi-skill loading, project override precedence, model-decision prompt wiring |
| `test_ultrawork_flow.py` | Long-running worker | Worker start, list, show, log tail, and stop lifecycle |
| `test_vscode_extension_mcp_boot_flow.py` | VSCode MCP boot flow | Extension manifest command contribution, source command wiring for MCP HTTP server, permission mode enum parity |
| `test_vscode_mcp_runtime_smoke_flow.py` | VSCode MCP runtime smoke | VSCode MCP command wiring, provider enum parity, and MCP HTTP initialize/list/call/close runtime flow |
| `test_webhook_audit_flow.py` | Webhook audit delivery | Run event delivery, HMAC verification, event filtering, failure suppression |
| `test_workspace_edit_flow.py` | Workspace edit workflow | Hash-anchored read/edit, git status, command execution, diff inspection, final diff summary |

## Integration Tests

| File | Coverage |
|---|---|
| `test_a2a_circuit_breaker.py` | Circuit open/close, endpoint skip, reset, backward compatibility |
| `test_a2a_traceparent.py` | W3C traceparent generation/parsing, delegation header injection, result trace metadata |
| `test_approval_ui.py` | Diff preview, y/n/e approval flow, path traversal handling, max prompt fallback |
| `test_audit_chain.py` | Audit hash-chain validity, tampering/insertion/deletion detection |
| `test_audit_sink_isolation.py` | Crashing sinks are isolated from other audit sinks |
| `test_benchmark.py` | p50/p95/mean latency, regression detection, serialisable benchmark output |
| `test_cancel_token.py` | Pre-cancel, mid-run cancel, thread-safe cancel behavior |
| `test_config_loader.py` | Config layer precedence, env override, workspace profile application |
| `test_destructive_approval_lifecycle.py` | Pause, approve, resume, deny path, auto-approve handler, read-only block |
| `test_disk_full_degradation.py` | ENOSPC and write-error graceful degradation with in-memory fallback |
| `test_dpop_replay_concurrency.py` | Concurrent DPoP JTI consumption allows exactly one success |
| `test_error_hints.py` | Error default hints and string rendering |
| `test_eval_report.py` | HTML report rendering for pass/fail, scores, reasoning, empty suites |
| `test_file_policy.py` | Deny-rule matching, first-match behavior, policy loading, runner wiring |
| `test_mcp_tool_adapter.py` | MCP tool discovery, annotations, prefix filtering |
| `test_migration_dry_run.py` | Migration dry-run preview without SQL side effects |
| `test_memory_retrieval_ranking.py` | Memory search relevance ranking favors high-signal auto-curated run summaries |
| `test_plugins.py` | Plugin discovery, registration, failure isolation, custom entry-point group |
| `test_redaction_config.py` | Configurable PII redaction toggles and custom patterns |
| `test_run_export.py` | Run archive export/import, hash-chain preservation, missing-file errors |
| `test_run_resume_checkpoint.py` | Checkpoint save/resume, pending approval, SQLite round trip, observation replay |
| `test_run_undo.py` | Pre-write capture, file deletion/restore, path traversal guard |
| `test_runner_cost_tracking.py` | `RunResult` cost fields and audit event cost fields |
| `test_schema_migration_live.py` | Migration ordering, idempotency, data survival, version tracking |
| `test_skill_loader.py` | Skill discovery, deduplication, cap enforcement, prompt injection |
| `test_streaming_tool_calls.py` | Streaming chunks, audit events, token accumulation |
| `test_subagent_budget_inheritance.py` | Subagent depth limits, error dicts, registry guard |
| `test_tool_rate_limit.py` | Sliding-window quotas, concurrency safety, expiry |
| `test_ultrawork_notify.py` | Webhook and shell notification delivery, failure suppression |
| `test_webhook_sink.py` | HTTP webhook delivery, HMAC, filtering, failure suppression |

## Related Unit Coverage

| File | Coverage |
|---|---|
| `tests/test_llm_transport.py` | TLS environment wiring for LLM HTTPS transport |

## Current Status

All currently implemented acceptance stories are passing. As of the latest
local verification, `python3 -m pytest tests/acceptance -q` reports
`69 passed`.

<!-- ACCEPTANCE_TIERS:START -->

## Acceptance Tiers (P0/P1/P2)

Use these tiers to control regression scope and release risk:

| Tier | Purpose | Representative acceptance flows |
|---|---|---|
| P0 | Safe first-run, policy boundaries, and core coding loop | `test_first_run_experience_flow.py`, `test_daily_cli.py`, `test_plan_mode_read_only_flow.py`, `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py`, `test_policy_as_code_flow.py` |
| P1 | Recovery, continuity, and IDE/runtime surface reliability | `test_run_undo_acceptance_flow.py`, `test_session_resume_continuity_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py`, `test_mcp_client_flow.py` |
| P2 | Ecosystem compatibility and extended operations | `test_external_tool_manifest_compatibility_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_ultrawork_flow.py`, `test_webhook_audit_flow.py` |

Recommended execution cadence:

1. Every PR: run all P0.
2. Before merge to `main`: run P0 + P1.
3. Before release: run full acceptance (P0 + P1 + P2).

<!-- ACCEPTANCE_TIERS:END -->

This file documents implemented acceptance flows. Market-standard use-case gaps
and planned future acceptance files are tracked in
[`docs/use-cases.md`](use-cases.md) and
[`docs/use-case-matrix.md`](use-case-matrix.md).
