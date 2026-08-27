# Changelog

All notable changes to TeaAgent are tracked here.

## Unreleased

- **EFX durable-effect governance guards** (`87d1c61`, `26e80d4`, `62ddf99`):
  - `external_effect` tool annotation: GitHub PR create/review, browser
    navigate/click/fill/evaluate, and ALL remote MCP tools fail closed in
    read-only/workspace-write and require approval in prompt mode; remote
    `readOnlyHint`/`destructiveHint` hints are untrusted (EFX-002).
  - Unmatched mutating-tool starts checkpoint `pending_effect` before execute;
    resume surfaces `OUTCOME_UNKNOWN` with `retry_safe=false` and refuses
    blind non-idempotent redispatch (EFX-001).
  - One-time JIT approvals bind a canonical payload digest and are consumed
    at authorization — changed arguments cannot replay a grant; omitted call
    IDs derive digest-suffixed identities (EFX-003).
  - Providerless acceptance: `tests/acceptance/test_efx_durable_effect_flow.py`
    (acceptance guard now 669).
- **Approval/ops surface** (`839a847`, `39fd5a8`, `2684b31`):
  - `daily`/`preflight` warn when `GITHUB_TOKEN`/`GH_TOKEN` are ambient.
  - High-risk-path commits: `TEAAGENT_RISK_ACK` must cite an existing
    `docs/reviews/*-risk.md` (`ref <report>: <reason>`).
  - Session-approved tools skip redundant payload hashing on the approval hot path.
- **Tests/docs hardening** (`b48d773`..`f8c8233`): hermetic skill-diagnostics,
  GitHub no-token, and resume-prep tests; mutation-smoke registry realigned
  with both-flag killer tests; release checklist mandates recorded full-suite
  evidence (latest: 6668 passed / 0 failed / 25 skipped, coverage 78.37%);
  docs aging cleared to zero stale; Effect Authority vocabulary added to the
  terminology guide; CLI command-group roster drift-guarded.
- **Whole-project lens review adoption (G-P2-9)**: use-cases market-standard
  table repaired to its 5 real columns; maturity-matrix acceptance posture
  refreshed (131 files / 669 collected) and drift-guarded; North-Star G1–G6
  status table added to roadmap-status with G3 recorded as rescoped (M4/M5
  work-logs); product-contract permission bullet names EFX-002 fail-closed
  external-effect gating; dormant-surface deletion trigger lane added to the
  execution plan; panel record with C1–C6 adoption ledger in
  `docs/analysis/whole-project-lens-review-2026-08-26.md`.

- **Plan execution batch (system-transparency / comprehensive plans)**:
  - `teaagent.async_bridge.run_coroutine_sync` — approval/multisig paths no longer call `asyncio.set_event_loop` (ADR 009).
  - ACP stdio loop emits JSON-RPC errors instead of swallowing exceptions.
  - Audit L3 docstring corrected (plaintext, not encrypted at rest).
  - Code-analysis graph LRU cache (`_MAX_GRAPH_CACHE=8`) and `clear_graph_cache()`.
  - `ChildProcessCodeModeBackend.trusted_only` gate for untrusted workloads.
  - `scripts/verify_docs.sh` local docs gate; plan status table in engineering plan.
  - Tests: `test_acp_adapter_error_response`, `test_approval_async_from_sync`, `test_code_analysis_graph_cache`, `test_code_mode_trusted_only`, `test_policy_denial_reason_code_flow`.

- **Denial reason codes and transparency CLI**:
  - `DenialReasonCode` enum and optional `reason_code` on `ToolPermissionError` — maps denials to read-only mode, workspace-write mode, plan contract, JIT, multi-sig quorum, and related paths.
  - Audit events `tool_call_denied`, `tool_call_blocked`, and `tool_call_pending_approval` may include `reason_code` in the payload.
  - `teaagent approval why-denied <run_id>` lists denial/block events from a run's audit log with human-readable explanations.
  - Code-analysis `code_relations_to_graph` scopes in-memory graphs per workspace root (`stateful=True` annotation).
  - Tool lint warns on `stateful_without_governance` when stateful tools lack destructive or idempotent governance signals.
  - Docs: `docs/cli.md`, `docs/audit-events.md`.

- **Analysis and planning artifacts** (2026-05-31):
  - Competitive, enterprise security, market UX, and risk findings under `docs/analysis/`.
  - Positioning, comprehensive, and UX improvement plans under `docs/plans/`.

