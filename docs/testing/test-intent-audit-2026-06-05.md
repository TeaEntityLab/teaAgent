# Test Intent Audit

**Audit Date:** 2026-06-05

## Executive Summary

- Total tests collected: 3508
- Total test files: 375
- Total test functions: 3492
- Tests with docstrings: 1064
- Total assertions: 8397
- Tests with weak patterns: 107
- Tests with skip decorators: 3
- Total mock calls: 439

## High-Risk Findings

Files with tests having no assertions:

| File | Tests with No Assertions |
|------|---------------------------|
| tests/test_refactoring.py | 1 |
| tests/test_bug_fixes.py | 6 |
| tests/test_memory_pinned.py | 1 |
| tests/test_schema.py | 6 |
| tests/test_hooks.py | 2 |
| tests/test_low_coverage_modules.py | 2 |
| tests/test_tranche_b_governance.py | 1 |
| tests/test_budget.py | 4 |
| tests/test_a2a_registry.py | 1 |
| tests/test_phase5_jit_approval_server.py | 2 |
| tests/test_task005_trust_expiry_enforcement.py | 1 |
| tests/test_agentcard.py | 1 |
| tests/test_governance_fuzz.py | 2 |
| tests/test_tui.py | 2 |
| tests/test_checkpoint.py | 1 |
| tests/test_code_analysis.py | 2 |
| tests/test_a2a_http.py | 1 |
| tests/integration/test_dpop_replay_concurrency.py | 2 |
| tests/integration/test_ultrawork_notify.py | 1 |
| tests/acceptance/test_github_integration_flow.py | 1 |
| tests/acceptance/test_hook_lifecycle_flow.py | 1 |
| tests/acceptance/test_headless_tui.py | 1 |

## Per-File Audit

