# Technical Debt Ledger

Known limitations, their origin, current impact, and the condition under which they should be resolved.  
Severity: **P0** (correctness/safety), **P1** (material UX/reliability), **P2** (architectural), **P3** (cosmetic/latent).

---

## Active Debt

### TD-01: TUI does not route through ChatSessionController
**Severity:** P0  
**Origin:** ADR-0025 was implemented for the REPL but the TUI migration was deferred (2026-06-01).  
**Impact:** TUI shows `$0.00` cost for all runs (CG-11). TUI `/undo` uses git-stash instead of surgical `UndoJournal` (CG-12). TUI session cost is not accumulated for budget enforcement (CG-15).  
**Introduced:** 2026-06-01 (REPL fixed, TUI deferred)  
**Resolution condition:** TUI migration spec at `daily-driver-tui-controller-migration-spec-2026-06-01.md`. Resolve when TUI test coverage makes migration safe.  
**Tracking:** CG-11, CG-12, CG-15 in daily-driver-known-issues-2026-06-01.md

### TD-03: ChatAgentConfig directly instantiates concrete collaborators
**Severity:** P2  
**Origin:** Fast initial implementation — constructing all collaborators in one place was expedient.  
**Impact:** Cannot unit-test ChatAgent behaviour (routing, budget checks, approval flow) without a full real filesystem, real LLM adapter, and real workspace. Tests are integration tests by necessity.  
**Introduced:** 2026-05-08 (P0 framework initial commit)  
**Resolution condition:** ADR-0012 accepted and implemented. Requires extracting interfaces for CodeAnalysisConfig, LSPServerManager, SubagentManager, HookRegistry, MemoryCatalog, WorkspaceToolConfig.  
**Tracking:** ADR-0012

### TD-04: CONFIG_KEYS is a hard-coded dict; plugins cannot extend config
**Severity:** P2  
**Origin:** Config schema was small at inception; hard-coding 8 keys was adequate.  
**Impact:** Plugins that need custom config keys must either use environment variables directly or monkey-patch CONFIG_KEYS. No validation or documentation for plugin-contributed config.  
**Introduced:** 2026-05-08  
**Resolution condition:** ADR-0015 accepted and implemented. Requires a `ConfigurationSchema` registry with per-key validation, type coercion, and documentation strings.  
**Tracking:** ADR-0015

### TD-05: Lambda closure bug risk in tool registration
**Severity:** P2  
**Origin:** Tool registration uses lambda closures in loops, creating the classic Python closure capture bug.  
**Impact:** A loop variable captured by a lambda produces wrong dispatch if the variable is mutated after lambda creation. Currently not causing a known runtime bug, but the pattern is fragile and will break the first time a tool loop is refactored.  
**Introduced:** Unknown; flagged in ADR-0016  
**Resolution condition:** ADR-0016 accepted. Replace all lambda closures in `register()` calls with `functools.partial` or explicit tool classes.  
**Tracking:** ADR-0016

### TD-06: Async-from-sync bridge is inconsistent across call sites
**Severity:** P1  
**Origin:** As async features were added incrementally, each call site that needed to run a coroutine from sync code implemented its own pattern.  
**Impact:** Some call sites use `asyncio.run()`, some use `loop.run_until_complete()`, some call `asyncio.set_event_loop()`. The inconsistency causes `RuntimeError: This event loop is already running` in nested async contexts (tests, Jupyter, prompt-toolkit sessions).  
**Introduced:** Progressively from 2026-05-08 to 2026-05-22  
**Resolution condition:** ADR-0018 accepted. Centralise in `run_coroutine_sync()` utility that handles both "running loop" and "no running loop" cases correctly.  
**Tracking:** ADR-0018

### TD-07: Error handling is inconsistent (bare except, unstructured strings)
**Severity:** P1  
**Origin:** Error handling was added reactively — each error case was handled at the point of discovery without a shared vocabulary.  
**Impact:** Some errors are logged, some are raised, some are swallowed. The LLM cannot reason about tool failures when errors are returned as free-text strings rather than structured `ErrorContext` objects. Post-incident debugging requires reading source code rather than the audit log.  
**Introduced:** 2026-05-08; worsened progressively  
**Resolution condition:** ADR-0014 accepted. Standardise on `TeaAgentError` hierarchy with `ErrorContext`, severity levels, and structured error emission to audit log.  
**Tracking:** ADR-0014