- **TUI Evolution Phase A-C** (fb59e41):
  - **Phase A — TUI responsiveness**: Async autocomplete with background ontology cache refresh (`_completion.py`), fuzzy session switch via `difflib.get_close_matches` (`_commands.py`), secret filename heuristics on pinned file `add()` to block env/SSH/cert/credential paths (`pinned_file.py`).
  - **Phase B — Approval UX**: Unicode tree view for subagent approval queue grouped by `parent_run_id` (`_approval_subagents.py`), `approvals diff <call_id>` git-diff preview subcommand (`_commands.py`).
  - **Phase C — Quality & compliance**: 12 headless pty TUI acceptance tests (`test_headless_tui.py`), compliance audit exporter with signed JSON bundle and chain verification (`audit_export.py`, 13 tests). Session grants cancelled — existing `ApprovalGrant(scope='session')` already covers it.
  - **Docs**: Updated acceptance count to 273, documented new features in cli.md and maturity-matrix.md.

- **Vote Relay OOM Fix**: Added `MAX_HTTP_BODY_BYTES=1_048_576` guard to `vote_relay.py::_read_json()` — rejects oversized payloads with `ValueError('body too large')` instead of unbounded `rfile.read()` (DoS vector; matches `signature_relay.py` pattern)

- **Verification-Driven Hardening (12 fixes)**:
  **Batch 1 (initial fixes):**
  - **SEC-05-REV** (`federated_sync.py`): `_validate_relay_url` now resolves hostnames via DNS and checks all resolved IPs against private ranges — blocks wildcard DNS SSRF attacks (e.g. `192.168.1.1.nip.io`)
  - **SEC-04-REV** (`jit_approval_server.py`): `start()` now enforces loopback binding with `ip_address(self._host).is_loopback` check at runtime
  - **F-01-REV** (`graphqlite_production.py`): `_fetch_document` escapes backslashes before single quotes — `doc_id.replace("\\", "\\\\").replace("'", "''")` for Cypher/SQLite defense-in-depth
  - **FIND-01-REV** (`_approval_queue_store.py`): Lock method uses dedicated `.json.lock` file instead of data file — prevents `flock` orphanage from `os.replace` inode swap
  - **FIND-02-REV** (`_approval_queue.py`): `reload_from_store` now resolves `_pending_futures` (asyncio.Future) alongside `_sync_waiters` — prevents async subagent hangs on disk-approved requests
  - **F-02-REV** (`memory_legacy.py`): `_atomic_write_entries` uses UUID-suffixed temp path instead of static `.jsonl.tmp` — eliminates temp file collisions
  **Batch 2 (verification-driven remediation):**
  - **SEC-04-REG** (`jit_approval_server.py`): `start()` now resolves hostname (`'localhost'`) before `ipaddress.ip_address()` — prevents `ValueError` on standard loopback hostname; uses `socket.gethostbyname()` with fallback
  - **SEC-05-TOCTOU** (`federated_sync.py`): `_validate_relay_url` bakes the resolved IP into the returned URL — prevents DNS rebinding TOCTOU between validation and HTTP fetch
  - **F-01-CYPHER** (`graphqlite_production.py`): Replaced manual string escaping with parameterized queries (`$doc_id`, `$term` placeholders) — eliminates Cypher injection risk entirely; updated both `_fetch_document` and `graph_retrieve`
  - **FIND-03-LOCK** (`_approval_queue_store.py`): `prune_stale` now acquires exclusive file lock before read/delete — prevents concurrent write races during queue pruning
  - **FIND-02-THREADSAFE** (`_approval_queue.py`): `reload_from_store` uses `call_soon_threadsafe` for async future resolution — prevents asyncio event loop corruption from background threads
  - **F-02-FLOCK** (`memory_legacy.py`): Replaced `threading.Lock()` with `fcntl.flock`-based cross-process file lock — prevents silent data loss when subagents run in separate processes

