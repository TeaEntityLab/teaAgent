# Backlog Priority

Prioritized by impact order: security and production risk → core platform capabilities → developer experience and ecosystem.

Last updated: 2026-05-31 (Phase 4–6 Beta hardening shipped; VS Code extension removed - does not exist in repo)

---

## Implemented

Items below were deferred at baseline and have since been implemented in-repo.

| Item | Sprint | Files |
|------|--------|-------|
| Key ring CLI support (`--oauth-key-ring-file`, `--oauth-active-kid`, fail-closed validation) | P0-r1 | `cli/_mcp_parsers.py`, `cli/_handlers/_mcp.py` |
| External state checkpoint store (`InMemoryCheckpointStore`, `SQLiteCheckpointStore`, `--checkpoint-store` CLI) | P0-r1 | `teaagent/checkpoint.py`, `runner/_core.py`, `chat_agent.py` |
| DPoP replay TTL configurable (`dpop_replay_ttl` + `--oauth-dpop-replay-ttl` CLI) | P0-r1 | `oauth21/_server.py`, `cli/_mcp_parsers.py` |
| OAuth key rotation overlap window (`OAuthKeyRing.rotate`, `key_for_validation`, `--oauth-rotation-window`) | P0-r2 | `oauth21/_store.py`, `oauth21/_server.py`, `oauth21/_resource.py` |
| Code Mode sandbox profile matrix (`SandboxProfile` enum, `default_sandbox`, `validate_runtime_support`) | P0-r2 | `code_mode/_types.py`, `code_mode/__init__.py` |
| LLM-as-Judge scoring (`JudgeScore`, `run_eval_with_judge`, `make_llm_judge_fn`) | P1-r1 | `teaagent/eval.py` |
| AgentCard + InMemoryAgentRegistry + `agent card` CLI | P1-r1 | `teaagent/agentcard.py`, `cli/_agent_parsers.py` |
| Managed runtime interface (`ManagedRuntimeAdapter` Protocol, `ManagedAgentRunner`, provider stubs) | P1-r2 | `teaagent/managed_runtime.py` |
| LATENCY conformance tier (p50/p95 sampling, threshold check, `latency_samples`/`latency_threshold_ms` params) | P1-r2 | `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| SQLiteAgentRegistry + A2ADispatcher (persistent A2A registry, in-process routing) | P1-r2 | `teaagent/agentcard.py` |
| Extended conformance tiers: `STREAMING`, `STRUCTURED_OUTPUT` | P2-r1 | `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| OpenAPI 3.1 schema auto-generation from `ToolRegistry` + `workspace openapi` CLI | P2-r1 | `teaagent/openapi.py`, `cli/_misc_parsers.py` |
| Web audit viewer (`AuditViewerServer`, HTML/JSON routes, `audit serve` CLI) | P2-r2 | `teaagent/audit_viewer.py`, `cli/_handlers/_audit.py` |
| Schema migration framework (`SchemaMigration`, `SQLiteMigrationStore`, `MigrationRunner`, `doctor migration` CLI) | P2-r2 | `teaagent/schema_migration.py`, `cli/_handlers/_doctor.py` |
| Code Mode kernel sandbox hardening (`seccomp_profile`, `apparmor_profile`, `selinux_label`, `oci_runtime` on `ContainerCodeModeBackend`; `IsolateCodeModeBackend` gVisor wrapper; `sandbox_profile_selected`/`sandbox_violation` audit events; `profile`+`audit_logger` params on `execute_code_mode`) | P0-r3 | `code_mode/_types.py`, `code_mode/_container.py`, `code_mode/_isolate.py`, `code_mode/__init__.py` |
| Cross-host OAuthStore persistence (`PostgreSQLOAuthStore` with `DELETE…RETURNING` atomic consume; `RedisOAuthStore` with Lua-script atomic consume, NX nonce/code saves, configurable key prefix) | P0-r3 | `oauth21/_pg_store.py`, `oauth21/_redis_store.py`, `oauth21/__init__.py` |
| Managed runtime audit events (`managed_task_started/completed/failed` on `ManagedAgentRunner.run`; `audit_logger`+`run_id` params); tool-context forwarding for Anthropic and OpenAI runtimes | P1-r3 | `teaagent/managed_runtime.py` |
| Extended conformance tiers: `TOOL_CALLING` (invokes `get_current_time` tool, checks `tool_calls`); `SAFETY` (API-level block + text refusal taxonomy); `LLMToolDefinition`, `LLMToolCall`, `SafetyCategory`, `LLMSafetyBlock` types; tool wiring in all three adapters | P1-r3 | `llm/_types.py`, `llm/_adapters.py`, `llm/__init__.py`, `llm_conformance/_types.py`, `llm_conformance/_runner.py` |
| A2A HTTP discovery + wire protocol: `A2ADiscoveryServer` (serves `/.well-known/agent.json`, handles POST `/a2a/task`); `A2AClient` (`fetch_card`, `delegate`); `FederatedAgentRegistry` (TTL-cached pulls from remote endpoints) | P1-r3 | `teaagent/agentcard.py` |
| GraphQLite production deployment (`GraphQLitePersistentStore`, `GraphQLiteProductionConfig`, index strategy, migration integration, `graphqlite migrate` CLI, production deployment guide) | P2-r3 | `teaagent/graphqlite_production.py`, `docs/graphqlite-production.md`, `cli/_handlers/_misc.py`, `cli/_misc_parsers.py` |
| Hosted doc site infrastructure (`pdoc` dependency, `scripts/build_docs.py` build script, class-level docstrings on core modules) | P2-r3 | `pyproject.toml`, `scripts/build_docs.py`, `teaagent/tools.py`, `teaagent/runner/_core.py`, `teaagent/budget.py`, `teaagent/policy.py`, `teaagent/memory.py` |
| ANP bidirectional adapter governed federation (`ANPGovernedService`, audit correlation, approval/budget invariants) | P1 | `teaagent/anp_adapter.py`, `tests/acceptance/test_anp_adapter_flow.py`, `docs/adr/0007-anp-adapter-boundary.md` |
| Daily-use ergonomics (init, providerless CLI, recipes, sessions, background/attach, model capabilities, KPI) | P1 | `teaagent/ergonomics/`, `teaagent/recipes/`, `scripts/measure_time_to_first_run.py`, `examples/ergonomics/` |
| mtime read-before-write concurrent modification guard (`workspace_write_file` rejects overwrites on mtime mismatch; `workspace_read_file` returns `mtime`; backward compatible) | P0 | `teaagent/workspace_tools/_files.py`, `tests/acceptance/test_mtime_read_before_write_flow.py` |
| Protected paths default deny rules (`.git/*` and `.teaagent/*` blocked by default in `FilePolicy`; `load_file_policy(include_protected_dirs=)` gating) | P0 | `teaagent/file_policy.py`, `tests/acceptance/test_protected_paths_flow.py` |
| LSP code analysis acceptance (7 tests covering tool registration, tree-sitter relations, candidate path extraction, config enablement) | P0 | `tests/acceptance/test_code_analysis_lsp_flow.py` |
| Declarative sub-agent definitions with Markdown frontmatter (`.md` file support matching Claude Code `.claude/agents/*.md` convention; `isolation`/`background`/`disallowed_tools`/`effort` fields on `SubagentDef`) | P1 | `teaagent/subagents/_types.py`, `teaagent/subagents/_loader.py`, `tests/acceptance/test_subagent_definitions_flow.py` |
| Context compaction latency SLO (traffic-light zoning boundary tests; compaction preserves recent observations; latency < 100ms SLO) | P1 | `teaagent/context.py`, `tests/acceptance/test_context_compaction_slo_flow.py` |
| Hook lifecycle acceptance elevation (16 tests: PreToolUse veto, PostToolUse chaining, permission_check_hook deny/allow/patterns, all 8 Claude Code events, registry enabled flag) | P1 | `tests/acceptance/test_hook_lifecycle_flow.py` |
| Architecture comparison matrix documenting TeaAgent vs Claude Code/Codex/OpenCode feature coverage | P2 | `docs/architecture.md` |
| Use-case matrix updated with LSP, sub-agent orchestration, mtime guard, and protected paths entries | P2 | `docs/use-cases.md`, `docs/use-case-matrix.md` |
| 5-Loop Governance Hardening (Tool, Coding, Audit, Memory, Swarm) | P0 | `teaagent/tools.py`, `teaagent/governance/tool_lint.py`, `teaagent/selftest.py`, `teaagent/plan_mode.py`, `teaagent/workflow_engine.py`, `teaagent/audit.py`, `teaagent/memory/failure_card.py`, `teaagent/swarm.py`, `teaagent/tournament/`, `docs/architecture.md` |