### TD-08: Backend selection uses module-level dicts, not registry class
**Severity:** P3  
**Origin:** `external_backends.py` was written before the registry pattern was established as a convention.  
**Impact:** Registry state bleeds across tests. Import order sensitivity. Backends cannot be registered conditionally (e.g., only if a dependency is installed).  
**Introduced:** 2026-05-14  
**Resolution condition:** ADR-0013 accepted. Replace module-level `_REGISTRY` dicts with `BackendRegistry` class instances, injected where needed.  
**Tracking:** ADR-0013

### TD-09: NFS deployment explicitly unsupported but not detected at startup
**Severity:** P1  
**Origin:** `fcntl` locking is the concurrency strategy (ADR-0029). NFS does not honour fcntl reliably.  
**Impact:** If a user places `.teaagent/` on an NFS mount, file corruption and race conditions occur silently. There is no startup check.  
**Introduced:** 2026-05-08  
**Resolution condition:** Add a `preflight` check that detects NFS mount for the workspace directory and warns (or hard-fails in strict mode).  
**Tracking:** Not yet filed as a ticket

### TD-10: Code Mode sandbox is not production-grade on macOS
**Severity:** P1  
**Origin:** ADR-0003 documents this explicitly — `RLIMIT_AS` is advisory-only on macOS; `RLIMIT_CPU` caps CPU but not wall-clock time under certain conditions.  
**Impact:** Adversarial code in Code Mode can consume unbounded memory on macOS without triggering the memory limit. Wall-clock timeout (`signal.SIGALRM`) is the primary defense.  
**Introduced:** 2026-05-08  
**Resolution condition:** For production deployments on macOS: wrap Code Mode in Docker (`DockerSandbox`). For Linux: `RLIMIT_AS` works correctly.  
**Tracking:** ADR-0003 "Not production-grade" note

### TD-11: MCP session store is in-memory only (ThreadingHTTPServer)
**Severity:** P2  
**Origin:** `MCPSessionStore` uses a plain Python dict. Chosen for simplicity at ADR-0005 time.  
**Impact:** MCP sessions are lost on process restart. No session persistence for long-running MCP clients that expect to reconnect to an existing session.  
**Introduced:** 2026-05-08  
**Resolution condition:** If MCP clients require session persistence across restarts → persist session store to SQLite under `.teaagent/mcp_sessions.db`.  
**Tracking:** ADR-0005 "insufficient for high-concurrency production" note

---

## Resolved Debt

| ID | Description | Resolved | Resolution |
|----|-------------|----------|-----------|
| TD-R01 | REPL showed fake $0.00 cost (CG-03) | 2026-06-01 | `ChatSessionController` accumulates real cost in `_run_agent_task` |
| TD-R02 | REPL `/undo` used destructive `git checkout` (CG-02) | 2026-06-01 | `UndoJournal` reverts specific writes only |
| TD-R03 | REPL result/answer never printed (CG-01) | 2026-06-01 | Fixed in `ChatSessionController.run()` result path |
| TD-R04 | Swarm subagents had no approval lineage | 2026-05-29 | `CentralizedApprovalQueue` with `parent_run_id` tracking (ADR-0022) |
| TD-R05 | No automated memory invalidation | 2026-05-29 | `AutoInvalidationRule` system with file-signature tracking (ADR-0024) |
| TD-R06 | jaraco.context CVE-2026-23949 | 2026-05-29 | Pinned `jaraco-context>=6.1.0` in `constraint-dependencies` |
| TD-R07 | Duplicate approval-manager ownership and import-order sensitivity | 2026-06-21 | Runner helper was renamed, canonical implementations moved to `teaagent.approval`, and a lazy facade plus alias identity tests preserve legacy imports |

---

## Debt Triage Criteria

When deciding whether to pay down technical debt:

1. **P0 always now** — correctness and safety issues block shipping
2. **P1 in the next sprint** — material UX/reliability impact that degrades operator trust
3. **P2 when touching the affected module** — pay it as you go; don't let it grow
4. **P3 batch quarterly** — cosmetic and latent issues, address in dedicated refactor sprints
