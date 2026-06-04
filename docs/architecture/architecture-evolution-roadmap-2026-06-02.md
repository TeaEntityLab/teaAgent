# TeaAgent — Architecture Evolution Roadmap
**Date:** 2026-06-02  
**Author:** Architecture review session (John + Claude)  
**Status:** Living document — update after each major milestone

---

## Executive Summary

TeaAgent is a governance-first agent harness. Its core abstractions (AgentRunner, ToolRegistry, ApprovalPolicy, AuditLogger) are sound and competitively differentiated. The immediate threats are not architectural in the abstract — they are two concrete divergences: the TUI surface bypassing the `ChatSessionController` (CG-12), and the broken agent suspend/resume round-trip (AG-01..04). Left unaddressed, both compound into a growing surface parity debt that will cost more to migrate the longer it sits.

Beyond the immediate fixes, three structural investments will determine whether teaagent scales from a single-user harness to a multi-user, multi-agent platform:

1. **Surface Protocol Abstraction** — decouple presentation from execution so new surfaces (web, IDE embedded, mobile) are first-class citizens, not forks.
2. **Async-First Runner** — the synchronous AgentRunner is the primary bottleneck for concurrent subagent coordination; migrating to async enables true parallelism without thread-pool workarounds.
3. **Federated State Store** — the JSONL single-writer model is correct for local single-user; it must become pluggable before team or cloud deployments are safe.

**Heddle Concept Fit (2026-06-03):** Recent architectural analysis mapped Heddle concepts to TeaAgent boundaries. The conclusion is to adopt Heddle's "boundaries and process" approach without copying the TypeScript/daemon framework. Key mappings include CLI entry flow, agent loop layering, session persistence, and memory maintenance loops. See [Heddle Concept Fit](heddle-concept-fit-2026-06-03.md) for detailed mapping and task plan.

---

## 1. Current Architecture Assessment

### 1.1 Core Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Surfaces: CLI REPL (chat_repl.py)  ·  TUI (tui/__init__)  │
├─────────────────────────────────────────────────────────────┤
│  ChatSessionController (chat_session_controller.py)         │
│  — unified execution path for interactive surfaces          │
│  — REPL: adopted · TUI: bypassed (CG-12, OPEN)             │
├─────────────────────────────────────────────────────────────┤
│  AgentRunner (runner/_core.py)                              │
│  — synchronous decide→dispatch→observe loop                 │
│  — per-iteration budget, approval, audit enforcement        │
├───────────────────┬────────────────────────────────────────┤
│  ToolRegistry     │  ApprovalPolicy (5 permission modes)   │
│  + annotations    │  + JIT approval SSE server             │
├───────────────────┴────────────────────────────────────────┤
│  Workspace Tools · Code Mode · SubagentManager · SwarmMgr  │
├─────────────────────────────────────────────────────────────┤
│  State Layer                                                │
│  AuditLogger (JSONL)  ·  RunStore (JSONL)                  │
│  MemoryCatalog (JSONL)  ·  ContextBus (SQLite)             │
│  SQLiteOAuthStore (SQLite)  ·  UndoJournal (files)         │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                             │
│  LLM adapters (13 providers)  ·  MCP stdio+HTTP            │
│  OAuth 2.1 / DPoP  ·  OTel spans+metrics  ·  ANP / ACP    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Design Patterns

| Pattern | Where | Strength |
|---------|-------|----------|
| Strategy (DecisionFn) | AgentRunner accepts any `DecisionFn` | Swappable LLM vs rule-based vs test double |
| Adapter (LLMAdapter) | `llm/_adapters.py`, 13 providers | Add provider without touching core |
| Sink-chain (AuditLogger) | `add_sink()` API | OTel, metrics, in-memory, all composable |
| Protocol (OAuthStore, CodeModeBackend) | oauth21/, code_mode/ | Pluggable storage and execution backends |
| Single-writer JSONL | AuditLogger, RunStore, MemoryCatalog | Lock-safe on single machine, simple, auditable |
| 5-loop governance | plan_gate, tool_lint, audit_chain, failure_card, approval_queue | Defense-in-depth with explicit closure |

### 1.3 Existing ADRs (0001–0025)

Twenty-five ADRs exist covering: framework fundamentals (0001-0002), Code Mode sandbox (0003), OAuth/DPoP (0004), MCP HTTP (0005), circular dependencies (0010), tight coupling (0012), async bridging (0018), Phase 4/5/6 (0019-0021), centralized approval queue (0022), plan-before-write (0023), memory invalidation (0024), and chat session controller (0025). New ADRs in this document pick up at **0026**.

---

## 2. Architectural Pain Points

### 2.1 Surface Divergence (Root Cause: CG-12)

**File:** `teaagent/tui/__init__.py:907` calls `run_chat_agent()` directly; `chat_session_controller.py` is not used.

**Impact radius:** Every fix applied to `ChatSessionController` is silently absent from the TUI. Current open gaps: CG-11 (cost accumulator — stop-gap `+=` committed at line 943 but full controller path not wired), CG-15 (undo verb — TUI uses git-stash, REPL uses UndoJournal), any future controller feature.

**Compounding mechanism:** Each quarter this stays open adds to the migration surface. At current velocity (one new controller feature per sprint), the divergence grows linearly.