| File | Tests | Docstrings | Assertions | Avg Asserts/Test | Mocks | Risk Flags |
|------|-------|------------|------------|-----------------|-------|------------|
| tests/test_oauth21_multikey.py | 3 | 0 | 4 | 1.3 | 0 | none |
| tests/test_model_routing.py | 10 | 0 | 31 | 3.1 | 0 | none |
| tests/test_wizard.py | 6 | 0 | 21 | 3.5 | 0 | none |
| tests/test_tournament_parallel_executor.py | 3 | 0 | 13 | 4.3 | 2 | none |
| tests/test_code_analysis_prompt.py | 2 | 0 | 3 | 1.5 | 0 | none |
| tests/test_wasm_runtime.py | 7 | 7 | 15 | 2.1 | 0 | construction_only |
| tests/test_run_evidence.py | 6 | 6 | 27 | 4.5 | 0 | none |
| tests/test_workspace_defaults_toml.py | 5 | 0 | 12 | 2.4 | 0 | none |
| tests/test_quality_matrix.py | 6 | 6 | 19 | 3.2 | 0 | none |
| tests/test_p2_primitives.py | 14 | 0 | 39 | 2.8 | 0 | none |
| tests/test_code_analysis_graph_cache.py | 1 | 0 | 3 | 3.0 | 0 | none |
| tests/test_circular_imports.py | 4 | 4 | 9 | 2.2 | 0 | construction_only |
| tests/test_code_mode_trusted_only.py | 1 | 0 | 1 | 1.0 | 0 | none |
| tests/test_audit_viewer.py | 10 | 0 | 23 | 2.3 | 1 | none |
| tests/test_cli_execution.py | 5 | 5 | 23 | 4.6 | 4 | none |
| tests/test_automation_delivery.py | 10 | 0 | 17 | 1.7 | 0 | none |
| tests/test_subagent_isolation.py | 12 | 5 | 52 | 4.3 | 14 | none |
| tests/test_docs_generator_guardrails.py | 2 | 0 | 6 | 3.0 | 0 | none |
| tests/test_refactoring.py | 22 | 22 | 37 | 1.7 | 1 | no_assertions |
| tests/test_background_unified.py | 6 | 6 | 15 | 2.5 | 0 | none |
| tests/test_context_pack.py | 7 | 0 | 24 | 3.4 | 7 | none |
| tests/test_approval_queue_persistence.py | 8 | 4 | 16 | 2.0 | 0 | none |
| tests/test_team_memory.py | 6 | 0 | 13 | 2.2 | 0 | none |
| tests/test_automation_limits.py | 3 | 0 | 5 | 1.7 | 2 | none |
| tests/test_context_auto_compaction.py | 4 | 4 | 6 | 1.5 | 0 | construction_only |
| tests/test_security_edge_cases.py | 10 | 10 | 12 | 1.2 | 0 | none |
| tests/test_time_to_first_run_kpi.py | 1 | 0 | 3 | 3.0 | 0 | none |
| tests/test_bug_fixes.py | 29 | 29 | 47 | 1.6 | 0 | no_assertions |
| tests/test_validation.py | 8 | 8 | 25 | 3.1 | 5 | none |
| tests/test_human_output.py | 4 | 0 | 12 | 3.0 | 0 | none |
| tests/test_consensus.py | 59 | 59 | 128 | 2.2 | 0 | none |
| tests/test_automation_run_budget.py | 5 | 1 | 6 | 1.2 | 0 | none |
| tests/test_mcp_server.py | 6 | 0 | 13 | 2.2 | 0 | none |
| tests/test_llm.py | 36 | 0 | 67 | 1.9 | 0 | none |
| tests/test_chat_agent.py | 26 | 0 | 81 | 3.1 | 11 | none |
| tests/test_automation_observability_unit.py | 2 | 0 | 13 | 6.5 | 0 | none |
| tests/test_support_helpers.py | 2 | 0 | 7 | 3.5 | 0 | none |
| tests/test_phase5_context_bus.py | 12 | 12 | 24 | 2.0 | 0 | none |
| tests/test_tournament.py | 11 | 11 | 22 | 2.0 | 0 | none |
| tests/test_phase4_coordinator.py | 6 | 6 | 21 | 3.5 | 0 | none |
| tests/test_skill_eval_dataset.py | 6 | 0 | 12 | 2.0 | 0 | none |
| tests/test_federated_sync.py | 21 | 1 | 57 | 2.7 | 1 | none |
| tests/test_strategic_features.py | 9 | 0 | 16 | 1.8 | 0 | none |
| tests/test_cockpit.py | 6 | 6 | 30 | 5.0 | 0 | none |
| tests/test_schema_migration.py | 12 | 0 | 21 | 1.8 | 0 | none |
| tests/test_phase4_agent_factory.py | 7 | 7 | 15 | 2.1 | 0 | none |
| tests/test_use_case_matrix.py | 3 | 0 | 6 | 2.0 | 0 | none |
| tests/test_cli_experiment.py | 8 | 8 | 8 | 1.0 | 0 | none |
| tests/test_workspace_tools.py | 46 | 3 | 101 | 2.2 | 0 | none |
| tests/test_managed_runtime_audit.py | 13 | 0 | 25 | 1.9 | 0 | construction_only |
| tests/test_surface_auth_hardening.py | 6 | 0 | 13 | 2.2 | 0 | none |
| tests/test_automation_ticket.py | 11 | 0 | 20 | 1.8 | 0 | none |
| tests/test_p1_primitives.py | 5 | 0 | 15 | 3.0 | 0 | none |
| tests/test_swarm_agent_execution.py | 2 | 0 | 6 | 3.0 | 3 | construction_only |
| tests/test_prompt.py | 33 | 0 | 57 | 1.7 | 0 | none |
| tests/test_errors.py | 28 | 0 | 39 | 1.4 | 0 | construction_only |
| tests/test_cli_permission_explain.py | 8 | 8 | 30 | 3.8 | 0 | none |
| tests/test_audit_export.py | 13 | 0 | 39 | 3.0 | 0 | none |
| tests/test_p0_harness.py | 11 | 0 | 36 | 3.3 | 0 | none |
| tests/test_conformance_tiers.py | 7 | 0 | 17 | 2.4 | 0 | none |
| tests/test_memory_pinned.py | 26 | 22 | 48 | 1.8 | 1 | placeholder,no_assertions |
| tests/test_permission_explain.py | 5 | 0 | 21 | 4.2 | 0 | none |
| tests/test_git_sandbox.py | 35 | 35 | 88 | 2.5 | 0 | construction_only |
| tests/test_phase6_swarm_score.py | 5 | 0 | 7 | 1.4 | 0 | none |
| tests/test_tranche_bc_governance.py | 7 | 3 | 21 | 3.0 | 0 | none |
| tests/test_daily.py | 3 | 0 | 10 | 3.3 | 0 | none |
| tests/test_preflight.py | 5 | 0 | 20 | 4.0 | 0 | none |
| tests/test_subagent_team_orchestrator.py | 15 | 0 | 29 | 1.9 | 4 | none |
| tests/test_subagent_lineage.py | 4 | 0 | 21 | 5.2 | 5 | none |
| tests/test_skill_router.py | 10 | 10 | 24 | 2.4 | 0 | none |
| tests/test_lore_commit_formatter.py | 1 | 1 | 6 | 6.0 | 0 | none |
| tests/test_oauth21.py | 41 | 1 | 80 | 2.0 | 0 | none |
| tests/test_release_evidence_bundle.py | 1 | 0 | 6 | 6.0 | 0 | none |
| tests/test_compaction_warning.py | 18 | 2 | 34 | 1.9 | 0 | none |
| tests/test_code_graph_integration.py | 1 | 1 | 6 | 6.0 | 0 | none |
| tests/test_run_store.py | 13 | 2 | 36 | 2.8 | 0 | none |
| tests/test_streaming.py | 5 | 0 | 12 | 2.4 | 0 | none |
| tests/test_background_run.py | 7 | 1 | 24 | 3.4 | 0 | none |
| tests/test_openapi.py | 11 | 0 | 28 | 2.5 | 0 | none |
| tests/test_external_backends.py | 15 | 0 | 36 | 2.4 | 11 | none |
| tests/test_sandbox_hardening.py | 23 | 0 | 43 | 1.9 | 2 | none |
| tests/test_subagent.py | 4 | 0 | 6 | 1.5 | 1 | none |
| tests/test_gatherer.py | 5 | 5 | 8 | 1.6 | 0 | none |
| tests/test_phase6_jit_server.py | 2 | 0 | 3 | 1.5 | 0 | none |
| tests/test_skill_candidate_artifacts.py | 5 | 0 | 8 | 1.6 | 0 | none |
| tests/test_resource_monitor.py | 3 | 3 | 5 | 1.7 | 0 | construction_only |
| tests/test_tui_split_pane.py | 4 | 4 | 7 | 1.8 | 0 | none |
| tests/test_inspect_shell_security.py | 8 | 1 | 15 | 1.9 | 0 | none |
| tests/test_phase4_workflow_engine.py | 10 | 10 | 26 | 2.6 | 0 | none |
| tests/test_prefetch_cache_migration.py | 3 | 3 | 15 | 5.0 | 0 | none |
| tests/test_cli_chat.py | 54 | 53 | 146 | 2.7 | 56 | construction_only |
| tests/test_analysis_followups.py | 5 | 0 | 14 | 2.8 | 0 | none |
| tests/test_heartbeat.py | 5 | 0 | 12 | 2.4 | 0 | none |
| tests/test_focus.py | 5 | 5 | 26 | 5.2 | 1 | none |
| tests/test_phase6_docker.py | 3 | 0 | 11 | 3.7 | 12 | none |
| tests/test_guided_recovery.py | 22 | 22 | 78 | 3.5 | 0 | none |
| tests/test_budget_warnings.py | 15 | 4 | 33 | 2.2 | 0 | none |
| tests/test_phase5_agent_factory.py | 3 | 3 | 5 | 1.7 | 0 | none |
| tests/test_code_ontology.py | 8 | 0 | 18 | 2.2 | 0 | construction_only |
| tests/test_approval_async_from_sync.py | 2 | 0 | 3 | 1.5 | 2 | none |
| tests/test_automation_collector.py | 6 | 0 | 24 | 4.0 | 0 | none |
| tests/test_task001_surface_parity.py | 2 | 0 | 7 | 3.5 | 1 | none |
| tests/test_task002_undo_honesty.py | 5 | 0 | 8 | 1.6 | 0 | none |
| tests/test_cli_ergonomics_handlers.py | 27 | 9 | 157 | 5.8 | 3 | none |
| tests/test_oauth_rotation.py | 14 | 0 | 17 | 1.2 | 2 | none |
| tests/test_code_analysis_manager.py | 2 | 0 | 2 | 1.0 | 0 | none |
| tests/test_task003_cost_truth.py | 4 | 0 | 6 | 1.5 | 4 | none |
| tests/test_schema.py | 16 | 0 | 23 | 1.4 | 0 | no_assertions |
| tests/test_acceptance_status_builder.py | 2 | 0 | 2 | 1.0 | 0 | none |
| tests/test_memory_failure.py | 21 | 21 | 44 | 2.1 | 0 | none |
| tests/test_graphqlite_production.py | 5 | 0 | 11 | 2.2 | 0 | none |
| tests/test_refresh_competitive_docs.py | 4 | 0 | 9 | 2.2 | 0 | none |
| tests/test_acceptance_tier_runner.py | 3 | 0 | 6 | 2.0 | 0 | none |
| tests/test_swarm.py | 17 | 7 | 43 | 2.5 | 0 | construction_only |
| tests/test_phase5_workflow_engine.py | 7 | 7 | 13 | 1.9 | 0 | none |
| tests/test_intent.py | 5 | 0 | 14 | 2.8 | 0 | none |
| tests/test_file_tail.py | 2 | 0 | 5 | 2.5 | 0 | none |
| tests/test_oauth21_pg_store.py | 17 | 0 | 27 | 1.6 | 0 | construction_only |
| tests/test_tsb_format.py | 20 | 6 | 43 | 2.1 | 0 | none |
| tests/test_env_config.py | 15 | 0 | 44 | 2.9 | 0 | none |
| tests/test_oauth21_sqlite_store.py | 12 | 0 | 27 | 2.2 | 0 | construction_only |
| tests/test_automation_templates.py | 2 | 0 | 4 | 2.0 | 0 | none |
| tests/test_hads_compliance.py | 2 | 0 | 2 | 1.0 | 0 | none |
| tests/test_hooks.py | 14 | 0 | 17 | 1.2 | 0 | no_assertions |
| tests/test_signature_relay.py | 4 | 0 | 12 | 3.0 | 0 | none |
| tests/test_preflight_env_health.py | 3 | 0 | 7 | 2.3 | 1 | none |
| tests/test_notify_slack_discord.py | 3 | 0 | 9 | 3.0 | 0 | none |
| tests/test_sandbox_profile.py | 10 | 0 | 19 | 1.9 | 0 | construction_only |
| tests/test_security_fixes.py | 20 | 20 | 35 | 1.8 | 0 | none |
| tests/test_replay_cli.py | 9 | 9 | 13 | 1.4 | 0 | none |
| tests/test_first_run.py | 4 | 0 | 17 | 4.2 | 0 | none |
| tests/test_git_tools.py | 11 | 0 | 15 | 1.4 | 0 | none |
| tests/test_tool_dependency_injection.py | 16 | 16 | 39 | 2.4 | 0 | none |
| tests/test_policy_jit.py | 15 | 15 | 37 | 2.5 | 16 | none |
| tests/test_chat_repl_displays_answer.py | 5 | 5 | 14 | 2.8 | 6 | none |
| tests/test_code_analysis_client.py | 2 | 0 | 8 | 4.0 | 0 | none |
| tests/test_governance_hardening.py | 34 | 6 | 58 | 1.7 | 0 | none |
| tests/test_shell_obfuscation_adversarial.py | 40 | 1 | 63 | 1.6 | 0 | none |
| tests/test_remediation_p1_p2.py | 11 | 0 | 19 | 1.7 | 3 | none |
| tests/test_audit_test_quality.py | 18 | 18 | 43 | 2.4 | 0 | none |
| tests/test_low_coverage_modules.py | 54 | 0 | 64 | 1.2 | 20 | no_assertions |
| tests/test_mcp_trust.py | 6 | 6 | 30 | 5.0 | 2 | none |
| tests/test_audit.py | 35 | 12 | 132 | 3.8 | 0 | construction_only |
| tests/test_phase6_skill_writer.py | 2 | 0 | 7 | 3.5 | 0 | none |
| tests/test_skill_executor.py | 3 | 0 | 9 | 3.0 | 0 | none |
| tests/test_e2e_cli_tui_parity.py | 5 | 5 | 10 | 2.0 | 16 | none |
| tests/test_tranche_b_governance.py | 9 | 2 | 15 | 1.7 | 0 | no_assertions |
| tests/test_subagent_approval_queue_integration.py | 4 | 0 | 12 | 3.0 | 0 | none |
| tests/test_session_stream_extended.py | 3 | 0 | 5 | 1.7 | 0 | none |
| tests/test_memory_isolation.py | 12 | 12 | 37 | 3.1 | 0 | none |
| tests/test_sigstore_signer.py | 17 | 17 | 32 | 1.9 | 16 | construction_only |
| tests/test_automation_lifecycle.py | 5 | 5 | 10 | 2.0 | 0 | none |
| tests/test_mcp_http.py | 31 | 0 | 64 | 2.1 | 0 | none |
| tests/test_provenance_gate.py | 5 | 0 | 8 | 1.6 | 0 | none |
| tests/test_governance_adversarial_runtime.py | 13 | 0 | 27 | 2.1 | 2 | none |
| tests/test_ownership.py | 7 | 7 | 11 | 1.6 | 7 | none |
| tests/test_memory.py | 7 | 2 | 26 | 3.7 | 0 | none |
| tests/test_llm_internals.py | 52 | 0 | 67 | 1.3 | 5 | none |
| tests/test_chat_repl_undo_scope.py | 3 | 3 | 10 | 3.3 | 0 | none |
| tests/test_auto_mode.py | 8 | 0 | 21 | 2.6 | 0 | none |
| tests/test_zero_coverage_modules.py | 84 | 0 | 140 | 1.7 | 2 | construction_only |
| tests/test_scratchpad.py | 13 | 0 | 44 | 3.4 | 0 | none |
| tests/test_consensus_cli.py | 11 | 11 | 11 | 1.0 | 0 | none |
| tests/test_anp_adapter.py | 11 | 0 | 27 | 2.5 | 0 | none |
| tests/test_acp_adapter_error_response.py | 1 | 0 | 5 | 5.0 | 6 | none |
| tests/test_docs_consistency.py | 21 | 0 | 22 | 1.0 | 0 | none |
| tests/test_fake_llm_adapter.py | 5 | 5 | 12 | 2.4 | 0 | none |
| tests/test_skill_rag.py | 24 | 24 | 52 | 2.2 | 0 | none |
| tests/test_provider_expansion.py | 6 | 1 | 17 | 2.8 | 0 | construction_only |
| tests/test_subagent_approval_queue_store.py | 37 | 1 | 54 | 1.5 | 0 | none |
| tests/test_phase4_tool_permissions.py | 13 | 13 | 39 | 3.0 | 0 | none |
| tests/test_swarm_locks.py | 8 | 8 | 20 | 2.5 | 0 | none |
| tests/test_budget.py | 11 | 2 | 11 | 1.0 | 3 | no_assertions,mock_only |
| tests/test_managed_runtime.py | 19 | 0 | 36 | 1.9 | 6 | construction_only |
| tests/test_oauth21_redis_store.py | 21 | 0 | 38 | 1.8 | 0 | construction_only |
| tests/test_vfs_sandbox.py | 17 | 17 | 23 | 1.4 | 0 | none |
| tests/test_a2a_registry.py | 13 | 0 | 24 | 1.8 | 0 | no_assertions,construction_only |
| tests/test_automation_promote.py | 3 | 0 | 6 | 2.0 | 0 | none |
| tests/test_automation_observability.py | 4 | 0 | 9 | 2.2 | 0 | none |
| tests/test_use_case_dashboard.py | 2 | 0 | 6 | 3.0 | 0 | none |
| tests/test_phase5_jit_approval_server.py | 11 | 11 | 19 | 1.7 | 0 | no_assertions |
| tests/test_task005_trust_expiry_enforcement.py | 4 | 0 | 5 | 1.2 | 0 | no_assertions |
| tests/test_chat_repl_suspension.py | 1 | 1 | 3 | 3.0 | 0 | none |
| tests/test_agentcard.py | 18 | 0 | 34 | 1.9 | 0 | no_assertions |
| tests/test_run_summary.py | 3 | 2 | 15 | 5.0 | 0 | none |
| tests/test_browser_tools.py | 14 | 4 | 26 | 1.9 | 0 | undocumented_skip,construction_only |
| tests/test_subagent_batch.py | 4 | 1 | 10 | 2.5 | 0 | none |
| tests/test_automation_chain.py | 3 | 0 | 7 | 2.3 | 0 | none |
| tests/test_automation_status.py | 1 | 0 | 5 | 5.0 | 0 | none |
| tests/test_tool_calling_conformance.py | 17 | 0 | 28 | 1.6 | 0 | none |
| tests/test_subagent_defs.py | 2 | 0 | 7 | 3.5 | 0 | none |
| tests/test_subagent_review.py | 12 | 0 | 16 | 1.3 | 0 | none |
| tests/test_automations.py | 4 | 0 | 18 | 4.5 | 0 | none |
| tests/test_tools.py | 12 | 0 | 21 | 1.8 | 0 | none |
| tests/test_cli.py | 54 | 5 | 179 | 3.3 | 34 | none |
| tests/test_smart_hitl.py | 4 | 0 | 13 | 3.2 | 8 | none |
| tests/test_telemetry.py | 17 | 0 | 38 | 2.2 | 0 | construction_only |
| tests/test_llm_transport.py | 4 | 0 | 8 | 2.0 | 7 | none |
| tests/test_plan_storage.py | 36 | 36 | 109 | 3.0 | 0 | none |
| tests/test_sandbox_cli.py | 8 | 8 | 8 | 1.0 | 4 | none |
| tests/test_ergonomics_modules.py | 13 | 0 | 32 | 2.5 | 2 | none |
| tests/test_skill_activation_explain.py | 2 | 0 | 9 | 4.5 | 0 | none |
| tests/test_skill_review.py | 14 | 3 | 32 | 2.3 | 0 | none |
| tests/test_plan_contract.py | 3 | 0 | 4 | 1.3 | 0 | none |
| tests/test_policy.py | 55 | 40 | 155 | 2.8 | 0 | undocumented_skip |
| tests/test_gatherer_skill_rag.py | 7 | 7 | 15 | 2.1 | 0 | none |
| tests/test_skill_eval.py | 3 | 0 | 9 | 3.0 | 0 | none |
| tests/test_full_access_gate.py | 18 | 0 | 34 | 1.9 | 0 | none |
| tests/test_governance_fuzz.py | 13 | 13 | 32 | 2.5 | 0 | no_assertions |
| tests/test_graphqlite_store.py | 4 | 0 | 9 | 2.2 | 1 | none |
| tests/test_decision_log.py | 8 | 0 | 21 | 2.6 | 0 | none |
| tests/test_repo_map_benchmark.py | 8 | 0 | 15 | 1.9 | 0 | none |
| tests/test_tui.py | 129 | 24 | 343 | 2.7 | 38 | no_assertions,construction_only |
| tests/test_sync_cli.py | 9 | 9 | 22 | 2.4 | 0 | none |
| tests/test_phase6_control_plane.py | 5 | 1 | 14 | 2.8 | 0 | none |
| tests/test_aci.py | 3 | 3 | 3 | 1.0 | 0 | construction_only |
| tests/test_issue_intake.py | 43 | 43 | 115 | 2.7 | 0 | none |
| tests/test_tui_interactive.py | 2 | 1 | 6 | 3.0 | 5 | none |
| tests/test_undo_diff_preview.py | 9 | 9 | 42 | 4.7 | 0 | none |
| tests/test_checkpoint.py | 15 | 0 | 26 | 1.7 | 0 | no_assertions |
| tests/test_code_analysis.py | 7 | 0 | 15 | 2.1 | 0 | no_assertions |
| tests/test_latency_tier.py | 6 | 0 | 13 | 2.2 | 0 | none |
| tests/test_validate_docs_consistency_mode.py | 5 | 5 | 8 | 1.6 | 0 | none |
| tests/test_acp_progress.py | 3 | 0 | 17 | 5.7 | 0 | none |
| tests/test_eval.py | 15 | 0 | 24 | 1.6 | 0 | none |
| tests/test_cost_tracker.py | 6 | 0 | 26 | 4.3 | 0 | none |
| tests/test_ergonomics.py | 37 | 1 | 120 | 3.2 | 0 | none |
| tests/test_llm_conformance.py | 3 | 0 | 13 | 4.3 | 1 | none |
| tests/test_phase6_remaining_features.py | 6 | 0 | 15 | 2.5 | 0 | none |
| tests/test_a2a_http.py | 19 | 0 | 35 | 1.8 | 0 | no_assertions,construction_only |
| tests/test_ultrawork.py | 6 | 0 | 15 | 2.5 | 0 | none |
| tests/test_self_healing_merge.py | 7 | 7 | 7 | 1.0 | 0 | construction_only |
| tests/integration/test_eval_report.py | 7 | 0 | 14 | 2.0 | 0 | none |
| tests/integration/test_redaction_config.py | 9 | 1 | 16 | 1.8 | 0 | construction_only |
| tests/integration/test_tsb_lifecycle.py | 5 | 5 | 16 | 3.2 | 0 | none |
| tests/integration/test_schema_migration_live.py | 4 | 0 | 7 | 1.8 | 0 | none |
| tests/integration/test_config_loader.py | 20 | 1 | 38 | 1.9 | 0 | construction_only |
| tests/integration/test_error_hints.py | 4 | 0 | 6 | 1.5 | 0 | none |
| tests/integration/test_plugins.py | 9 | 1 | 17 | 1.9 | 11 | none |
| tests/integration/test_subagent_budget_inheritance.py | 8 | 6 | 29 | 3.6 | 0 | construction_only |
| tests/integration/test_destructive_approval_lifecycle.py | 8 | 3 | 29 | 3.6 | 0 | none |
| tests/integration/test_run_undo.py | 8 | 3 | 25 | 3.1 | 0 | none |
| tests/integration/test_skill_loader.py | 12 | 4 | 20 | 1.7 | 0 | none |
| tests/integration/test_cancel_token.py | 3 | 2 | 4 | 1.3 | 0 | none |
| tests/integration/test_run_export.py | 8 | 1 | 17 | 2.1 | 0 | none |
| tests/integration/test_mcp_tool_adapter.py | 3 | 0 | 8 | 2.7 | 0 | none |
| tests/integration/test_undo_audit.py | 2 | 0 | 8 | 4.0 | 0 | none |
| tests/integration/test_webhook_sink.py | 4 | 1 | 8 | 2.0 | 0 | none |
| tests/integration/test_streaming_tool_calls.py | 4 | 0 | 8 | 2.0 | 0 | none |
| tests/integration/test_runner_cost_tracking.py | 4 | 1 | 12 | 3.0 | 0 | none |
| tests/integration/test_memory_retrieval_ranking.py | 1 | 0 | 2 | 2.0 | 0 | none |
| tests/integration/test_tool_rate_limit.py | 6 | 0 | 9 | 1.5 | 0 | none |
| tests/integration/test_migration_dry_run.py | 7 | 0 | 16 | 2.3 | 0 | none |
| tests/integration/test_benchmark.py | 10 | 0 | 15 | 1.5 | 0 | construction_only |
| tests/integration/test_audit_sink_isolation.py | 5 | 0 | 6 | 1.2 | 0 | none |
| tests/integration/test_a2a_circuit_breaker.py | 7 | 1 | 9 | 1.3 | 7 | none |
| tests/integration/test_approval_ui.py | 12 | 1 | 15 | 1.2 | 0 | none |
| tests/integration/test_dpop_replay_concurrency.py | 4 | 4 | 4 | 1.0 | 0 | no_assertions |
| tests/integration/test_a2a_traceparent.py | 9 | 1 | 17 | 1.9 | 0 | none |
| tests/integration/test_ultrawork_notify.py | 6 | 0 | 10 | 1.7 | 2 | no_assertions |
| tests/integration/test_file_policy.py | 12 | 1 | 25 | 2.1 | 0 | none |
| tests/integration/test_disk_full_degradation.py | 7 | 1 | 11 | 1.6 | 6 | construction_only |
| tests/integration/test_parallel_experiments.py | 4 | 4 | 16 | 4.0 | 0 | none |
| tests/integration/test_run_resume_checkpoint.py | 4 | 1 | 11 | 2.8 | 0 | none |
| tests/integration/test_audit_chain.py | 12 | 4 | 23 | 1.9 | 0 | none |
| tests/acceptance/test_consensus_flow.py | 5 | 0 | 15 | 3.0 | 0 | none |
| tests/acceptance/test_background_attach_resume_notify_flow.py | 2 | 0 | 8 | 4.0 | 1 | none |
| tests/acceptance/test_agent_undo_cli_flow.py | 1 | 0 | 13 | 13.0 | 1 | none |
| tests/acceptance/test_security_mcp_trust_flow.py | 10 | 0 | 27 | 2.7 | 0 | none |
| tests/acceptance/test_daily_cockpit_parity_flow.py | 9 | 9 | 52 | 5.8 | 0 | construction_only |
| tests/acceptance/test_automation_wake_agent_gate_skips_unchanged_flow.py | 1 | 0 | 5 | 5.0 | 0 | none |
| tests/acceptance/test_audit_chain_integrity_flow.py | 5 | 1 | 8 | 1.6 | 0 | none |
| tests/acceptance/test_subagent_directory_snapshot_isolation_flow.py | 2 | 1 | 6 | 3.0 | 4 | none |
| tests/acceptance/test_skill_activation_explain_flow.py | 1 | 0 | 14 | 14.0 | 0 | none |
| tests/acceptance/test_security_tls_server_flow.py | 5 | 1 | 8 | 1.6 | 0 | none |
| tests/acceptance/test_skill_index_only_prompt_flow.py | 1 | 0 | 7 | 7.0 | 0 | none |
| tests/acceptance/test_plugin_install_security_flow.py | 1 | 0 | 8 | 8.0 | 0 | none |
| tests/acceptance/test_run_undo_failed_write_flow.py | 1 | 0 | 4 | 4.0 | 0 | none |
| tests/acceptance/test_automation_budget_caps_flow.py | 1 | 0 | 2 | 2.0 | 2 | none |
| tests/acceptance/test_automation_status_observability_flow.py | 1 | 0 | 7 | 7.0 | 0 | none |
| tests/acceptance/test_mcp_client_flow.py | 1 | 0 | 8 | 8.0 | 0 | none |
| tests/acceptance/test_error_remediation_flow.py | 7 | 0 | 14 | 2.0 | 0 | none |
| tests/acceptance/test_automation_template_dry_run_human_flow.py | 1 | 0 | 10 | 10.0 | 0 | none |
| tests/acceptance/test_skill_candidate_flow.py | 2 | 0 | 12 | 6.0 | 2 | none |
| tests/acceptance/test_github_integration_flow.py | 5 | 2 | 7 | 1.4 | 0 | no_assertions |
| tests/acceptance/test_webhook_audit_flow.py | 4 | 1 | 7 | 1.8 | 0 | none |
| tests/acceptance/test_protected_paths_flow.py | 8 | 0 | 14 | 1.8 | 0 | none |
| tests/acceptance/test_cli_tui_surface_parity_flow.py | 2 | 0 | 10 | 5.0 | 0 | none |
| tests/acceptance/test_subagent_lineage_flow.py | 1 | 0 | 9 | 9.0 | 1 | none |
| tests/acceptance/test_skill_candidate_offline_eval_flow.py | 1 | 0 | 6 | 6.0 | 1 | none |
| tests/acceptance/test_first_hour_e2e_flow.py | 1 | 0 | 19 | 19.0 | 1 | none |
| tests/acceptance/test_first_run_experience_flow.py | 3 | 0 | 15 | 5.0 | 0 | none |
| tests/acceptance/test_desktop_client_server_session_flow.py | 1 | 0 | 8 | 8.0 | 0 | none |
| tests/acceptance/test_model_smoke_gating_flow.py | 2 | 0 | 9 | 4.5 | 0 | none |
| tests/acceptance/test_run_undo_acceptance_flow.py | 1 | 0 | 9 | 9.0 | 0 | none |
| tests/acceptance/test_skill_candidate_contract_policy_provenance_flow.py | 2 | 0 | 21 | 10.5 | 0 | none |
| tests/acceptance/test_subagent_worktree_isolation_flow.py | 1 | 0 | 3 | 3.0 | 2 | none |
| tests/acceptance/test_agents_md_injection_flow.py | 2 | 0 | 6 | 3.0 | 0 | none |
| tests/acceptance/test_mtime_read_before_write_flow.py | 6 | 0 | 9 | 1.5 | 0 | none |
| tests/acceptance/test_session_resume_continuity_flow.py | 1 | 0 | 16 | 16.0 | 2 | none |
| tests/acceptance/test_run_evidence_summary_flow.py | 9 | 9 | 31 | 3.4 | 0 | none |
| tests/acceptance/test_workspace_edit_flow.py | 1 | 0 | 7 | 7.0 | 0 | none |
| tests/acceptance/test_automation_context_from_chain_flow.py | 1 | 0 | 7 | 7.0 | 1 | none |
| tests/acceptance/test_docs_acceptance_count_accuracy.py | 2 | 0 | 5 | 2.5 | 0 | none |
| tests/acceptance/test_a2a_federation_flow.py | 1 | 0 | 8 | 8.0 | 0 | none |
| tests/acceptance/test_security_plugin_system_flow.py | 12 | 0 | 21 | 1.8 | 0 | none |
| tests/acceptance/test_daily_ergonomics_flow.py | 1 | 0 | 16 | 16.0 | 0 | none |
| tests/acceptance/test_security_readiness_flow.py | 10 | 0 | 16 | 1.6 | 0 | none |
| tests/acceptance/test_managed_runtime_cloud_task_flow.py | 3 | 0 | 12 | 4.0 | 0 | none |
| tests/acceptance/test_managed_runtime_flow.py | 1 | 0 | 12 | 12.0 | 0 | none |
| tests/acceptance/test_automation_run_ticket_self_contained_flow.py | 5 | 0 | 19 | 3.8 | 0 | none |
| tests/acceptance/test_remote_mcp_consumption_flow.py | 5 | 0 | 8 | 1.6 | 0 | none |
| tests/acceptance/test_approval_root_cli_flow.py | 5 | 4 | 14 | 2.8 | 1 | none |
| tests/acceptance/test_subagent_definitions_flow.py | 8 | 0 | 23 | 2.9 | 0 | none |
| tests/acceptance/test_skill_marketplace_flow.py | 5 | 0 | 14 | 2.8 | 0 | construction_only |
| tests/acceptance/test_policy_denial_reason_code_flow.py | 3 | 0 | 5 | 1.7 | 0 | none |
| tests/acceptance/test_code_analysis_lsp_flow.py | 7 | 0 | 15 | 2.1 | 0 | none |
| tests/acceptance/test_automation_foreground_parity_flow.py | 1 | 0 | 3 | 3.0 | 0 | none |
| tests/acceptance/test_context_compaction_slo_flow.py | 18 | 0 | 47 | 2.6 | 0 | none |
| tests/acceptance/test_browser_tools_integration_flow.py | 5 | 2 | 7 | 1.4 | 0 | none |
| tests/acceptance/test_automation_promote_quarantined_flow.py | 1 | 0 | 6 | 6.0 | 0 | none |
| tests/acceptance/test_security_ssh_signatures_flow.py | 9 | 0 | 15 | 1.7 | 0 | none |
| tests/acceptance/test_sandbox_enhancement_flow.py | 6 | 0 | 11 | 1.8 | 0 | none |
| tests/acceptance/test_selected_skills_prevent_eager_skill_prompt_bloat_flow.py | 1 | 0 | 6 | 6.0 | 0 | none |
| tests/acceptance/test_security_subagent_run_context_flow.py | 7 | 0 | 9 | 1.3 | 0 | none |
| tests/acceptance/test_security_security_env_flow.py | 14 | 0 | 10 | 0.7 | 0 | none |
| tests/acceptance/test_agent_fix_test_review_flow.py | 1 | 0 | 10 | 10.0 | 0 | none |
| tests/acceptance/test_vscode_mcp_runtime_smoke_flow.py | 1 | 0 | 10 | 10.0 | 0 | none |
| tests/acceptance/test_policy_as_code_flow.py | 4 | 1 | 11 | 2.8 | 0 | none |
| tests/acceptance/test_context_pack_read_only_flow.py | 5 | 0 | 28 | 5.6 | 2 | none |
| tests/acceptance/test_external_tool_manifest_compatibility_flow.py | 2 | 0 | 9 | 4.5 | 1 | none |
| tests/acceptance/test_first_session_setup_flow.py | 3 | 0 | 19 | 6.3 | 0 | none |
| tests/acceptance/test_backend_adapter_flow.py | 1 | 0 | 7 | 7.0 | 0 | none |
| tests/acceptance/test_memory_auto_curation_flow.py | 3 | 0 | 11 | 3.7 | 0 | none |
| tests/acceptance/test_daily_cli.py | 3 | 0 | 35 | 11.7 | 3 | none |
| tests/acceptance/test_security_read_only_gate_flow.py | 11 | 0 | 13 | 1.2 | 0 | construction_only |
| tests/acceptance/test_code_analysis_prompt_injection_flow.py | 1 | 0 | 3 | 3.0 | 0 | none |
| tests/acceptance/test_security_vote_relay_flow.py | 9 | 0 | 18 | 2.0 | 0 | construction_only |
| tests/acceptance/test_automation_webhook_delivery_flow.py | 1 | 0 | 9 | 9.0 | 0 | none |
| tests/acceptance/test_no_agent_automation_delivers_script_output_flow.py | 2 | 0 | 10 | 5.0 | 0 | none |
| tests/acceptance/test_live_provider_conformance_flow.py | 3 | 0 | 13 | 4.3 | 0 | none |
| tests/acceptance/test_cancel_flow.py | 3 | 0 | 3 | 1.0 | 0 | none |
| tests/acceptance/test_provider_matrix_consistency_flow.py | 1 | 0 | 14 | 14.0 | 0 | none |
| tests/acceptance/test_security_approval_manager_flow.py | 20 | 0 | 33 | 1.6 | 0 | construction_only |
| tests/acceptance/test_automation_permission_and_autopropose_flow.py | 2 | 0 | 11 | 5.5 | 1 | none |
| tests/acceptance/test_cost_tracking_flow.py | 2 | 0 | 10 | 5.0 | 0 | none |
| tests/acceptance/test_daily_tui.py | 3 | 0 | 26 | 8.7 | 0 | none |
| tests/acceptance/test_surface_launch_recipes_flow.py | 2 | 0 | 9 | 4.5 | 0 | none |
| tests/acceptance/test_ultrawork_flow.py | 1 | 0 | 10 | 10.0 | 0 | none |
| tests/acceptance/test_cloud_tasks_flow.py | 4 | 0 | 12 | 3.0 | 0 | none |
| tests/acceptance/test_repo_map_quality_large_repo_flow.py | 2 | 0 | 9 | 4.5 | 0 | none |
| tests/acceptance/test_hook_lifecycle_flow.py | 15 | 0 | 25 | 1.7 | 0 | no_assertions |
| tests/acceptance/test_issue_to_plan_acceptance_flow.py | 8 | 8 | 27 | 3.4 | 0 | construction_only |
| tests/acceptance/test_from_plan_cli_flow.py | 1 | 0 | 7 | 7.0 | 1 | none |
| tests/acceptance/test_plan_review_revision_flow.py | 8 | 8 | 30 | 3.8 | 0 | none |
| tests/acceptance/test_error_recovery_common_misuse_flow.py | 5 | 0 | 11 | 2.2 | 2 | none |
| tests/acceptance/test_guided_recovery_flow.py | 5 | 5 | 22 | 4.4 | 0 | none |
| tests/acceptance/test_messaging_gateway_flow.py | 8 | 0 | 10 | 1.2 | 0 | construction_only |
| tests/acceptance/test_plan_mode_read_only_flow.py | 3 | 0 | 16 | 5.3 | 3 | none |
| tests/acceptance/test_anp_adapter_flow.py | 6 | 0 | 19 | 3.2 | 0 | none |
| tests/acceptance/test_skill_install_flow.py | 12 | 0 | 28 | 2.3 | 3 | none |
| tests/acceptance/test_vscode_extension_mcp_boot_flow.py | 2 | 0 | 4 | 2.0 | 0 | none |
| tests/acceptance/test_subagent_parallel_worktree_merge_flow.py | 2 | 0 | 12 | 6.0 | 4 | none |
| tests/acceptance/test_security_storage_flow.py | 9 | 0 | 10 | 1.1 | 0 | none |
| tests/acceptance/test_headless_tui.py | 17 | 6 | 27 | 1.6 | 7 | no_assertions,construction_only |
| tests/acceptance/test_plan_cli_flow.py | 1 | 0 | 8 | 8.0 | 0 | none |
| tests/acceptance/test_p0_slo_flow.py | 4 | 3 | 26 | 6.5 | 0 | none |
| tests/acceptance/test_provenance_gate_blocks_untrusted_skill_or_cron_write_flow.py | 1 | 0 | 13 | 13.0 | 0 | none |
| tests/acceptance/test_agent_teams_flow.py | 4 | 0 | 9 | 2.2 | 0 | none |
| tests/regression/test_contract_session_resume.py | 3 | 0 | 7 | 2.3 | 0 | none |
| tests/regression/test_contract_audit_chain.py | 5 | 0 | 8 | 1.6 | 0 | none |
| tests/regression/test_contract_policy.py | 3 | 0 | 3 | 1.0 | 0 | none |
| tests/regression/test_contract_approval.py | 9 | 0 | 16 | 1.8 | 0 | none |
| tests/e2e/test_end_to_end.py | 3 | 0 | 7 | 2.3 | 0 | none |
| tests/policy/test_permission_matrix.py | 3 | 0 | 7 | 2.3 | 0 | none |

