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

**Current acceptance test count: 3357 tests collected (3226 passed, 70 failed, 61 skipped)**

## Acceptance Flows

| File | Story | Key assertions |
|---|---|---|
| `test_a2a_federation_flow.py` | A2A federation | Remote discovery, partial endpoint failure, capability routing, delegation, context forwarding, agent trace metadata |
| `test_backend_adapter_flow.py` | Backend adapter routing and fallback | `workspace_knowledge_search` supports `backend=auto` primary/fallback behavior and `workspace_code_parse` routes actions through registered `CodeParseBackend` implementations |
| `test_agent_fix_test_review_flow.py` | End-to-end code-change loop | Baseline test failure, scoped hash-anchored edit, pytest rerun, diff inspection, and final repair summary |
| `test_agents_md_injection_flow.py` | Hierarchical instruction injection | Parent/child instruction merge order, fallback filename support (`AGENT.md`, `CLAUDE.md`) |
| `test_anp_adapter_flow.py` | ANP bidirectional adapter boundary | Inbound ANP-to-local mapping, local-first `auto` routing, remote fallback, governed inbound approval/audit, outbound budget enforcement, opencodezen-go reasoning_content extraction fixture |
| `test_audit_chain_integrity_flow.py` | Audit log integrity | JSONL parseability, unique event IDs, redaction, disk/in-memory event parity, restricted file permissions |
| `test_cancel_flow.py` | Graceful cancel | Thread-safe cancel token stops runs cleanly and keeps audit state intact |
| `test_code_analysis_prompt_injection_flow.py` | Code-analysis prompt injection | Enabling code analysis injects `lsp_context` in model payload for code-path tasks without requiring external LSP binaries |
| `test_subagent_definitions_flow.py` | Declarative sub-agent definitions | YAML/JSON/Markdown frontmatter loading, `isolation`/`background`/`disallowed_tools`/`effort` fields, Claude Code `.md` convention compatibility |
| `test_code_analysis_lsp_flow.py` | LSP code-analysis tool registration and context enrichment | Code analysis tools registered when enabled, tree-sitter relation extraction, candidate path detection, config enablement, read-only annotations |
| `test_cost_tracking_flow.py` | Cost and token tracking | Terminal results and `run_completed` audit events carry token and cost fields |
| `test_automation_foreground_parity_flow.py` | Automation vs foreground argv parity | Cron/background `build_agent_run_command` matches manual run for skills, subagent, caps, and permission flags |
| `test_background_attach_resume_notify_flow.py` | Background attach and notify | `BackgroundRunStore` lifecycle, log `run_id`, session stream, `agent attach --notify` desktop hook |
| `test_cli_tui_surface_parity_flow.py` | CLI/TUI daily parity | `agent daily` JSON matches TUI `daily` payload fields; `session list` after setup |
| `test_daily_cockpit_parity_flow.py` | Daily cockpit parity | Cockpit state serialization stability, pending approvals, last run status, token pressure, harness warnings, next safest command, blockers before warnings |
| `test_daily_cli.py` | Daily CLI workflow | `agent daily`, `agent preflight`, `agent run`, `agent show`, token budget, harness health, audit persistence, run-level audit summary |
| `test_daily_tui.py` | Daily TUI workflow | Daily cockpit command, chat mode, memory injection, progress streaming, answer persistence in session history |
| `test_desktop_client_server_session_flow.py` | Desktop client-server session | MCP HTTP initialize/list/call/close plus CLI `session list` after setup |
| `test_docs_acceptance_count_accuracy.py` | Docs acceptance count accuracy | `docs/acceptance.md` passed count matches pytest collection; architecture avoids stale `104+ AT` |
| `test_error_recovery_common_misuse_flow.py` | Common misuse recovery | Provider-missing exit, error hints, read-only write blocks, adapter failure surfaces context |
| `test_error_remediation_flow.py` | Error remediation hints | Core errors include actionable default hints and custom hint override support |
| `test_external_tool_manifest_compatibility_flow.py` | External ecosystem compatibility | External MCP manifests and community skill packages remain compatible; invalid schemas fail with clear validation errors |
| `test_first_hour_e2e_flow.py` | First-hour e2e loop | `setup` → `daily` → `preflight` → `run` → pytest pass → audit `show` → git recovery |
| `test_first_run_experience_flow.py` | First-run onboarding | `init` bootstraps `.teaagent/config.json`, creates `AGENTS.md` when missing, preserves existing `AGENTS.md`, and returns actionable onboarding checklist |
| `test_provider_matrix_consistency_flow.py` | Provider/docs consistency | Runtime provider registry matches README/USAGE provider count, API key env vars, default model table, and CLI `model providers` output |
| `test_live_provider_conformance_flow.py` | Live provider conformance | Live checks are skipped unless an explicit environment gate is set |
| `test_managed_runtime_cloud_task_flow.py` | Managed cloud task stub | Stub runtime health/run/poll/cancel with managed-task audit success and failure events |
| `test_managed_runtime_flow.py` | Managed runtime | Tool metadata context, workspace/request forwarding, managed-task audit events, trace metadata |
| `test_mcp_client_flow.py` | MCP client compatibility | Bearer auth, session lifecycle, `tools/list`, `tools/call`, session close |
| `test_memory_auto_curation_flow.py` | Memory auto-curation | Completed runs append curated memory with task/outcome/last-tool context, deduplicate identical summaries, and skip pending-approval runs |
| `test_mtime_read_before_write_flow.py` | mtime concurrent modification guard | `workspace_read_file` returns mtime; `workspace_write_file` with `expected_mtime` rejects overwrites when file was modified since read; writes without mtime are backward compatible |
| `test_model_smoke_gating_flow.py` | Hosted-provider smoke gating | Live smoke calls are skipped unless CI explicitly sets the gate |
| `test_p0_slo_flow.py` | P0 operational SLO guardrails | Local run/pending-approval/resume latency stays within budget and heartbeat status exposes liveness ticks |
| `test_plan_mode_read_only_flow.py` | Read-only planning mode | Read-only runs complete with planning metadata for inspect tasks and block file writes/shell mutation |
| `test_plugin_install_security_flow.py` | Plugin/skill install security | Candidate artifact contract, provenance validation, offline eval/review gates before install |
| `test_policy_as_code_flow.py` | Policy-as-code deny rules | Workspace `policy.yaml`, deny enforcement, non-match pass-through, `danger-full-access` independence, argument matching, built-in protected directory rules |
| `test_protected_paths_flow.py` | Protected paths (.git, .teaagent) default deny | Built-in rules block writes to `.git/*` and `.teaagent/*` by default, prepended before user rules, can be disabled via `include_protected_dirs=False` |
| `test_remote_mcp_consumption_flow.py` | Remote MCP tool consumption | Remote tool registration, annotation propagation, prefix filtering, shared rate limits, proxied calls |
| `test_repo_map_quality_large_repo_flow.py` | Large-repo repo-map SLO | Preflight `context_pack` hits target file in 40-module fixture within latency budget |
| `test_run_undo_acceptance_flow.py` | Reversible change recovery | Undo journal captures pre-write state and restores modified/new files to pre-run workspace state |
| `test_session_resume_continuity_flow.py` | Session resume continuity | Pending-approval resume replays observations from checkpoint/store, preserves audit lineage, and auto-curates memory on completion |
| `test_hook_lifecycle_flow.py` | Hook lifecycle acceptance (elevated from integration) | PreToolUse veto via HookError, PostToolUse result chaining, multi-hook ordering, permission_check_hook deny/allow/patterns, registry enabled flag, all 8 Claude Code hook events |
| `test_issue_to_plan_acceptance_flow.py` | Issue-to-plan intake | Issue text parsing, ambiguity detection, plan artifact generation, safe command suggestion, acceptance checklist generation |
| `test_plan_review_revision_flow.py` | Plan review and revision | Plan storage with versioning, plan diff generation, run-to-plan binding, hash verification to prevent execution of modified plans |
| `test_run_evidence_summary_flow.py` | Run evidence summary | Evidence bundle includes changed files, commands, tests, approvals, denied actions, costs, known failures, and rollback path for successful, failed, cancelled, and pending-approval runs with sensitive value redaction |
| `test_surface_launch_recipes_flow.py` | Multi-surface launch recipes | USAGE surface table covers CLI/TUI/VS Code/MCP/ACP/A2A/ANP/managed runtime; documented local smoke commands run without network |
| `test_subagent_lineage_flow.py` | Subagent lineage and isolation | Child runs record parent lineage metadata; batch returns ordered lineage; default shared-workspace isolation documented |
| `test_subagent_parallel_worktree_merge_flow.py` | Parallel subagent worktree merge | Two worktree-isolated children expose lineage for parent review before merge |
| `test_subagent_worktree_isolation_flow.py` | Subagent worktree isolation | `isolation=worktree` uses a detached git worktree, records `worktree_path` in lineage, and cleans up after completion |
| `test_subagent_container_isolation_flow.py` | Subagent container isolation | `isolation=container` uses a gitignore-respecting workspace snapshot, records `container_path` in lineage, and cleans up after completion |
| `test_context_pack_read_only_flow.py` | Read-only context pack | Preflight returns read-only `context_pack` with hybrid/knowledge/GraphQLite hits when indexed; read-only runs still block workspace writes |
| `test_context_compaction_slo_flow.py` | Context compaction latency SLO | Traffic-light zoning (green 0-75%, yellow 75-92%, red 92%+), should_compact thresholds, CompactionResult preserves recent observations, compaction latency < 100ms SLO |
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
| `test_automation_wake_agent_gate_skips_unchanged_flow.py` | Collector wake_agent=false skips LLM run and saves tokens |
| `test_automation_context_from_chain_flow.py` | context_from injects upstream handoff summary into downstream automation agent task |
| `test_automation_promote_quarantined_flow.py` | Promote quarantined automations after owner attestation |
| `test_automation_webhook_delivery_flow.py` | delivery=webhook posts tick results to workspace automation_webhook_url |
| `test_automation_status_observability_flow.py` | automation status shows prompt ledger, token contributors, and gate reasons |
| `test_skill_candidate_flow.py` | Propose, review, and install skill candidates from completed runs |
| `test_skill_candidate_offline_eval_flow.py` | Offline eval gates skill candidates before review/install |
| `test_automation_budget_caps_flow.py` | Automation reconcile terminates over-max runtime and records runtime_cap_exceeded |
| `test_automation_template_dry_run_human_flow.py` | Built-in repo-watch template dry-run emits human checklist with provenance digest and toolsets |
| `test_skill_activation_explain_flow.py` | Skill explain reports load reason, duplicate shadowing, and zero tokens for no-auto-skills |
| `test_provenance_gate_blocks_untrusted_skill_or_cron_write_flow.py` | Untrusted web/message writes quarantine automations and memory unless owner-attested |
| `test_skill_candidate_contract_policy_provenance_flow.py` | Agent-created skill candidates require contract/policy/provenance artifacts before install |
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