---

## Open — High (P0)

_No open P0 items._

---

## Future Roadmap — Phase 4-5 (Beta — core shipped, E2E hardening ongoing)

Phase 4 (consensus) and Phase 5 (sandbox routing + execution) are **Beta** with CLI,
unit tests, and acceptance flows. Optional hardening (async votes, skill execution,
docker-smoke CI) is shipped. See [architecture.md](architecture.md#phase-4-5-roadmap-beta).

### Phase 4: Federated Swarm Consensus & Peer Attestations — **Beta**

| Task | Priority | Status | Evidence |
|------|----------|--------|----------|
| Consensus data structures | P1 | Shipped | `teaagent/consensus.py`, `tests/test_consensus.py` |
| Peer identity management | P1 | Shipped | `PeerRegistry`, CLI `teaagent consensus peers` |
| Voting mechanism | P1 | Shipped | `VotingMechanism`, `tests/test_consensus.py` |
| Consensus engine | P0 | Shipped | `ConsensusEngine`, attestation + pre-approval |
| Swarm integration | P0 | Shipped | `SwarmManager` + pre-approval gate |
| CLI commands | P2 | Shipped | `teaagent/cli/_handlers/_consensus.py` |
| E2E acceptance | P2 | Shipped | `tests/acceptance/test_consensus_flow.py` |

### Phase 5: Hardened Sandbox Virtualization — **Beta**

| Task | Priority | Status | Evidence |
|------|----------|--------|----------|
| Docker resource limits | P1 | Shipped | `prepare_subagent_isolation` `--cpus` / `--memory` |
| WASM runtime wrapper | P0 | Shipped | `teaagent/wasm_runtime.py`, `tests/test_wasm_runtime.py` |
| Skill execution routing | P1 | Shipped | `teaagent/skill_router.py`, `isolation=auto` on subagents |
| Resource monitoring | P2 | Shipped | `teaagent/resource_monitor.py`, `teaagent sandbox monitor` |
| CLI commands | P2 | Shipped | `teaagent/cli/_handlers/_sandbox.py` |
| E2E acceptance | P2 | Shipped | `tests/acceptance/test_sandbox_enhancement_flow.py` |

### Remaining (optional hardening)

| Task | Priority | Status | Description |
|------|----------|--------|-------------|
| Async consensus UX | P2 | Shipped | Non-blocking vote collection via `async_vote_collection` + poll |
| WASM skill execution | P1 | Shipped | `teaagent/skill_executor.py`, `teaagent sandbox execute` |
| Docker dogfood benchmarks | P2 | Shipped | Optional CI `docker-smoke` job (`tests/test_phase6_docker.py`) |

### Phase 6: Skill writer, docker monitor, control plane — **Beta**

| Task | Priority | Status | Evidence |
|------|----------|--------|----------|
| SkillWriter publish + review | P1 | Shipped | `teaagent/skill_writer.py`, `tests/test_phase6_skill_writer.py` |
| Docker resource monitor + abort | P1 | Shipped | `teaagent/docker_sandbox.py`, `tests/test_phase6_docker.py` |
| Prompt tournament scoring | P2 | Shipped | `teaagent/swarm.py`, `tests/test_phase6_swarm_score.py` |
| Control plane HTTP + dashboard | P2 | Shipped | `teaagent/control_plane_api.py`, `tests/test_phase6_control_plane.py` |
| Control plane CLI | P2 | Shipped | `teaagent control-plane serve` |
| JIT approval server | P2 | Shipped | `teaagent/jit_approval_server.py`, `tests/test_phase6_jit_server.py` |
| External peer voting UX | P2 | Shipped | `teaagent consensus wait`, `votes-import`, `import_votes_batch` |
| Comparator tournament from subagent results | P2 | Shipped | `teaagent/tournament/benchmark.py`, `tests/test_phase6_remaining_features.py` |
| Control plane swarm dogfood | P2 | Shipped | `teaagent/control_plane_bridge.py`, `SwarmManager(control_plane_state=…)` |
| WASM skill contract CLI | P2 | Shipped | `teaagent/wasm_skill.py`, `teaagent sandbox wasm-contract` |
| SSH vote relay (production peers) | P1 | Shipped | `teaagent/vote_relay.py`, `teaagent consensus relay` |
| WASM skill CI template workflow | P2 | Shipped | `.github/workflows/wasm-skill-build.yml`, `docs/wasm-skill-ci.md` |
| Multi-tenant control plane | P2 | Shipped | `teaagent/control_plane_tenant.py`, `X-TeaAgent-Tenant` |
| Relay mTLS + API tokens | P1 | Shipped | `teaagent/surface_auth.py`, `teaagent/tls_server.py`, `docs/http-surface-auth.md` |
| Per-tenant authZ + reverse proxy templates | P2 | Shipped | `templates/reverse-proxy/`, control plane bearer enforcement |

---

## Open — Daily-use ergonomics

_All items from the 2026-05-22 ergonomics tranche are shipped._ Future work is strategic (hosted surfaces, repo-map quality eval) under ongoing maintenance below.

---

## Recently completed (competitive refresh, 2026-05-22)

| Item | Notes |
|------|-------|
| Docs/provider architecture drift guard | `scripts/validate_docs_consistency.py` now checks README/USAGE/architecture counts against `PROVIDER_CONFIGS`, unique credential env vars (including shared `CLOUDFLARE_API_TOKEN` / `OPENCODEZEN_API_KEY`), and survey doc freshness; `docs/architecture.md` updated to 13 providers. |
| Mode and safety comparison matrix | `docs/USAGE.md` matrix maps permission modes, Plan/Auto/Code lanes, shell mutation, approvals, audit, and rollback; validator enforces every `PermissionMode` value and required topics. |
| Multi-surface launch recipes | `docs/USAGE.md` “Choose Your Surface” table with CLI/TUI/VS Code/MCP/ACP/A2A/ANP/managed-runtime recipes; `validate_surface_recipes` + `test_surface_launch_recipes_flow.py` smoke local commands. |
| Subagent lineage and isolation hardening | Child runs record lineage metadata; `isolation: shared`, `worktree`, or `container` snapshot; `worktree_path`/`container_path` in lineage; `test_subagent_worktree_isolation_flow.py`, `test_subagent_container_isolation_flow.py`. |
| Repo-map / context pack for coding runs | `build_context_pack` on `agent preflight`; candidate files, memories, optional LSP symbols, hybrid/knowledge/GraphQLite read-only hits; `test_context_pack_read_only_flow.py`. |
| Plugin/skill compatibility catalog | `docs/plugin-skill-catalog.md` with fixture-backed `validate_plugin_skill_catalog`. |
| Competitive use-case dashboard refresh | Matrix/HTML include survey review date and open P1/P2 gap counts via `build_use_case_matrix.py` + `render_use_case_dashboard.py`. |
| Periodic mainstream-agent refresh cadence | `docs/release-checklist.md` requires survey refresh before minor releases or protocol ADRs. |
| Everyday usage onboarding | README “Daily Use in 5 Commands”, USAGE daily section, cli recipe table, TUI `daily → preflight → ask → resume` flow. |

---

## Ongoing maintenance (competitive refresh complete)

Competitive-refresh feature work is shipped. Before minor releases or protocol ADRs, run:

```bash
python3 scripts/refresh_competitive_docs.py
```

Then manually refresh [scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md) when upstream signals change (see [docs/release-checklist.md](release-checklist.md)).

| Cadence | What to keep in sync |
|---------|----------------------|
| Survey | `Last reviewed` date, source table, `docs/use-cases.md` differentiators |
| Docs drift | `validate_docs_consistency.py` (providers, mode matrix, surface recipes, catalog) |
| Coverage artifacts | `docs/acceptance.md` count, `docs/use-case-matrix.md`, `docs/use-case-matrix.html` via `refresh_competitive_docs.py --check` (CI/review) and `refresh_competitive_docs.py` (intentional regeneration) |
| Extension surfaces | `docs/plugin-skill-catalog.md`, `docs/USAGE.md`, `docs/cli.md` when hooks, isolation modes, or preflight/context APIs change |
| New index backends | `teaagent/context_pack.py` read-only graph evidence when adding search stores |
| Strategic P2 research | hosted/cloud surface docs, background sessions, desktop/client-server packaging, repo-map quality evaluation |
| Ergonomics KPI | `python3 scripts/measure_time_to_first_run.py --write docs/ergonomics-kpi.json` before regenerating the use-case matrix |