**Fix:** TICKET-12 (TUI → ChatSessionController migration). The ADR (0025) is accepted; only the TUI migration is outstanding.

### 2.2 Broken Agent Suspend/Resume (AG-01..04)

**Root cause:** `run_store.py` `task_for_run()` raises at line 143 because `run_started` is never written to the audit log during a REPL `/background` suspend. `teaagent resume <id>` therefore errors immediately; `agent run --background <id>` treats the ID as a literal task string.

**Impact radius:** Background/cloud agent workflows are effectively non-functional for REPL users. The only working path is `agent interactive-review <id>` (review-only, no observation rehydration).

**Fix:** Ensure `run_started` is written before process detach; add observation serialization to the suspend record; add rehydration on resume.

### 2.3 Test Anti-Pattern Masking Live Bugs (CG-16)

**File:** `tests/test_tui.py:1140` injects `_session_cost_cents` by hand into the TUI instance, so 104 TUI tests pass while the live accumulation path is wrong.

**Structural problem:** This is not a one-off test smell — it reflects the broader pattern of surface tests that bypass the execution path under test. As long as the TUI's internal state is set directly in tests, bugs in the path that *sets* that state are invisible to CI.

**Fix:** Tests must route through the same code path the user does. After TICKET-12 migration, the test should use a real ChatSessionController instance.

### 2.4 Exception Swallowing (CG-13)

**File:** `chat_session_controller.py:143-159` catches `(AttributeError, TypeError)` to detect test mocks. A real `UndoJournal.save()` failure with an `AttributeError` (e.g., corrupted journal state) is indistinguishable from a mock and silently dropped.

**Risk:** Low probability but high blast radius — a crash during undo journal save could leave the user believing a recovery point exists when it does not.

**Fix:** Replace the broad exception catch with an explicit `isinstance(self.undo_journal, MockUndoJournal)` check (or a `is_test_double()` protocol), then re-raise non-mock exceptions.

### 2.5 Undo Verb Collision (CG-15, DQ-6)

**Scope:** `/undo` in the TUI invokes git-stash-based checkpoint restore; `/undo` in the REPL invokes `UndoJournal.restore()`. Same command, different blast radius. Users switching between surfaces get inconsistent recovery semantics.

**Open decision (DQ-6):** The recommended resolution is (a) consolidate onto `UndoJournal`, rename git-stash to `checkpoint restore` as a deliberate rename (breaking change). This is the correct long-term path; the alternative (keep both) extends the inconsistency indefinitely.

### 2.6 Single-Writer JSONL Ceiling

**Documented in ADR 0008:** NFS / multi-writer shared roots are explicitly unsupported. The state model is correct for local single-user but has hard limits:
- No concurrent multi-session writes to the same workspace
- No distributed audit log aggregation across team members
- RunStore heartbeat is PID-based and not process-independent
- BackgroundRunStore records PIDs that may not survive machine restarts

**Migration path (ADR 0008):** `SQLiteAuditStore` / shared DB behind feature flags — not started.

### 2.7 Module Sprawl and Circular Risk

The top-level `teaagent/` package contains 250+ Python files. ADRs 0010 (circular dependencies), 0012 (tight coupling), and 0013 (backend abstraction) acknowledge this. The risk is not theoretical: any import of `tools.py` from `runner/_core.py` through an intermediate that imports `runner` creates a cycle.

**Mitigation in place:** `runner/` sub-package with explicit `_types.py` boundary, `workspace_tools/` sub-package with `builder.py` factory. The pattern exists; it has not been applied uniformly.

---

## 3. Scalability Analysis

### 3.1 At 10× (10 concurrent users, 10 concurrent agents)

| Bottleneck | Current behavior | Risk |
|------------|-----------------|------|
| JSONL file locking | `fcntl.LOCK_EX` per write, sequential per workspace | Low: each workspace is independent; 10 users = 10 workspaces = no contention |
| ThreadPoolExecutor in SwarmManager | Default `max_workers=None` (CPU count) | Medium: swarm with 10 subagents can saturate threads; GIL limits Python compute |
| ContextBus (SQLite WAL) | Per-workspace SQLite, WAL mode | Low: WAL handles concurrent readers + 1 writer well at 10× |
| BackgroundRunStore | PID polling, no heartbeat protocol | Medium: 10 background agents all polling for completion on single machine |
| AgentRunner (sync) | Blocking I/O to LLM provider | High: 10 concurrent sync agent loops = 10 threads blocked on network I/O |

**Assessment:** 10× is achievable with the current model if each agent lives in its own workspace. The sync runner becomes a real constraint when multiple agents share a process.

### 3.2 At 100× (100 concurrent users, 100 concurrent agents)

| Bottleneck | Impact |
|------------|--------|
| JSONL single-writer | Fine per workspace; breaks if workspaces are shared or on NFS |
| SQLiteOAuthStore | SQLite with `BEGIN IMMEDIATE` serializes writes; 100 concurrent auth flows will queue |
| SwarmManager ThreadPoolExecutor | Thread-per-agent model doesn't scale; 100 threads on a single machine is GIL-heavy |
| AuditLogger fsync per event | 100 agents × N events/second = fsync contention if on the same disk |
| SubagentLineage depth enforcement | No hard depth limit at the API boundary; potential runaway delegation trees |