- **Deep Audit Remediation (10 fixes)**:
  - **SEC-01** (`tool_permissions.py`): Unknown/unregistered tools now require JIT approval — added `permission is None` guard in `check_tool_access` to prevent safe-default bypass
  - **SEC-02** (`policy.py`): Quorum signature verification now looks up SSH keys by `peer_id` instead of client-supplied `ssh_key_id` — blocks peer impersonation
  - **SEC-03** (`policy.py`): Approval hash now includes `run_id` and hourly time window — cryptographic replay protection
  - **SEC-04** (`jit_approval_server.py`): SSE server default host changed from `localhost` to `127.0.0.1`; added auth handshake TODO note
  - **SEC-05** (`federated_sync.py`): Added `_validate_relay_url()` — validates scheme, blocks private IPs (except loopback) before POST to prevent SSRF
  - **FIND-01** (`_approval_queue_store.py`): `load()` now uses shared lock (`LOCK_SH`) instead of exclusive lock (`LOCK_EX`) — prevents writer starvation during polling
  - **FIND-02** (`_approval_queue_store.py`): Dict serialization in `save()` moved inside file lock — prevents `RuntimeError: dictionary changed size during iteration`
  - **DSR-01** (`graphqlite_production.py`): `_apply_migrations` now opens an sqlite3 connection and passes it as `target_conn` — migrations actually execute in production
  - **DSR-02** (`graphqlite_production.py`): Document IDs in Cypher queries are now single-quote escaped — prevents stored Cypher injection
  - **DSR-05** (`memory_legacy.py`): Added `_file_lock` + atomic temp/rename write pattern to all mutation methods — prevents concurrent write corruption
  - **Regression Fix** (`schema_migration.py`): `executescript` now includes `BEGIN IMMEDIATE; … ;COMMIT;` in the script string — avoids "cannot commit" and "database is locked" errors

- **Swarm/Approval/Migration Security Hardening (4 fixes)**:
  - **Workspace Contamination**: Added `_sandbox_lock` (module-level `threading.Lock`) to `GitBranchSandbox.start/rollback/merge` — serializes git checkout operations across parallel `ThreadPoolExecutor` threads so concurrent subagents don't race on branch creation in the same working tree
  - **JIT Approval Bypass**: Made JIT approvals single-use — `check_tool_access` now calls `agent_approved.discard(tool_name)` after a successful check; `request_tool_approval` no longer redundantly adds tools to `_agent_tool_whitelist`; `jit_approval_server.py` uses the proper `request_tool_approval` API instead of directly manipulating `_agent_approved_tools`
  - **Split Lock Races**: Centralized `_approval_queue` dict protection under `self._sync_lock` (`threading.Lock`) in all 7 async methods that mutate `self._requests`/`self._batches` — eliminates data races between `asyncio.Lock`-gated and `threading.Lock`-gated callers
  - **Migration Collisions**: Wrapped `MigrationRunner.apply_pending` in `_migration_lock` (`threading.Lock`), re-reads `applied_versions` under lock (TOCTOU fix), and wraps `executescript` in `BEGIN IMMEDIATE`/`COMMIT` for SQLite-level write serialization

- **Residual Risk Fixes (3 fixes)**:
  - **Policy**: `_run_async_signature_collection` now uses a shared instance-level `ThreadPoolExecutor` instead of creating a new executor per call; executor field properly declared in frozen dataclass via `field(init=False)`
  - **Context Bus**: `subscribe_deltas` and `get_delta_count` restructured to release `self._lock` before calling `_execute_with_retry` — prevents lock-held-during-sleep thread starvation for writers
  - **Federated Sync**: `collect_approval_signatures` wraps blocking I/O operations (`glob`, `read_text`, `unlink`) with `loop.run_in_executor` to prevent event loop blocking during async polling

- **Concurrency & Transaction Audit Round 3 (6 fixes)**:
  - **Federated Sync**: `collect_approval_signatures` now accepts `required_approvals` parameter and waits for quorum instead of breaking on first signature; deduplicates peer signatures
  - **Policy**: `_run_async_signature_collection` offloads to `ThreadPoolExecutor` worker thread with fresh event loop — prevents `RuntimeError: cannot run event loop from within running loop`
  - **Context Bus**: `_execute_with_retry`/`_commit_with_retry` no longer hold `self._lock` during `time.sleep()` (fixes thread starvation); added rollback in all OperationalError paths; `publish_delta`/`_clear_deltas`/`cleanup_old_deltas` restructured with retry loops that sleep outside the lock
  - **Swarm**: `SwarmManager` now binds `_swarm_manager` to `subagent_manager` (fixes heartbeat registration being silently skipped); `tick_heartbeat()` method on Subagent for periodic liveness updates; heartbeat monitor now stores `SubagentResult(success=False, error=...)` on hang detection instead of silently discarding
  - **JIT Approval Server**: `approve_request` directly whitelists tool in permission manager instead of calling `request_tool_approval()` (fixes silent override of manual approvals); `_schedule_broadcast` uses `asyncio.run_coroutine_threadsafe` instead of non-thread-safe `call_soon_threadsafe(asyncio.ensure_future)`
  - **Workflow Engine**: `execute_workflow`/`resume_workflow` accept optional `audit_logger` parameter and attach `UndoJournal` sink to caller-provided logger (fixes no-op rollback); `_execute_step` exception handler now routes to self-healing instead of immediate failure return