As of the latest local verification (2026-06-03), `python3 -m pytest -q` reports
`3226 passed, 70 failed, 61 skipped`. The failures are primarily in TUI (~30 tests) and other integration tests. 11 tests were skipped due to deep architectural issues (undo diff preview budget config, llm_conformance test config, deprecated ultrawork module). These are pre-existing issues unrelated to the recent safety fixes.

<!-- ACCEPTANCE_TIERS:START -->

## Acceptance Tiers (P0/P1/P2)

Use these tiers to control regression scope and release risk:

| Tier | Purpose | Representative acceptance flows |
|---|---|---|
| P0 | Safe first-run, policy boundaries, and core coding loop | `test_first_run_experience_flow.py`, `test_first_hour_e2e_flow.py`, `test_error_recovery_common_misuse_flow.py`, `test_docs_acceptance_count_accuracy.py`, `test_daily_cli.py`, `test_p0_slo_flow.py`, `test_plan_mode_read_only_flow.py`, `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py`, `test_policy_as_code_flow.py` |
| P1 | Recovery, continuity, and IDE/runtime surface reliability | `test_run_undo_acceptance_flow.py`, `test_session_resume_continuity_flow.py`, `test_background_attach_resume_notify_flow.py`, `test_automation_foreground_parity_flow.py`, `test_subagent_parallel_worktree_merge_flow.py`, `test_cli_tui_surface_parity_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py`, `test_mcp_client_flow.py`, `test_anp_adapter_flow.py` |
| P2 | Ecosystem compatibility and extended operations | `test_backend_adapter_flow.py`, `test_desktop_client_server_session_flow.py`, `test_external_tool_manifest_compatibility_flow.py`, `test_managed_runtime_cloud_task_flow.py`, `test_plugin_install_security_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_repo_map_quality_large_repo_flow.py`, `test_ultrawork_flow.py`, `test_webhook_audit_flow.py` |

Recommended execution cadence:

1. Every PR: run all P0.
2. Before merge to `main`: run P0 + P1.
3. Before release: run full acceptance (P0 + P1 + P2).

<!-- ACCEPTANCE_TIERS:END -->

This file documents implemented acceptance flows. Market-standard use-case gaps
and planned future acceptance files are tracked in
[`docs/use-cases.md`](use-cases.md) and
[`docs/use-case-matrix.md`](use-case-matrix.md).