**Assessment:** 100× requires: (1) async runner to eliminate thread-per-agent, (2) SQLite→PostgreSQL migration path for OAuth and ContextBus, (3) pluggable audit store to allow batched/async writes, (4) explicit swarm depth limits enforced at SubagentManager.

### 3.3 At 1000× (platform / SaaS scale)

This is a redesign, not an optimization:
- JSONL must be replaced by an event-sourced log (Kafka, Postgres WAL, or equivalent)
- Approval workflows need async push channels (the SSE JIT server is a prototype of this)
- Agent identity must be cryptographic, not PID-based
- Cost accounting must be multi-tenant with per-user isolation

**Recommendation:** Do not over-engineer for 1000× now. Instead, ensure the 10× and 100× paths do not close off the 1000× options (i.e., keep stores behind protocols, not concrete types).

---

## 4. Extensibility Analysis

### 4.1 Adding a New LLM Provider

**Effort:** Low. Implement `LLMAdapter.chat() → LLMResponse`, add to `PROVIDER_CONFIGS` in `llm/_adapters.py`. No changes to runner, registry, or governance. Well-documented.

**Gap:** No conformance test suite that a new provider must pass before being registered. `llm_conformance/` exists but is not enforced in CI as a gate for new providers.

### 4.2 Adding a New Tool

**Effort:** Low. Call `ToolRegistry.register()` with schema, annotations, and handler. Approval policy, audit, and plan gate all apply automatically.

**Gap:** Tools are registered at import time or at runner construction; there is no hot-reload path for tools added to a live agent session. Plugin tools loaded from `.teaagent/plugins/` are also static (loaded once at startup).

### 4.3 Adding a New Permission Mode

**Effort:** Medium-High. Requires changes to:
1. `policy.py` (add mode enum value and policy rules)
2. `runner/_approval_manager.py` (approval logic)
3. `cli/` (CLI argument validation and help text)
4. `tui/` (TUI mode selector)
5. Documentation and acceptance tests

**Gap:** Permission mode is a string enum spread across four touch points. There is no single `PermissionModePlugin` that can be registered in one place and have it propagate.

### 4.4 Adding a New Surface (web, mobile, IDE embedded)

**Effort:** High. Currently requires forking either `chat_repl.py` or `tui/__init__.py` and manually wiring to `ChatSessionController`. There is no `SurfaceAdapter` protocol.

**Gap:** This is the single biggest extensibility gap relative to the stated goal of multi-surface parity. Without a surface protocol, every new surface diverges by default (as TUI did).

### 4.5 Adding a New Governance Loop

**Effort:** Medium. The 5-loop system is organized as discrete modules (`plan_gate.py`, `tool_lint.py`, `audit_chain.py`, `failure_card.py`, `_approval_queue.py`) hooked into `AgentRunner` explicitly. A new loop requires code changes to `runner/_core.py`.

**Gap:** No declarative governance plugin point. Governance loops are hardcoded, not registered.

---

## 5. Multi-Agent Coordination

### 5.1 Current Capability

| Capability | Status |
|-----------|--------|
| Parallel subagent execution | ✅ `SwarmManager` + `ThreadPoolExecutor` |
| Subagent isolation (shared/worktree/container) | ✅ `_isolation.py` |
| Approval queue aggregation | ✅ `_approval_queue.py` (centralized, timeout-handled) |
| Parent→child lineage tracking | ✅ `SubagentLineage` struct |
| Consensus before execution | ✅ `ConsensusEngine` + `PeerRegistry` (Phase 4) |
| Result capture per subagent | ✅ `_review.py` captures output |
| Multi-child result comparison | ❌ `_review.py` captures but does not compare children against each other |
| Context propagation (parent observations → child) | ❌ No protocol; children start from scratch |
| Hierarchical permission inheritance | ✅ **One-way read-only** — subagents do NOT inherit parent JIT grants; subagent grants never propagate back to parent. Enforced by `SubagentManager.run_subagent` omitting `jit_state` from `sub_config` (SEC-06 fixed 2026-06-05). Tests: `test_subagent_does_not_inherit_parent_approvals`, `test_subagent_approval_doesnt_elevate_parent`. |
| Grandchild depth limit | ⚠️ `depth` field in `SubagentLineage`; no hard ceiling at API boundary |

### 5.2 For Agent Swarms (10–50 concurrent agents)

The current model (threads + git-branch sandboxes) works for tournament-style swarms where each agent runs a bounded task and returns a result. It breaks for:

- **Long-lived agents** that need to communicate mid-run (ContextBus is the right primitive; it lacks push notification)
- **Dynamic task assignment** (a parent discovering mid-run that it needs a specialist subagent for a sub-problem)
- **Shared workspace agents** (two agents editing the same file need OT or CRDT coordination; currently prevented by sandbox isolation, but that isolation has a cost)

### 5.3 For Hierarchical Delegation (parent → child → grandchild)

The `SubagentLineage.depth` field exists but there is no enforcement that a depth-3 agent cannot spawn a depth-4 agent. A rogue or confused agent could create an unbounded delegation tree. The fix is a single integer check at `SubagentManager.run()`: `if lineage.depth >= MAX_DEPTH: raise SubagentDepthLimitError`.

### 5.4 For True Multi-Agent Coordination (future)

What the architecture needs but doesn't yet have:
1. **A2A message bus**: agents sending typed messages to each other (not just parent-to-child tool calls)
2. **Shared memory space**: a namespace within ContextBus that multiple agents can read/write with conflict detection
3. **Reactive triggers**: an agent waking up in response to another agent's observation (event-driven, not polling)

