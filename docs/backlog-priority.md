# Backlog Priority

Prioritized by impact order: security and production risk → core platform capabilities → developer experience and ecosystem.

Last updated: 2026-05-16

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

---

## Open — High (P0)

*(No open P0 items in this track.)*

---

## Open — Medium (P1)

*(No open P1 items in this track.)*

---

## Open — Low (P2)

| Item | Why now | Acceptance target |
|------|---------|-------------------|
| Periodic mainstream-agent README refresh | Agent conventions are moving quickly; roadmap claims should be refreshed from official READMEs before major planning cycles. | Add a manual checklist or script-backed note that records reviewed sources and date. |

---

## Recommended Execution Order (remaining)

1. Periodic mainstream-agent README refresh.