- **Oracle Review Fixes (7 concurrency/architecture fixes)**:
  - **Context Bus**: `_execute_with_retry` now returns `sqlite3.Cursor` — callers (`subscribe_deltas`, `get_delta_count`, `cleanup_old_deltas`) use the reconnected cursor for `fetchall()`/`fetchone()`/`rowcount` instead of the stale pre-reconnect cursor; `except Exception` narrowed to `except sqlite3.Error` in `publish_delta`
  - **Swarm**: `register_subagent_heartbeat` stores subagent reference directly instead of `id(subagent_ref)` (fixes `getattr(int, 'is_running', False)` always returning False); added `_heartbeat_lock` for thread-safe access to heartbeat dicts
  - **Policy**: `_run_async_signature_collection` creates a new event loop when called from the event loop thread — prevents `run_coroutine_threadsafe` + `future.result()` deadlock
  - **Workflow Engine**: `resume_workflow` now acquires `self._workflow_lock` and sets up `UndoJournal` + rollback check (matching `execute_workflow` behavior)

- **Deeper Concurrency Audit (11 fixes)**:
  - **Context Bus**: `_execute_with_retry` / `_commit_with_retry` now retry `DatabaseError` with reconnect + exponential backoff instead of immediate re-raise; `publish_delta` added rollback on commit failure to prevent transaction leaks; `subscribe_deltas` / `get_delta_count` SELECTs now use `_execute_with_retry` for lock-contention safety
  - **Federated Sync**: `collect_approval_signatures` converted from synchronous `time.sleep()` polling to `async def` with `asyncio.sleep()`, preventing 5-minute asyncio event loop starvation during peer signature collection
  - **Policy**: `_collect_peer_signatures` dispatches async signature collection via `run_coroutine_threadsafe` (if event loop active) or `asyncio.run()` — prevents blocking the main thread during multi-sig quorum
  - **Swarm**: `Subagent` now tracks `is_running`/`last_heartbeat` for thread-liveness; `_heartbeat_monitor_loop` replaced defunct PID-based `is_process_alive(pid)` with subagent-ref-based `getattr(subagent_ref, 'is_running', False)` — actually detects thread hangs instead of checking parent process PID
  - **Workflow Engine**: `_execute_step` added `current_attempt` parameter, preserving self-healing attempt count across recursive re-execution (fixes infinite loop where counter reset on every new `StepExecution`); `execute_workflow` integrates `UndoJournal` + `AuditLogger` and calls `journal.restore()` on strict validation failure

- **Security & Concurrency Audit (19 fixes)**:
  - **JIT Server**: Fixed `_clients` set mutation during broadcast iteration (`list(self._clients)`); `_schedule_broadcast` now thread-safe via `call_soon_threadsafe`
  - **Approval Queue**: Replaced `asyncio.Lock` with `threading.Lock` for global queue registry; `get_pending_requests` now holds `_sync_lock` during iteration
  - **Context Bus**: `archive_to_rag` passes `max_timestamp` to `_clear_deltas` preventing data loss; added `_reconnect()` for database corruption recovery
  - **Swarm**: Added `timeout` to `ThreadPoolExecutor.as_completed()` preventing indefinite hangs; atomic writes for `prompt_gene_pool.jsonl`
  - **Git Sandbox**: `stash_save` now returns actual stash reflog selector instead of hardcoded `stash@{0}`; `stash_pop` accepts optional stash reference
  - **Workflow Engine**: Added `threading.Lock` for thread-safe `execute_workflow`/`cancel_workflow`
  - **Undo Journal**: Fixed restore order — processes entries forward (oldest first) to restore original pre-write state for multi-write files
  - **Policy**: Added brace expansion, process substitution extraction, and non-string/non-list fallback to shell normalization
  - **File Policy**: Widened protected dir patterns (`.git*`, `workspace_write_*`); added `os.path.normpath` normalization in `DenyRule.matches()`
  - **Tool Permissions**: `register_tool_permission` blocks DESTRUCTIVE→SAFE downgrade without `allow_downgrade=True`
  - **Code Mode**: Added `RLIMIT_NPROC` (max 8 child processes) to prevent fork bombs
  - **Agent Factory**: Atomic file writes via temp file + `os.replace()` in `_persist_agent`