## Remediation Queue

Prioritized by risk (security/audit paths first, then P0 acceptance, then others):

| Priority | File | Issue | Action |
|----------|------|-------|--------|
| P1 | tests/acceptance/test_github_integration_flow.py | 1 tests with no assertions | Add behavior assertions |
| P1 | tests/acceptance/test_headless_tui.py | 1 tests with no assertions | Add behavior assertions |
| P1 | tests/acceptance/test_hook_lifecycle_flow.py | 1 tests with no assertions | Add behavior assertions |
| P2 | tests/integration/test_dpop_replay_concurrency.py | 2 tests with no assertions | Add behavior assertions |
| P2 | tests/integration/test_ultrawork_notify.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_a2a_http.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_a2a_registry.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_agentcard.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_budget.py | 4 tests with no assertions | Add behavior assertions |
| P3 | tests/test_bug_fixes.py | 6 tests with no assertions | Add behavior assertions |
| P3 | tests/test_checkpoint.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_code_analysis.py | 2 tests with no assertions | Add behavior assertions |
| P3 | tests/test_governance_fuzz.py | 2 tests with no assertions | Add behavior assertions |
| P3 | tests/test_hooks.py | 2 tests with no assertions | Add behavior assertions |
| P3 | tests/test_low_coverage_modules.py | 2 tests with no assertions | Add behavior assertions |
| P3 | tests/test_memory_pinned.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_phase5_jit_approval_server.py | 2 tests with no assertions | Add behavior assertions |
| P3 | tests/test_refactoring.py | 1 tests with no assertions | Add behavior assertions |
| P3 | tests/test_schema.py | 6 tests with no assertions | Add behavior assertions |
| P3 | tests/test_task005_trust_expiry_enforcement.py | 1 tests with no assertions | Add behavior assertions |
| ... | 2 more files | ... | ... |

## Methodology

This audit uses AST analysis to scan test files for:
- Test function discovery
- Docstring presence
- Assertion counting
- Mock usage detection
- Weak pattern identification (no assertions, assert True, mock-only, construction-only, undocumented skip)

Weak patterns detected:
- `no_assertions`: Test functions with zero assert statements
- `placeholder`: Test functions whose body is only `pass`
- `assert_true`: Tests using `assert True` without meaningful checks
- `mock_only`: Tests with mocks but no state/output assertions
- `construction_only`: Tests whose assertions only prove object construction or truthiness
- `undocumented_skip`: Skipped tests without an explicit pytest skip reason

## Next Steps

1. Review files with high-risk findings
2. Add behavior assertions to construction-only tests
3. Document skip reasons for optional dependencies
4. Remove or implement placeholder tests