---

## 6. Persistence & Session Resumption

### 6.1 Current State

| What | How | Survives process restart? | Survives machine restart? |
|------|-----|--------------------------|--------------------------|
| Audit events | JSONL, fsync per write | ✅ | ✅ (if same mount) |
| Run summary | JSONL atomic write | ✅ | ✅ |
| Background run record | JSON with PID | ✅ (file) | ❌ (PID invalid) |
| Conversation context | In-memory only | ❌ | ❌ |
| Cost accumulator | In-memory (`SessionState`) | ❌ | ❌ |
| Undo journal snapshots | Files under `.teaagent/undo/` | ✅ | ✅ |
| Agent observations | In-memory list | ❌ | ❌ |
| Tool call history (replay) | AuditLogger JSONL | ✅ (read-only) | ✅ |

**Gap:** Conversation context (the LLM message history), cost accumulator, and observations are never checkpointed. A crashed or suspended agent loses all of this. The audit log records *what happened* but not the *state needed to resume*.

### 6.2 Root Cause of Broken Resume (AG-01..04)

The suspend→resume round-trip requires:
1. Write `run_started` to audit log (missing — `task_for_run()` at `run_store.py:143` raises)
2. Serialize conversation context + observations to a checkpoint file
3. `teaagent resume <id>` reads checkpoint and rehydrates the runner
4. The runner continues from the last observation

Steps 2–4 do not exist. Step 1 is the immediate bug (TICKET-16).

### 6.3 True Session Resumption Design

To support reliable resumption, the architecture needs a **checkpoint protocol**:

```
CheckpointWriter (at each tool boundary):
  → writes: {run_id, turn_index, messages[], observations[], cost_cents, timestamp}
  → to: .teaagent/runs/<run_id>.checkpoint.json (atomic write)

ResumeLoader (at teaagent resume <id>):
  → reads checkpoint file
  → reconstructs SessionState with accumulated cost
  → reconstructs message history (messages[])
  → rehydrates AgentRunner with observations as pre-loaded context
  → continues loop from turn_index
```

**Key constraint:** Checkpoints must be written atomically (use `atomic_write_text`) at the same point as the audit log. The checkpoint and the audit log must be consistent.

**Key trade-off:** Per-turn checkpointing doubles the write I/O for long runs. A reasonable default is checkpoint every N turns (configurable, default 5) or immediately before any destructive tool call.

---

## 7. Future Governance Expansion

### 7.1 Where New Permission Modes Fit

New modes should be registered via a `PermissionModeRegistry` (not a string enum hardcoded in `policy.py`). Each mode registers:
- A name string
- An `ApprovalPolicy` instance (or factory)
- A display name and description for `--help`
- Optional: a `validate()` function called at startup

This eliminates the four-touch-point problem (§4.3) and allows operators to define custom modes in `.teaagent/config.json`.

### 7.2 Where New Policy Types Fit

Current policy types: per-tool approval, per-mode blanket rules, plan-before-write gate, file policy deny rules. Adding temporal policies (e.g., "only allow shell-mutate during business hours"), identity-scoped policies (e.g., "only this OAuth subject can approve destructive tools"), or risk-based dynamic policies (e.g., "require consensus when risk score > 0.8") requires a **policy evaluation pipeline**, not a single policy object.

Design: replace `ApprovalPolicy.assert_allowed()` with a `PolicyEvaluator.evaluate(context) → Decision(allow|deny|escalate)` that runs a chain of policy handlers. Each handler can short-circuit on deny or escalate on uncertainty.

### 7.3 Where New Audit Mechanisms Fit