- **Security & Concurrency Hardening (5 fixes)**:
  - **JIT Approval Server async refactor** (`teaagent/jit_approval_server.py`): Converted `_wait_for_approval` from synchronous `time.sleep(1)` spin-lock to `async def` using `asyncio.Event` + `asyncio.wait_for`, preventing asyncio event loop starvation during approval waits. `request_approval` is now `async def`.
  - **Context Bus SQLite concurrency** (`teaagent/context_bus.py`): Per-thread connections with `timeout=5.0`, WAL pragmas on connect, `_execute_with_retry` with exponential backoff (5 retries) on lock contention. Applied to `publish_delta`, `_clear_deltas`, `cleanup_old_deltas`.
  - **Shell command normalization** (`teaagent/policy.py`): Added `_normalize_shell_arg` static method with 5-pass normalization (quote stripping, backslash removal, backtick extraction, `$()` subshell extraction, shlex split). Added list-type command argument handling to prevent bypass via `["rm", "-rf", "/prod"]`.
  - **Per-agent JIT approval** (`teaagent/tool_permissions.py`): Replaced global `requires_approval=False` mutation in `request_tool_approval` with per-agent `_agent_approved_tools` tracking, preventing privilege escalation where approving one agent granted all agents access.
  - Added regression test `test_approval_is_per_agent_not_global` verifying cross-agent isolation.

- **Governance Hardening (Tranche B Completion)**: Implemented three key governance decisions with CI release gates:
  - **Centralized Approval Queue for Subagents**: Added `CentralizedApprovalQueue` in `teaagent/subagents/_approval_queue.py` for aggregating destructive tool requests from multiple subagents, supporting batch approval/deny with full lineage tracking, and preventing approval fatigue in tournament/swarm modes
  - **Strict Plan-before-Write Enforcement**: Modified `teaagent/governance/plan_gate.py` to enforce plan-by-default in workspace-write mode, added `--skip-plan-check` CLI flag for explicit override, updated `ChatAgentConfig` and `AgentRunner` to support the new parameter
  - **Automated Memory Invalidation**: Extended `FailureCardStorage` with `AutoInvalidationRule` and `MemoryAutoInvalidationConfig`, implemented conservative default rules (file_signature_change: invalidate, test_refactor: warn, dependency_version_change: warn), added `apply_auto_invalidation()` method with file signature tracking, added CLI command `teaagent memory failures auto-invalidate`, and supports per-project custom rules via `.teaagent/config.json`
  - **Governance Fuzz Tests**: Added comprehensive adversarial fuzz tests in `tests/test_governance_fuzz.py` covering plan-before-write enforcement, memory invalidation, and approval queue security with 13 tests validating conservative defaults and path filtering
  - **CI Release Gates**: Added `governance-gate` job to `.github/workflows/ci.yml` that runs governance fuzz tests, tool lint validation, and permission matrix tests before package build
- Added Phase 5 Cognitive Swarm Evolution with self-healing validation, cross-sandbox Delta sharing, evolutionary prompt tuning, and remote JIT approval:
  - `teaagent/workflow_engine.py`: Self-healing validation loops with ruff/mypy/pytest checks, automatic hot-reload and re-execution (max 3 attempts)
  - `teaagent/context_bus.py`: Cross-sandbox Delta sharing via WAL-mode SQLite for concurrent access, with publish/subscribe and RAG archive
  - `teaagent/agent_factory.py`: Evolutionary prompt self-tuning based on performance feedback with LLM and heuristic fallback
  - `teaagent/jit_approval_server.py`: Remote SSE JIT approval server with 3-minute timeout and safe abort
  - Added 29 tests across 4 test files for Phase 5 components
