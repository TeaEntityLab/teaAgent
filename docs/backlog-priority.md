# Backlog Priority

Prioritized by impact order: security and production risk → core platform capabilities → developer experience and ecosystem.

Last updated: 2026-05-22

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
| IDE integration - VS Code extension (command palette, task provider, terminal profile, TeaAgent output channel) | P2-r3 | `vscode/package.json`, `vscode/src/extension.ts` |
| Hosted doc site infrastructure (`pdoc` dependency, `scripts/build_docs.py` build script, class-level docstrings on core modules) | P2-r3 | `pyproject.toml`, `scripts/build_docs.py`, `teaagent/tools.py`, `teaagent/runner/_core.py`, `teaagent/budget.py`, `teaagent/policy.py`, `teaagent/memory.py` |
| ANP bidirectional adapter governed federation (`ANPGovernedService`, audit correlation, approval/budget invariants) | P1 | `teaagent/anp_adapter.py`, `tests/acceptance/test_anp_adapter_flow.py`, `docs/adr/0007-anp-adapter-boundary.md` |

---

## Open — High (P0)

_No open P0 items._

---

## Recently completed (competitive refresh, 2026-05-22)

| Item | Notes |
|------|-------|
| Docs/provider architecture drift guard | `scripts/validate_docs_consistency.py` now checks README/USAGE/architecture counts against `PROVIDER_CONFIGS`, unique credential env vars (including shared `CLOUDFLARE_API_TOKEN` / `OPENCODEZEN_API_KEY`), and survey doc freshness; `docs/architecture.md` updated to 13 providers. |
| Mode and safety comparison matrix | `docs/USAGE.md` matrix maps permission modes, Plan/Auto/Code lanes, shell mutation, approvals, audit, and rollback; validator enforces every `PermissionMode` value and required topics. |
| Multi-surface launch recipes | `docs/USAGE.md` “Choose Your Surface” table with CLI/TUI/VS Code/MCP/ACP/A2A/ANP/managed-runtime recipes; `validate_surface_recipes` + `test_surface_launch_recipes_flow.py` smoke local commands. |
| Subagent lineage and isolation hardening | Child runs record `parent_run_id`, `def_name`, `depth`, `batch_index`, and `isolation: shared`; `subagent_batch` returns ordered `lineage`; runner binds parent run context for tools. |
| Repo-map / context pack for coding runs | `build_context_pack` on `agent preflight`; read-only candidate files, memories, symbol stats, graph/RAG index status; `test_context_pack_read_only_flow.py`. |
| Plugin/skill compatibility catalog | `docs/plugin-skill-catalog.md` with fixture-backed `validate_plugin_skill_catalog`. |
| Competitive use-case dashboard refresh | Matrix/HTML include survey review date and open P1/P2 gap counts via `build_use_case_matrix.py` + `render_use_case_dashboard.py`. |
| Periodic mainstream-agent refresh cadence | `docs/release-checklist.md` requires survey refresh before minor releases or protocol ADRs. |

---

## Open — Medium (P1, maintenance)

| Item | Why now | Acceptance target |
|------|---------|-------------------|
| DeepWiki-backed agent landscape survey | Initial 2026-05-22 survey landed; keep refreshing before minor releases. | Re-run survey when Codex/Claude Code/OpenCode/OpenHands/Aider signals change; update review date, source table, and `docs/use-cases.md`; `validate_docs_consistency.py` must pass. |
| Subagent lineage and isolation | Lineage on `subagent`/`subagent_batch`; default `isolation: shared`. | Keep docs/tests aligned when adding `worktree`/`container` isolation or new lineage fields. |
| Repo-map / context pack | Preflight `context_pack` shipped; extend with LSP symbol hydration when needed. | Keep read-only guarantees; extend acceptance when adding live graph/RAG hits. |
| Mode and safety comparison matrix | Matrix in `docs/USAGE.md` with validator coverage. | Keep matrix in sync when permission modes or rollback APIs change. |
| Multi-surface launch recipes | Recipes in `docs/USAGE.md` with validator + smoke tests. | Keep recipes current when CLI/IDE/MCP surfaces change. |

---

## Open — Low (P2, maintenance)

| Item | Why now | Acceptance target |
|------|---------|-------------------|
| Plugin/skill compatibility catalog | Catalog and fixtures exist. | Update catalog when discovery paths or hook events change. |
| Competitive use-case dashboard | Dashboard reflects survey metadata. | Regenerate matrix/HTML after acceptance or survey updates. |
| Periodic mainstream-agent refresh cadence | Release checklist exists. | Follow `docs/release-checklist.md` before each minor release. |

---

## Recommended Execution Order (maintenance)

1. DeepWiki survey refresh (before minor releases).
2. Docs/provider drift guard (`validate_docs_consistency.py`).
3. Mode/safety matrix and multi-surface recipes sync.
4. Subagent lineage docs when isolation modes expand.
5. Context pack enhancements (LSP symbols, live graph/RAG hits).
6. Plugin/skill catalog updates when extension surfaces change.
7. Regenerate use-case matrix and HTML dashboard after acceptance changes.