The current `AuditLogger.add_sink()` API is already extensible for new sinks. What's missing:
- **Audit policy**: which events go to which sinks (e.g., L3 full-trace only to local, L1 metadata to OTel)
- **Audit signing**: events should be signable so the chain is tamper-evident not just hash-linked (the current `audit_chain.py` checks hashes but doesn't sign)
- **Cross-agent audit correlation**: a shared `correlation_id` that links parent and child agent audit events into a single trace tree

### 7.4 Where Governance Plugins Fit

Long-term, governance loops should be declaratively registered, not hardcoded in `runner/_core.py`. A `GovernancePlugin` protocol:

```python
class GovernancePlugin(Protocol):
    name: str
    def pre_tool(self, ctx: ToolCallContext) -> GovernanceDecision: ...
    def post_tool(self, ctx: ToolCallContext, result: Any) -> None: ...
    def pre_run(self, runner: AgentRunner) -> None: ...
    def post_run(self, result: RunResult) -> None: ...
```

The 5 existing loops (plan gate, tool lint, audit chain, failure card, approval queue) become default-registered plugins. New loops can be installed without modifying `runner/_core.py`.

---

## 8. Long-Term Maintainability

### 8.1 Decisions to Lock In Now

| Decision | Why lock in now | Risk of waiting |
|----------|-----------------|-----------------|
| Surface Protocol Abstraction | Every new surface will diverge without it | CG-12 compounds; web surface fork will diverge immediately |
| TICKET-12 (TUI migration) | ADR 0025 accepted; delay grows migration surface | Every new controller feature widens the gap |
| DQ-6 (undo verb) | Overlapping recovery verbs are a user safety issue | User muscle memory will make renaming harder over time |
| CheckpointWriter at tool boundary | Retro-fitting resume into a running system is hard | Resume becomes architecturally impossible once async migration starts without this foundation |
| SubagentLineage depth limit | Runaway delegation is a security/cost issue | Harder to enforce retroactively once deep hierarchies exist in production |

### 8.2 Decisions to NOT Lock In Yet

| Decision | Why wait |
|----------|----------|
| Async runner migration | Validate surface abstraction first; async migration on top of surface divergence = two simultaneous rewrites |
| PostgreSQL for audit store | Local SQLite is correct for the foreseeable scale; migrate on validated demand |
| A2A message bus | Subagent model is thread-based now; switching to message-passing before async runner is premature |
| Temporal governance policies | No user evidence this is needed yet; add when a concrete use case emerges |

### 8.3 Module Boundary Rules (enforce going forward)

1. `runner/` exports only from `runner/_types.py` and `runner/__init__.py`; nothing in `runner/` imports from `tui/` or `cli/`
2. `tui/` and `cli/` import from `chat_session_controller.py` as the single execution entry point; neither imports `run_chat_agent` directly
3. New packages under `teaagent/` must have a `_types.py` boundary module before any other file in the package imports from outside the package
4. Circular imports detected by `ADR 0010`'s import graph check must be part of CI (not just documented)

---

## Evolution Plans

### 6-Month Plan (2026-06-02 → 2026-12-01)

**Theme: Close the parity debt, stabilize the foundation.**

#### Milestone 1: Surface Parity (Month 1-2)
- [ ] **TICKET-12**: Migrate TUI to `ChatSessionController` — wires CG-11 (real cost), CG-02 (UndoJournal), CG-09/10 (suspension honesty) to TUI in one PR
- [ ] **TICKET-16** (AG-01): Write `run_started` before process detach in background suspend
- [ ] **CG-13**: Replace broad `(AttributeError, TypeError)` catch in controller with explicit mock detection
- [ ] **DQ-6**: Consolidate undo — rename TUI's git-stash path to `checkpoint restore`; `/undo` uses UndoJournal on both surfaces
- [ ] **DQ-5**: Label cost source (server-reported vs. local estimate) in both surfaces

#### Milestone 2: Resume Round-Trip (Month 2-3)
- [ ] **AG-02..04**: Implement `CheckpointWriter` — serialize conversation context + observations at each tool boundary
- [ ] **AG-resume**: `teaagent resume <id>` reads checkpoint, rehydrates `SessionState` and message history, continues loop
- [ ] Add resume acceptance test covering: suspend in REPL → resume in new process → verify cost accumulator, observations, conversation continuity

#### Milestone 3: Test Integrity and CI Gates (Month 3-4)
- [ ] **CG-16**: Rewrite `test_tui_cost_shows_session_cost` to route through `ChatSessionController` (after TICKET-12)
- [ ] Add CI gate: `grep -r '_session_cost_cents' tests/` must not contain direct injection
- [ ] Add CI gate: `python -m py_compile` import graph check for known circular dependency paths (ADR 0010 enforcement)
- [ ] Enforce `llm_conformance` suite as a required gate for new LLM provider PRs

#### Milestone 4: Surface Protocol Abstraction (Month 4-6)
- [ ] Define `SurfaceAdapter` protocol (see ADR 0026 below)
- [ ] Refactor `chat_repl.py` as `CLISurfaceAdapter`
- [ ] Refactor `tui/__init__.py` as `TUISurfaceAdapter` (builds on TICKET-12)
- [ ] Document surface registration pattern in `tool-authoring.md` equivalent for surfaces

**6-month success criteria:**
- `teaagent tui` and `teaagent chat` produce identical behavior for all controller-managed behaviors
- `teaagent resume <id>` completes a round-trip in the acceptance test suite
- Zero direct `_session_cost_cents` injections in `tests/`
- New surface can be added by implementing `SurfaceAdapter` without modifying `chat_session_controller.py` or `runner/_core.py`

---

### 1-Year Plan (2026-12-01 → 2027-06-01)

**Theme: Async-first runner, pluggable state, multi-agent coordination hardening.**

#### Quarter 3 (2026 Q4): Async Runner Migration
- [ ] **ADR 0028**: Define async migration strategy — `AgentRunner.arun()` async entry point, `run()` becomes a sync wrapper calling `asyncio.run(arun())`
- [ ] Migrate LLM adapter `chat()` to `async chat()` for all 13 providers
- [ ] Migrate workspace tool dispatch to async (uses `asyncio.to_thread()` for blocking I/O)
- [ ] SubagentManager uses `asyncio.gather()` instead of `ThreadPoolExecutor` for parallel subagents
- [ ] Maintain backward-compatible sync `AgentRunner.run()` wrapper throughout

**Trade-off:** Async migration is a large, high-risk change. It must not start until Surface Protocol Abstraction is complete — two simultaneous rewrites create untestable surface area.

#### Quarter 4 (2027 Q1): Pluggable State Store
- [ ] **ADR 0029**: `AuditStore` protocol — `SQLiteAuditStore` and `JSONLAuditStore` implementations, feature-flagged
- [ ] `RunStore` migrated to `AuditStore` protocol — local JSONL remains default; SQLite enabled via `TEAAGENT_AUDIT_STORE=sqlite`
- [ ] `BackgroundRunStore` — replace PID-based heartbeat with a heartbeat file written every 30s; resume validates heartbeat age

#### Multi-Agent Hardening
- [ ] `SubagentManager`: enforce `MAX_DEPTH=5` hard limit on lineage depth (configurable)
- [ ] `_review.py`: implement multi-child result comparison — compare outputs pairwise, flag conflicts, surface to parent for resolution
- [ ] `ContextBus`: add push notification channel (SQLite triggers or file-watch) so agents can react to peer observations without polling
- [x] **ADR 0030**: Hierarchical permission inheritance — approval lineage is one-way read-only; subagents do not inherit parent JIT grants; child grants do not propagate to parent. Implemented 2026-06-05 (SEC-06). See `SubagentManager.run_subagent` and tests `test_subagent_does_not_inherit_parent_approvals`, `test_subagent_approval_doesnt_elevate_parent`.

#### Governance Plugin System
- [ ] Define `GovernancePlugin` protocol
- [ ] Refactor 5-loop system as default-registered plugins
- [ ] Add `PermissionModeRegistry` — modes registered declaratively, not as hardcoded enum values

**1-year success criteria:**
- `AgentRunner.arun()` exists and passes all existing tests
- 10 concurrent subagents use `asyncio.gather()`, not `ThreadPoolExecutor`
- `teaagent resume` works across machine restarts (heartbeat file protocol)
- `SQLiteAuditStore` passes parity test suite against `JSONLAuditStore`
- New governance plugin installable without modifying `runner/_core.py`

---

### 3-Year Plan (2027-06-01 → 2029-06-01)

**Theme: Platform scale, cross-organization federation, policy-as-code maturity.**

#### Distributed State (Year 2)
- Optional PostgreSQL backend for `AuditStore`, `RunStore`, `ContextBus` — enables multi-user team workspaces
- Per-tenant audit isolation with row-level security
- Event-sourced audit log: append-only, replayable, exportable as evidence bundles (F-ECO-011 realized)

#### Agent Identity and Trust (Year 2)
- Cryptographic agent identity (Ed25519 key per agent instance) replaces PID-based identity
- Agent-to-agent trust graph: an orchestrator signs tasks delegated to subagents; subagents verify signature before execution
- Cross-organization federation via ANP matures from experimental to production: bidirectional audit correlation, shared trust anchors

#### Policy-as-Code Maturity (Year 2-3)
- `policy.yaml` becomes a version-controlled artifact with a migration system (schema versioned, changes audited)
- Policy change events are first-class audit events: who changed what policy, when, and with what justification
- Temporal policies: time-scoped permission grants (e.g., elevated access during incident response windows)
- Risk-scoring pipeline: policies can reference a `RiskScorer` that evaluates tool call risk dynamically and routes to appropriate approval tier

#### Native WASM Skills (Year 2-3)
- `wasm_runtime.py` graduated from beta to production
- Skills compiled to WASM run in a deterministic, sandboxed environment with bounded memory and CPU
- Skill marketplace (`marketplace/`) distributes signed WASM artifacts; signature verified at load time (Sigstore integration)

#### Reactive Multi-Agent Coordination (Year 3)
- A2A message bus: typed messages between agents within a workspace (not just parent→child tool delegation)
- Shared memory namespace in `ContextBus` with optimistic concurrency control (version field, conflict detection)
- Event-driven agent wakeup: an agent can register an observation trigger and be resumed when another agent records a matching observation
- Cross-workspace federation: teams can share a ContextBus across workspaces with explicit access control

**3-year success criteria:**
- A team of 10 developers sharing a PostgreSQL-backed workspace workspace with independent audit trails per user
- `teaagent` listed as a certified ANP participant (cross-org agent interoperability)
- Skills distributed and verified via Sigstore-backed marketplace
- A parent agent can dynamically spawn, communicate with, and merge results from 20 concurrent subagents using async coordination

---

## Architecture Decision Records

### ADR 0026: Surface Protocol Abstraction

**Status:** Proposed — 2026-06-02

**Context:** TeaAgent has two interactive surfaces (CLI REPL, TUI) and a plan for more (web, IDE embedded, mobile). Without a surface protocol, each new surface independently re-implements execution wiring (as TUI did, producing CG-12). The `ChatSessionController` is the execution path; the surfaces are I/O adapters.

**Decision:** Define a `SurfaceAdapter` protocol in `teaagent/surface_adapter.py`:

```python
class SurfaceAdapter(Protocol):
    def output(self, text: str) -> None: ...
    def prompt(self, message: str) -> str: ...
    def on_run_start(self, task: str) -> None: ...
    def on_run_end(self, result: ExecutionResult) -> None: ...
    def on_approval_request(self, request: ApprovalRequest) -> bool: ...
```

`ChatSessionController` accepts a `SurfaceAdapter` instead of a bare `output_fn: Callable`. Each surface (`CLISurfaceAdapter`, `TUISurfaceAdapter`) implements the protocol. New surfaces implement `SurfaceAdapter` without touching the controller.

**Consequences:**
- (+) New surfaces cannot bypass execution governance by construction
- (+) Surface tests can use a `StubSurfaceAdapter` that records outputs without a real TTY
- (-) `TUISurfaceAdapter` wraps `prompt_toolkit` interaction; async `prompt()` requires care in sync context
- (-) Breaking change to `ChatSessionController.__init__` signature; all callers must be updated in one PR

**Trade-offs considered:**
- Alternative: keep bare `Callable` and add surface methods one by one → same fragmentation as today
- Alternative: make TUI call `ChatSessionController` via message queue → over-engineered; adds latency for local I/O

**Implementation:** TICKET-12 is the prerequisite (TUI adoption of controller). Surface protocol extraction follows TICKET-12 in the same milestone.

---

### ADR 0027: Session State Checkpointing for True Resumption

**Status:** Proposed — 2026-06-02

**Context:** Agent suspend→resume is broken (AG-01..04). The root cause is twofold: (1) `run_started` is never written before process detach (immediate bug, TICKET-16), and (2) conversation context, cost, and observations are never checkpointed (structural gap). Even after fixing (1), resuming an agent that crashed mid-task would restart from scratch, losing all accumulated work.

**Decision:** Introduce a `CheckpointWriter` that writes an atomic checkpoint at each tool boundary:

```python
@dataclass
class AgentCheckpoint:
    run_id: str
    turn_index: int
    messages: list[LLMMessage]
    observations: list[dict]
    cost_cents: float
    written_at: str

class CheckpointWriter:
    def __init__(self, path: Path) -> None: ...
    def write(self, checkpoint: AgentCheckpoint) -> None:  # atomic_write_text
```

`AgentRunner` calls `checkpoint_writer.write()` after each successful tool dispatch. `teaagent resume <id>` loads the checkpoint, reconstructs `SessionState`, rehydrates `AgentRunner`, and continues the loop.

**Checkpoint frequency:** Every tool boundary by default. Configurable via `TEAAGENT_CHECKPOINT_INTERVAL_TURNS` (default 1; set higher for performance-sensitive runs).

**Consistency guarantee:** Checkpoint is written *after* the audit event for the same turn. If a crash occurs between audit write and checkpoint write, the run replays the last turn on resume (idempotent tool calls are safe; non-idempotent are re-prompted).

**Consequences:**
- (+) Crash recovery: agent resumes from last checkpoint, not from scratch
- (+) Process migration: checkpoint file can be copied to a new machine for continuation
- (-) I/O overhead: one `atomic_write_text` per tool call (mitigable with interval)
- (-) Message history size grows with turns; checkpoint files can become large for long runs (mitigate with context compaction before write)

**Alternatives considered:**
- Checkpoint only on `/background` suspend → doesn't help with crashes
- WAL-style append-only checkpoint log → more complex, benefits unclear at current scale

---

### ADR 0028: Async-First AgentRunner Migration Strategy

**Status:** Proposed — 2026-06-02

**Context:** `AgentRunner` is synchronous. LLM calls, tool I/O, and subagent coordination are all blocking. As concurrent subagent counts increase, the thread-per-agent model (ThreadPoolExecutor in SwarmManager) wastes threads on I/O wait and hits GIL pressure on CPU-bound tasks. The async migration is necessary for 100× scale.

**Decision:** Introduce `AgentRunner.arun()` as the primary async entry point. `AgentRunner.run()` becomes a compatibility shim:

```python
def run(self, task: str, ...) -> RunResult:
    return asyncio.get_event_loop().run_until_complete(self.arun(task, ...))
```

Migration order:
1. `LLMAdapter.chat()` → `async chat()` (all 13 providers)
2. Workspace tool dispatch → `asyncio.to_thread()` for blocking file I/O
3. `AgentRunner._dispatch_tool()` → `await tool_fn(args)`
4. `AgentRunner.arun()` — full async loop
5. `SubagentManager.run_parallel()` → `asyncio.gather()`
6. `SwarmManager` — replace `ThreadPoolExecutor` with `asyncio.TaskGroup`

**Prerequisite:** Surface Protocol Abstraction (ADR 0026) must be complete. The TUI uses `prompt_toolkit`'s own event loop; the sync/async boundary must be managed at the surface, not inside the runner.

**Consequences:**
- (+) 10–100 concurrent subagents without thread pool exhaustion
- (+) Backpressure is natural (awaiting slow LLM responses doesn't block other agents)
- (-) All existing tests that call `runner.run()` directly continue to work via the shim; tests that mock `LLMAdapter.chat()` must be updated to `AsyncMock`
- (-) `async_bridge.py` can be deleted once migration is complete

**Trade-offs considered:**
- Keep sync runner, add separate `AsyncAgentRunner` class → two codebases to maintain
- Use `concurrent.futures` thread pool forever → cannot hit 100× target
- Trio or AnyIO instead of asyncio → complexity without benefit; ecosystem compatibility worse

---

### ADR 0029: Pluggable Audit and Run Store

**Status:** Proposed — 2026-06-02

**Context:** All state (audit events, run summaries, memory catalog) is stored in JSONL with `fcntl.LOCK_EX`. This is correct for single-user local workspaces. Team workspaces, NFS mounts, and cloud deployments require a different backend. ADR 0008 acknowledged this and deferred it. It is now blocking cloud and multi-user scenarios.

**Decision:** Introduce `AuditStore` and `RunStore` protocols. Concrete implementations: `JSONLAuditStore` (current, remains default), `SQLiteAuditStore` (new, single-machine team), `PostgresAuditStore` (future, distributed). Selected via `TEAAGENT_AUDIT_STORE` environment variable or `.teaagent/config.json`.

```python
class AuditStore(Protocol):
    def append(self, event: AuditEvent) -> None: ...
    def events(self, run_id: str) -> Iterator[AuditEvent]: ...
    def integrity_check(self, run_id: str) -> bool: ...
```

The `AuditLogger` class wraps an `AuditStore` instance. Sinks continue to plug into `AuditLogger.add_sink()`.

**Migration path:** `JSONLAuditStore` is the default and remains unchanged. `SQLiteAuditStore` is feature-flagged. A parity test suite (`tests/stores/test_audit_store_parity.py`) validates that all store implementations produce identical results for the same event sequence.

**Consequences:**
- (+) NFS-safe team workspaces become possible with SQLite
- (+) Cloud deployments can use Postgres without changing `AuditLogger` callers
- (-) New `AuditStore` implementations must pass the parity test suite (new contributor burden)
- (-) Hash-chain integrity check is store-specific; each implementation must implement it correctly

---

### ADR 0030: Hierarchical Agent Trust and Permission Inheritance

**Status:** Proposed — 2026-06-02

**Context:** `SubagentLineage` tracks `parent_run_id`, `depth`, and `isolation`. There is no enforcement that a child agent cannot hold permissions its parent does not have — the child's `PermissionMode` is set independently at `SubagentManager.run()` time. A child could be spawned with `danger-full-access` by a parent running in `read-only` mode.

**Decision:** Enforce permission inheritance at `SubagentManager`:

1. A child agent's effective `PermissionMode` is the *more restrictive* of (parent mode, requested mode). The parent cannot delegate permissions it does not hold.
2. `SubagentLineage` carries `effective_permission_mode: PermissionMode` (not just `def_name`). This is set at spawn time and cannot be overridden by the child.
3. `MAX_LINEAGE_DEPTH = 5` (configurable via `TEAAGENT_MAX_AGENT_DEPTH`). `SubagentManager.run()` raises `SubagentDepthLimitError` if `lineage.depth >= MAX_LINEAGE_DEPTH`.
4. Each depth level is recorded in the audit log with the inherited permission mode; governance fuzz tests validate that escalation is impossible.

**Consequences:**
- (+) A compromised or confused child cannot escalate its permissions above the parent's
- (+) Depth limit prevents runaway delegation trees (security and cost)
- (-) Some legitimate orchestration patterns (root orchestrator in `read-only`, specialist child in `allow`) are prevented — the orchestrator must itself hold `allow` to grant it
- (-) Breaking change for any existing code that spawns children with elevated modes; audit existing usages before merging

**Alternatives considered:**
- Allowlist-based escalation: parent explicitly grants specific extra permissions to child → more flexible but significantly more complex; deferred to Year 2
- No enforcement, just logging → insufficient; logging a violation after it happens does not prevent it

---

## Decision Log

| Decision | Resolution | Date | Rationale |
|----------|-----------|------|-----------|
| DQ-1 (P-OPS background journeys) | Open | — | Pending enterprise commitment signal |
| DQ-2 (parallel experiment artifact) | Open | — | Pending ML persona validation |
| DQ-3 (TUI fixed-region vs. drop auto-clear) | Option (b) now, (a) later | 2026-06-01 | Stop regression first |
| DQ-4 (prompt+background behavior) | Option (b): refuse with message | 2026-06-01 | Safety default |
| DQ-5 (cost source labeling) | Both, labeled | — | Implement in TICKET-12 |
| DQ-6 (undo verb consolidation) | Option (a): rename git-stash to `checkpoint restore` | — | Recovery hazard outweighs breaking-change friction |
| DQ-7 (doc working mode) | Maintain doc package + backlog | 2026-06-01 | INDEX is durable; issues are disposable |
| ADR-0026 (Surface Protocol) | Proposed | 2026-06-02 | — |
| ADR-0027 (Checkpointing) | Proposed | 2026-06-02 | — |
| ADR-0028 (Async Runner) | Proposed | 2026-06-02 | — |
| ADR-0029 (Pluggable Store) | Proposed | 2026-06-02 | — |
| ADR-0030 (Agent Trust) | Proposed | 2026-06-02 | — |

---

## Appendix: Risk Register for Proposed ADRs

| ADR | Highest Risk | Mitigation |
|-----|-------------|------------|
| 0026 (Surface) | TUI prompt_toolkit event loop conflicts with sync controller | Implement `TUISurfaceAdapter.prompt()` using `prompt_toolkit`'s `run_in_executor` |
| 0027 (Checkpoint) | Checkpoint file grows unbounded for very long runs | Cap at last N checkpoints (default 10); compact messages before writing |
| 0028 (Async) | `AsyncMock` migration breaks existing test suite in bulk | Introduce `arun()` first without removing `run()`; migrate tests incrementally |
| 0029 (Store) | Parity divergence between `JSONLAuditStore` and `SQLiteAuditStore` | Mandatory parity test suite; both stores must pass before merging |
| 0030 (Trust) | Breaks orchestrator patterns that currently rely on child escalation | Audit all `SubagentManager.run()` call sites before enforcing; add explicit override for root orchestrator |

---

*This document should be reviewed and updated at each major milestone. Next scheduled review: 2026-09-01 (end of 6-month plan milestone 2).*