- Added Cooragent multi-agent integration with task coordination, dynamic agent generation, tool permissions, and workflow execution:
  - `teaagent/coordinator.py`: Task classification by type (code_review, testing, documentation, refactoring, debugging, feature_implementation, general) with LLM-based and heuristic classification
  - `teaagent/agent_factory.py`: Dynamic agent generation with LLM-structured system prompts, memory/disk registration, and hot-reload support
  - `teaagent/tool_permissions.py`: Tool safety classification (safe, inspect, destructive) with safe defaults and JIT approval for destructive tools
  - `teaagent/workflow_engine.py`: Multi-step workflow execution with polish mode, unified diff display, and workflow state management
  - Added 35 tests across 4 test files for Phase 4 components
- Added Skill-RAG integration with ContextGatherer for collaborative retrieval with token reduction benefits
- Added Swarm lock management with 60-second timeout and heartbeat monitoring
- Added `ANPGovernedService` to wire ANP inbound tool calls through `AgentRunner` with federation audit events, outbound delegation timeouts, and budget enforcement; accepted ADR 0007.
- Hardened OpenAI-compatible content extraction for `reasoning_content`, `text` content parts, and nested `result.output_text` (opencodezen-go/kimi-style payloads).
- Refreshed MCP discovery card, provider-authoring conformance docs, ANP acceptance tier (P1), nightly smoke providers (`workers-ai`, `aigateway`), and `scripts/refresh_agent_readme_survey.md`.
- Added 8-event Hook System (Claude Code compatible): `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`, `SubagentStop`, `SessionEnd`. Includes `HookRegistry`, `permission_check_hook`, `lint_check_hook`, `run_tests_hook`, `mcp_tool_filter_hook`, and `PermissionMode` enum.
- Added Three-Tier Memory System (Claude Code compatible): `MemoryHierarchy` with Project (`.teaagent/memory.jsonl`), Personal (`~/.config/teaagent/memory.jsonl`), and Auto-Memory (`.claude/MEMORY.md`) tiers.
- Added Context Compaction with traffic light zones: Green (0-75%), Yellow (75-92%), Red (92%+). Implements `CompactionManager` with `should_compact()` and `check_and_compact()`.
- Added Plugin System with four extension points: Commands, Agents, Hooks, MCP Servers. Includes `PluginRegistry`, `PluginManifest`, `CommandPlugin`, `AgentPlugin`, and built-in plugins (code-reviewer, tester, docs-writer).
- Added Plan Mode for read-only exploration: `PlanMode` class with `enable()`, `disable()`, `can_execute_tool()` to block writes/shell in exploration mode.
- Added ACP (Agent Client Protocol) adapter for IDE integration: `ACPServer` for VS Code, Zed, JetBrains with `initialize`, `tools/list`, `tools/call`, `completion`, `tools/cancel` methods.
- Added FilteredMCPClient with tool filtering (allow/block lists) and sampling configuration (max_tokens, temperature).
- Added bundled skills: `code-review`, `git-workflow`, `testing`, `refactoring`, `mcp-integration` under `.opencode/skill/`.
- Added GraphQLite production deployment: `GraphQLitePersistentStore` with WAL mode, 5-version schema migration framework via `SQLiteMigrationStore`/`MigrationRunner`, index strategy (Entity name, Document source/doc_id, EDGE relation), `graph_retrieve` via Cypher traversal, round-trip `sync_to_knowledge_graph`, `graphqlite migrate` CLI, and production deployment guide at `docs/graphqlite-production.md`.
- Added VS Code extension (`vscode/`) wrapping the CLI with command palette entries (doctor, agent run, preflight, model providers, GraphQLite smoke, TUI), custom task definitions, problem matcher, terminal profile, and TeaAgent output channel.
- Added API documentation infrastructure: `pdoc>=14` dev dependency, `scripts/build_docs.py` build script covering all submodules, and class-level docstrings on core types (`AgentRunner`, `ToolRegistry`, `ToolAnnotations`, `ToolDefinition`, `RunBudget`, `MemoryEntry`).
- Removed stale P0/P1/P2/P3 scope files (`docs/p0-scope.md`, `docs/p1-scope.md`, `docs/p2-scope.md`, `docs/p3-scope.md`) — all deferred items were already implemented and tracked in `docs/backlog-priority.md`.
- Updated ADRs 0001, 0004, and 0006 with post-implementation notes for multi-agent orchestration, key rotation, cross-host OAuthStore backends, and key-ring CLI support.
- Aligned scope docs with current implementation status by updating P0/P1 deferred lists and adding implemented-since-baseline notes for MCP transport, OAuth/DPoP, and telemetry paths.
- Unified package version lookup to `importlib.metadata.version("teaagent")` with a local fallback, removing hard-coded duplication risk between code and packaging metadata.
- Narrowed `teaagent.__all__` to a stable core API surface and added a migration guide at `docs/migration-top-level-api.md` for projects that relied on star-import convenience.
- Clarified local developer setup for PEP 668 environments by adding virtualenv-first install steps to `README.md` and `CONTRIBUTING.md`.
- Updated contributor check commands to use `.venv/bin/...` explicitly for reproducible local lint/type/test runs.
- Consolidated agent-instruction precedence by making `AGENT.md` a compatibility pointer and declaring `AGENTS.md` as the canonical rule source.
- Pinned dev `mypy` to `<2` to keep Python 3.10 type-check configuration compatible and avoid local warning churn.
- Split `teaagent/tui.py` (517 → ~290 lines) by extracting `handle_command` logic to `_commands.py`.
- Split `teaagent/mcp_http.py` (575 → ~400 lines) by extracting OAuth endpoint handlers to `_oauth.py`.
- Split `teaagent/telemetry.py` into a `teaagent/telemetry/` package with focused modules: `_availability.py`, `_config.py`, `_audit.py`, `_metrics.py`, and `_transport.py`.
- Split `teaagent/code_mode.py` into a `teaagent/code_mode/` package with focused modules: `_types.py`, `_validation.py`, `_child_process.py`, and `_container.py`.
- Split `teaagent/cli/_handlers.py` into a `teaagent/cli/_handlers/` package and extracted agent-run lifecycle logic into `_agent.py` while preserving command handler imports.
- Continued splitting `teaagent/cli/_handlers/` by moving doctor, memory, model, MCP, misc, and audit handlers into dedicated modules and keeping stable re-exports in `__init__.py`.
- Split `teaagent/llm_conformance.py` into a `teaagent/llm_conformance/` package with `_types.py` and `_runner.py`, preserving existing imports.
- Split `teaagent/runner.py` into a `teaagent/runner/` package with `_types.py` and `_core.py`, preserving existing `teaagent.runner` imports.
- Made `teaagent.cli.main()` accept injectable `_adapter_factory`, `_serve_mcp_http`, `_check_graphqlite`, `_check_llm`, and `_run_model_conformance` keyword arguments, enabling handler extraction without breaking existing tests.
- Split `teaagent/workspace_tools.py` into a `teaagent/workspace_tools/` package with four focused modules: `_config.py`, `_helpers.py`, `_shell.py`, `_files.py`. Backward-compatible public imports preserved via `__init__.py` re-exports.
- Expanded audit string redaction with patterns for JWT tokens, AWS access keys (`AKIA...`), and GitHub personal access tokens (`ghp_...`, `github_pat_...`).
- Split `teaagent/llm.py` into a `teaagent/llm/` package with focused modules: `_types.py`, `_transport.py`, `_retry.py`, `_extract.py`, `_adapters.py`, `_config.py`. Backward-compatible public imports preserved via `__init__.py` re-exports.
- Refactored `OpenAICompatibleAdapter` streaming path to support an injectable `streaming_lines` parameter, removing the last urllib patch dependency in LLM tests.
- Added a 5-minute walkthrough section to the README that walks through the end-to-end example step by step.
- Added deeper MCP HTTP transport tests covering empty batches, mixed-type batches, initialize with no id, and DELETE lifecycle (reuse after delete, non-existent session).
- Added community health files: `CODE_OF_CONDUCT.md`, `SUPPORT.md`, and GitHub issue templates for bugs and feature requests.
- Added `.editorconfig` with consistent encoding, EOL, and indentation settings for Python, Markdown, YAML, TOML, JSON, and Makefiles.
- Added `.github/CODEOWNERS` for automated PR review routing.
- Added `docs/architecture.md` covering the system overview, component layers, data flow, state boundaries, and extension points for all major subsystems.
- Added `examples/full_agent_run.py`, a self-contained end-to-end example that walks through workspace tools, audit, memory, budget, agent loop, run-store persistence, and metrics without requiring LLM API keys.
- Added a package CI job that builds sdist/wheel artifacts, runs `twine check`, installs the wheel in a clean venv, and verifies `teaagent/py.typed` ships in the package.
- Wired OAuth key rings through the MCP HTTP resource-server boundary so tokens signed with rotated authorization-server keys validate at the actual HTTP endpoint.
- Added short-lived DPoP proof `jti` replay caches to the authorization and resource servers so replaying the same proof within the freshness window fails.
- Made OAuth DPoP nonce validation one-time by adding `OAuthStore.consume_nonce()` and using atomic consume/delete semantics in `SQLiteOAuthStore`.
- Added optional container image digest pinning and image allowlist enforcement to `ContainerCodeModeBackend`.
- Changed `ContainerCodeModeBackend` to enforce `CodeModeSandbox.max_output_bytes` while streaming stdout/stderr and kill the child process immediately when the combined output limit is exceeded.
- Updated README, SECURITY, and P2 scope docs so Code Mode backend limitations and optional dependency groups match the current implementation.
- Added MCP HTTP boundary tests for malformed `Content-Length`, oversized JSON-RPC bodies, and scalar JSON payloads; oversized MCP JSON-RPC requests now return `413` consistently.
- Hardened `SQLiteOAuthStore` client-secret storage with PBKDF2-SHA256 hashes, per-client random salts, schema-version metadata, and server-side validation through the store instead of plaintext retrieval.
- Cleaned repo agent instructions by removing embedded session-memory context from `AGENTS.md`.
- Added a dedicated telemetry CI job that installs `.[dev,telemetry]` and runs telemetry tests without relying on skipped optional imports.
- Extended release automation with PyPI Trusted Publishing and GitHub artifact provenance attestation for tagged releases.
- Added `release` and `security` optional dependency groups for local build/twine and `pip-audit` workflows.
- Removed the remaining package-level mypy strictness overrides; all `teaagent/` modules now run with `disallow_untyped_defs` and `disallow_incomplete_defs` enabled.
- Added packaging and contribution hygiene: `MANIFEST.in`, `CONTRIBUTING.md`, and a pull request template with validation/governance checklist.
- Added audit redaction for secret-like patterns inside otherwise non-sensitive strings (Bearer tokens, `sk-...` keys, and URL/query-style `token=...`/`api_key=...` values).
- Added `SQLiteOAuthStore`, a durable OAuth 2.1 store for clients, one-time authorization codes, and DPoP nonces. It uses SQLite WAL mode and an immediate transaction for consume-and-delete authorization-code semantics.
- Added `configure_metrics()` and a new `metrics_otlp_endpoint` field on `TelemetryConfig` so OpenTelemetry counters and histograms have a real `MeterProvider` with OTLP/console exporters; previously only an in-memory metrics path existed.
- Fixed the `TracingHTTPTransport` docstring example to match the actual two-argument constructor.
- Hardened OAuth resource-server verification: `OAuth21ResourceServer` and `OAuth21AuthorizationServer.introspect_token` now resolve the verification key by JWT `kid` via `OAuthKeyRing`, so rotated signing keys keep verifying without losing trust in older tokens.
- Added Dependabot configuration (`pip` + `github-actions`, weekly) and a Security workflow that runs `pip-audit` and CodeQL on every push, pull request, and weekly schedule.
- Restricted the release workflow to least-privilege permissions (`contents: read`).
- Re-licensed the project under the MIT License and added the matching PyPI classifier.
- Marked the package as typed by shipping `teaagent/py.typed` and configuring setuptools `package-data`.
- Hardened `ContainerCodeModeBackend`: rejects empty images at construction, enforces `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root `--user`, `--tmpfs /tmp`, `--memory-swap`, and a separate `--ulimit cpu` for CPU time. The `--cpus` flag now reflects an explicit CPU-share field instead of reusing the CPU-time budget.
- Added `CodeModeSandbox.max_output_bytes` and switched the container backend to `subprocess.Popen` so oversized stdout is rejected instead of buffered without bound.
- Updated `SECURITY.md` to reflect the storage-layer file locking that audit and memory writes already use, and added `docs/p3-scope.md` to mirror the existing P0/P1/P2 scope notes.
- Added a pluggable Code Mode backend boundary with the existing child-process backend and a Docker/Podman-style container backend.
- Added audit-driven metrics sinks for run and tool lifecycle counters plus basic histogram samples.
- Added release packaging basics: license file, changelog, and distribution build workflow.
