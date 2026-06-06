# Multi-Agent Coordination Critique — teaAgent
**Date:** 2026-06-06  
**Scope:** Remote-orchestration perspective on subagent spawning, state consistency, failure modes, latency tolerance, scaling, communication, and testing coverage.  
**Method:** Full codebase trace; every claim is pinned to a file:line.

---

## 1. Capability Inventory

### 1.1 What Exists and Is Code-Grounded

| Capability | Entry Point | Status |
|---|---|---|
| Single subagent spawn | [`subagents/_manager.py:82`](../../teaagent/subagents/_manager.py) `run_subagent()` | Implemented |
| Batch parallel spawn | [`subagents/_tools.py:232`](../../teaagent/subagents/_tools.py) `_register_batch()` + `ThreadPoolExecutor` | Implemented |
| Named-team orchestration | [`subagents/_team_orchestrator.py:166`](../../teaagent/subagents/_team_orchestrator.py) `TeamOrchestrator.run_team()` | Implemented |
| Swarm execution | [`swarm.py:532`](../../teaagent/swarm.py) `SwarmManager.execute_swarm()` | Implemented (separate layer) |
| Depth-capped recursion | [`subagents/_manager.py:112`](../../teaagent/subagents/_manager.py) — checked per `SubagentDef.max_depth` | Partial (see §7.2) |
| Approval state propagation | [`subagents/_approval_queue.py:673`](../../teaagent/subagents/_approval_queue.py) centralized queue singleton | Implemented |
| JIT approval isolation (SEC-06) | [`subagents/_manager.py:207`](../../teaagent/subagents/_manager.py) — passes `jit_state=None` to child | Implemented, tested |
| Permission mode capping | [`subagents/_manager.py:32–256`](../../teaagent/subagents/_manager.py) `MAX_CHILD_PERMISSION='workspace-write'` | Implemented |
| Isolation modes | [`subagents/_isolation.py:24`](../../teaagent/subagents/_isolation.py) — `shared/worktree/directory-snapshot/docker` | Implemented |
| Diff capture / patch apply | [`subagents/_review.py:35`](../../teaagent/subagents/_review.py) `capture_subagent_review()` / `apply_subagent_review()` | Implemented |
| Per-subagent cost tracking | [`subagents/_types.py:75`](../../teaagent/subagents/_types.py) `cost_cents` field, audit log | Implemented |
| Swarm cost aggregation | [`swarm.py:624`](../../teaagent/swarm.py) `SwarmReport.total_cost_cents` | Implemented |
| Heartbeat tracking | [`swarm.py:395`](../../teaagent/swarm.py) heartbeat thread + `threading.Event` | Implemented (swarm only) |
| Lineage tracing | [`subagents/_types.py:28`](../../teaagent/subagents/_types.py) `SubagentLineage`, audit `subagent_lineage` event | Implemented |

### 1.2 What Is Missing or Not Integrated

| Claimed / Expected | Reality |
|---|---|
| Parent budget cap propagated to children | **Not propagated.** Parent's `max_estimated_cost_cents` never reaches child config. Children get fixed `max_iterations=5, max_tool_calls=5` from `SubagentDef` defaults. |
| Undo journal synchronization | **One-way diff only.** Child changes are captured as a git patch ([`_review.py:35`](../../teaagent/subagents/_review.py)); there is no live undo sync. Parent cannot undo a shared-isolation child write mid-run. |
| Distributed approval queue | **In-process singleton only.** `_approval_queues` is a module-level `dict` ([`_approval_queue.py:673`](../../teaagent/subagents/_approval_queue.py)) killed with the process. |
| Swarm ↔ SubagentManager integration | **Parallel, independent layers.** `SwarmManager` and `SubagentManager` share no state, no approval queue, no cost rollup. Tournament uses `SwarmManager`; the `subagent` tool uses `SubagentManager`. |

---

## 2. State Diagram — Parent ↔ Child

```
PARENT
  │
  ├─ permission_mode ──────────► capped to MAX_CHILD_PERMISSION if unsafe ─► child config
  │                                  (_manager.py:230–256)
  │
  ├─ jit_state ───────────────► NOT passed (jit_state=None) ─────────────► child gets fresh JIT
  │                                  (_manager.py:207)
  │
  ├─ max_estimated_cost_cents ─► NOT passed ──────────────────────────────► child ignores parent budget
  │
  ├─ parent_run_id ────────────► context var ─────────────────────────────► approval queue key
  │                                  (subagent_run_context.py:5)
  │
  ├─ workspace root ───────────► shared / worktree / snapshot / docker ───► child isolation context
  │
  ├─ approval queue ───────────► CentralizedApprovalQueue singleton ──────► child submits sync requests
  │   (blocking, 180s timeout)         (_approval_queue.py:278)
  │
  └─ audit log ────────────────► separate per-run .jsonl ─────────────────► lineage event written at end
                                      (_manager.py:300)

CHILD
  │
  ├─ tool execution ───────────► if destructive + batch_index set ─────────► submit_request_sync() blocks
  │
  ├─ cost_cents ───────────────► captured at end ──────────────────────────► returned in SubagentSession
  │
  ├─ diff ─────────────────────► captured before cleanup ─────────────────► .patch in subagent-reviews/
  │
  └─ state changes ────────────► shared-mode: direct on parent workspace
                                 worktree: git worktree, merge needed
                                 snapshot: copy, apply_subagent_review() needed
                                 docker: container, explicit export needed
```

**Divergence points** (states that can go out of sync):

| State | Sync mechanism | Can diverge? |
|---|---|---|
| Permission mode | Capped at spawn, immutable | No |
| JIT approval | Isolated by design | No (deliberate) |
| Cost / budget | None — child tracks independently | **Yes** — parent cannot enforce spend cap |
| Workspace files (shared mode) | None — concurrent writes unordered | **Yes** — concurrent children race |
| Workspace files (worktree) | Manual `apply_subagent_review()` | **Yes** — parent must explicitly apply |
| Undo journal | Not synced | **Yes** — parent can't undo child shared writes |
| Approval queue state | In-memory singleton | **Yes** — lost on process crash |

---

## 3. Failure Scenario Matrix

| Scenario | Impact | Current handling | Severity |
|---|---|---|---|
| **Subagent hangs indefinitely** | Parent thread blocked in `ThreadPoolExecutor.as_completed()` until swarm timeout (600 s) | Partial results collected after `FuturesTimeoutError` ([`swarm.py:713`](../../teaagent/swarm.py)) — but only in SwarmManager, not SubagentManager batch | High |
| **Subagent crashes / raises exception** | Exception caught per-future; returns error dict | Handled; parent sees `{'error': str(e)}` | Medium |
| **Approval queue timeout (child waiting 180 s)** | Tool call denied (returns `False`) | Logged as TIMEOUT; child proceeds without approval — effectively a deny | Medium |
| **Parent process crashes mid-batch** | All in-flight child threads lose their approval queue; all pending requests are lost | **No recovery.** Queue is in-memory only; `_persist()` writes JSON but reload is manual | Critical |
| **Concurrent shared-isolation children writing same file** | Silent file corruption; last writer wins | **No protection.** No file locking, no conflict detection in shared mode | Critical |
| **Approval queue asyncio loop not running when sync child resolves** | `_loop` is `None`; `call_soon_threadsafe` raises `AttributeError` | `contextlib.suppress(RuntimeError)` at line 440 swallows the error; future never resolves → 180 s timeout | High |
| **Subagent spawns subagent (depth > 1) without named def** | Depth check at `_manager.py:112` only fires when `sub_def` is not `None`; ad-hoc spawns may bypass | Unbounded recursion if raw `subagent` tool is called without a `SubagentDef` binding | High |
| **ThreadPoolExecutor saturated (>max_workers pending)** | Excess tasks queue in-process; memory grows without bound | No queue size limit; no backpressure signal | Medium |
| **Child cost exceeds parent's intended budget** | Parent budget not enforced at child level | No mechanism; parent sees total only post-facto in audit | High |
| **Docker isolation container fails to start** | Child cannot run | Exception propagated to parent result dict — no retry | Medium |

---

## 4. Latency Tolerance

### 4.1 Timeout Inventory

| Timeout | Value | Location | What happens on expiry |
|---|---|---|---|
| Swarm batch timeout | 600 s (10 min) | [`swarm.py:691`](../../teaagent/swarm.py) | `FuturesTimeoutError` — partial results returned |
| Approval request (async) | 180 s (3 min) | [`_approval_queue.py:452`](../../teaagent/subagents/_approval_queue.py) | Request marked TIMEOUT; tool call denied |
| Approval request (sync, polling) | 180 s (3 min) | [`_approval_queue.py:316`](../../teaagent/subagents/_approval_queue.py) | Returns `False` (deny); child proceeds |
| SubagentManager batch | None explicit | [`_tools.py:284`](../../teaagent/subagents/_tools.py) | **No timeout.** ThreadPoolExecutor with `as_completed()` blocks indefinitely if no timeout is passed |

**Key gap:** the `_register_batch()` path in `_tools.py:284` uses `ThreadPoolExecutor` + `as_completed()` **without a timeout**. A single hanging child blocks the batch forever. The 600 s timeout exists only in `SwarmManager._execute_subagent_batch()`.

### 4.2 Retry / Backoff

**None.** No retry logic exists at the subagent coordination layer. A failed or timed-out child is reported as an error and the batch continues. This is a one-shot model.

### 4.3 Circuit Breaker

**None.** There is no mechanism to stop spawning new subagents after a threshold of failures, nor to reduce concurrency under load.

---

## 5. Scaling Limits

### 5.1 Concurrency Controls

| Layer | Default limit | Location | Adjustable? |
|---|---|---|---|
| SubagentManager batch (`subagent_batch` tool) | `max_workers` = from tool arg (no default cap shown) | [`_tools.py:284`](../../teaagent/subagents/_tools.py) | Yes, via tool argument |
| TeamOrchestrator | `max_concurrent = 3` | [`_team_orchestrator.py:122`](../../teaagent/subagents/_team_orchestrator.py) | Via TeamDef YAML |
| SwarmManager | `max_parallel = 3` | [`swarm.py:370`](../../teaagent/swarm.py) | Via constructor |

### 5.2 Resource Limits

- **Threads:** Each concurrent subagent occupies one `ThreadPoolExecutor` thread. Python's GIL does not protect I/O-bound threads, so 20+ parallel children is realistic but all compete for file and network handles.
- **Approval queue threads:** Each child blocked on approval spins a thread (250 ms poll loop at [`_approval_queue.py:318`](../../teaagent/subagents/_approval_queue.py)). 10 blocked children = 10 spinning threads simultaneously.
- **Memory:** Directory-snapshot isolation copies the entire workspace per child ([`_isolation.py:135`](../../teaagent/subagents/_isolation.py)). 10 children × 500 MB workspace = 5 GB temporary storage.
- **Audit log:** Each run writes to `.teaagent/runs/*.jsonl`. High-frequency subagent spawning generates unbounded files with no rotation or cleanup.
- **Approval queue dict:** In-memory `dict` with no size cap. 10,000 past requests accumulate in RAM without eviction.

### 5.3 "Can You Actually Spawn 10 Nested Agents?"

- **Batch (flat):** Yes, if `max_workers` is set high enough. All 10 run in parallel threads.
- **Nested (depth > 1):** Only if each level uses a named `SubagentDef` with `max_depth > 1`. The default `max_depth = 1` ([`subagents/_types.py:22`](../../teaagent/subagents/_types.py)) blocks a level-1 child from spawning level-2 children with a named def. Without a def, depth enforcement is bypassed.
- **10 levels deep:** Not guarded globally. If each `SubagentDef.max_depth` is permissive, recursion can go arbitrarily deep with no global circuit breaker.

---

## 6. Communication Model Assessment

### 6.1 Pattern: Synchronous-blocking with in-process queue

```
Parent thread (LLM tool call)
    │
    ▼
SubagentManager.run_subagent()   ← blocks until child returns
    │
    ▼
ThreadPoolExecutor.submit()      ← child runs in worker thread
    │
    ├─ child needs approval ────► submit_request_sync() ← worker thread blocks on threading.Event (250ms poll)
    │                                  │
    │                           Parent TUI/CLI polls queue
    │                           Parent approves → event.set() → child unblocks
    │
    └─ child completes ─────────► result dict returned to parent
```

**Assessment:** This is a **synchronous blocking model disguised with threads**, not a true async message-passing architecture. The consequences:

1. **No back-pressure:** Parent submits work as fast as the LLM calls tools. No rate limiting on spawning.
2. **No result streaming:** Parent cannot act on partial batch results until all children finish (or timeout).
3. **No distributed coordination:** The approval queue singleton only works in-process. A multi-process or multi-machine deployment would have no approval routing.
4. **Mixed asyncio + threading is fragile:** The `_approval_queue.py` bridges async futures and threading events at [`lines 259–270`](../../teaagent/subagents/_approval_queue.py). If the asyncio event loop is on a different thread than expected, `get_running_loop()` at line 441 returns `None` and the bridge silently fails. The `contextlib.suppress(RuntimeError)` at line 440 hides the failure mode.

### 6.2 Context Variable Propagation

Parent-run context is propagated via `contextvars.ContextVar` ([`subagent_run_context.py:5`](../../teaagent/subagent_run_context.py)). This works correctly for single-threaded or async code but may lose context across `ThreadPoolExecutor` worker threads unless `copy_context()` is used at submission. **This is not verified in the codebase.**

---

## 7. Testing Coverage Gaps

### 7.1 What Is Covered

- Single subagent spawn, depth limit enforcement with named def ([`tests/test_subagent.py`](../../tests/test_subagent.py))
- Batch concurrent timing ([`tests/test_subagent_batch.py:51`](../../tests/test_subagent_batch.py))
- Team orchestrator YAML/JSON loading ([`tests/test_subagent_team_orchestrator.py`](../../tests/test_subagent_team_orchestrator.py))
- JIT approval isolation SEC-06, including adversarial case ([`tests/integration/test_subagent_budget_inheritance.py:92–241`](../../tests/integration/test_subagent_budget_inheritance.py))
- Approval queue sync submit/approve/deny/timeout ([`tests/test_subagent_approval_queue_integration.py`](../../tests/test_subagent_approval_queue_integration.py))
- Isolation modes (worktree, directory-snapshot, docker) ([`tests/test_subagent_isolation.py`](../../tests/test_subagent_isolation.py))

### 7.2 Gaps — Missing Coverage

| Gap | Risk | Why it matters |
|---|---|---|
| **Depth > 2 nesting (real recursive chain)** | High | Default max_depth=1, but ad-hoc spawning without a named def bypasses the check; unbounded recursion possible |
| **Concurrent shared-isolation children writing same file** | Critical | Race condition; no test verifies last-writer-wins or conflict detection |
| **Batch tool timeout (no deadline passed to as_completed)** | High | `_tools.py:284` has no timeout; a hanging child blocks forever — untested |
| **Approval queue across thread boundary with no asyncio loop** | High | `contextlib.suppress(RuntimeError)` on line 440 hides this failure path |
| **Budget cap: child exceeds parent's max_estimated_cost_cents** | High | Not propagated; no test proves children are bounded by parent's spend limit |
| **Approval queue persistence across process restart** | Critical | `_persist()` / `reload_from_store()` exists but is optional; restart recovery untested |
| **10+ concurrent subagents (ThreadPoolExecutor at scale)** | Medium | Only tested with 2–3 in batch tests; starvation and memory at N=10+ unknown |
| **contextvars propagation into ThreadPoolExecutor workers** | Medium | `parent_run_id` context var may not propagate unless `copy_context()` is used at submit |
| **Swarm + SubagentManager interaction** | Medium | Two parallel layers; no test exercises both simultaneously |
| **Partial batch failure with mix of success/fail** | Medium | `test_batch_handles_task_failure` covers single failure; mix of failures and timeouts is not tested |
| **Docker isolation container lifecycle under concurrent load** | Low | `test_subagent_docker_container_hardened` exists but tests single container; concurrent containers untested |

---

## 8. Critical Assessment

### Is the current subagent model production-ready?

**No — with qualification.** The implementation is architecturally sound for a single-process, single-user agent running short-lived tasks. It is not safe for high-concurrency, multi-process, or long-running orchestration scenarios.

### Scenarios That Would Fail Catastrophically

**Scenario 1: Shared isolation + concurrent writes**  
Two parallel subagents both targeting the same file in `shared` isolation (the default) will silently corrupt each other's output. No lock, no conflict detection, no warning. A parent spawning `subagent_batch([edit file X, edit file X])` produces undefined behavior. The test suite does not cover this.

**Scenario 2: Parent crash mid-approval**  
10 children are blocked on destructive tool approvals. Parent process exits (OOM, SIGKILL). The `threading.Event` objects are gone. All children are stranded with no reply, will time out after 180 s, then proceed with deny. The persisted queue JSON (if `_store` is configured) must be manually reloaded — there is no automatic recovery mechanism.

**Scenario 3: Budget overrun via batch spawning**  
Parent has `max_estimated_cost_cents = 100`. It spawns 20 subagents via `subagent_batch`. Each child has `max_iterations=5, max_tool_calls=5` from its `SubagentDef`. Each makes 5 LLM calls costing 5¢. Total: $1.00, 10× parent's budget. The parent's budget limit is never checked against children because it is never passed to them. The audit log will record the overrun, but it cannot prevent it.

**Scenario 4: Unbounded recursion via raw subagent tool**  
A child agent (via the `subagent` tool, not a named `SubagentDef`) calls the `subagent` tool again. The depth check at `_manager.py:112` only fires when `sub_def` is not `None`. Without a named def, `depth` increments but the guard does not trigger. This creates an unbounded call chain that terminates only when the LLM decides to stop or the host OOMs.

**Scenario 5: asyncio loop boundary crash silently swallowed**  
A child in a `ThreadPoolExecutor` worker calls `submit_request_sync()`. Internally, the method tries to get the running asyncio loop with `asyncio.get_running_loop()` ([`line 441`](../../teaagent/subagents/_approval_queue.py)). If the call is made from a thread with no running loop, `RuntimeError` is raised and suppressed by `contextlib.suppress(RuntimeError)`. The future is created but `_loop` remains `None`. When the parent tries to resolve the future via `_resolve_future_threadsafe()`, `call_soon_threadsafe(None, ...)` raises `AttributeError`. The child waits 180 s, times out, and the approval is silently denied. No error surfaces to the user.

### Where the Design Is Naive

1. **Threading as the concurrency model.** Python threads are GIL-bound for CPU work and carry OS-level overhead. The `ThreadPoolExecutor` model means every concurrent subagent holds a real OS thread. At 50 concurrent agents, this is 50 × thread-stack memory (~8 MB each on macOS = 400 MB) plus 50 spinning poll loops for approvals.

2. **In-memory queue as the coordination hub.** A real multi-agent system needs a durable, inspectable message queue (Redis, SQLite, Kafka). The in-memory dict is invisible to external monitoring, lost on crash, and cannot coordinate across processes.

3. **No back-pressure or admission control.** The LLM can call `subagent_batch` with `tasks=[...×100]` and the system will attempt to spawn 100 concurrent threads. There is no policy layer that says "at most N subagents globally."

4. **Two parallel orchestration layers.** `SwarmManager` and `SubagentManager` solve the same problem differently with no shared state. This is a maintainability liability: a fix to approval routing in one layer does not fix the other.

5. **Default isolation is `shared`.** This is the most dangerous default possible. The safe default should be `worktree` (git-isolated). Choosing `shared` as the default means every bug in a child agent directly damages the parent workspace without a recovery path.

---

## 9. Recommended Hardening

### P0 — Prevents data loss or security bypass

| # | Recommendation | File(s) to change |
|---|---|---|
| P0-MA-001 | **Fix shared-isolation race condition.** Either change `DEFAULT_SUBAGENT_ISOLATION` to `'worktree'`, or add a file-level `fcntl` lock when children write in shared mode. | [`subagents/_isolation.py:8`](../../teaagent/subagents/_isolation.py) |
| P0-MA-002 | **Enforce global depth limit regardless of def presence.** Add a check at `run_subagent()` entry that enforces a hard global max depth (e.g., 5) using the `depth` parameter, independent of `sub_def`. | [`subagents/_manager.py:87`](../../teaagent/subagents/_manager.py) |
| P0-MA-003 | **Propagate parent budget cap to children.** Pass `max_estimated_cost_cents` from parent `ChatAgentConfig` to child, scaled by `1 / expected_children` or set as an explicit `child_budget_cents` field in `SubagentDef`. | [`subagents/_manager.py:261`](../../teaagent/subagents/_manager.py), [`subagents/_types.py`](../../teaagent/subagents/_types.py) |
| P0-MA-004 | **Add timeout to `_register_batch()` `as_completed` call.** Mirror the 600 s timeout from `SwarmManager._execute_subagent_batch()`. | [`subagents/_tools.py:289`](../../teaagent/subagents/_tools.py) |

### P1 — Prevents silent failures or hard-to-debug states

| # | Recommendation | File(s) to change |
|---|---|---|
| P1-MA-001 | **Replace `contextlib.suppress(RuntimeError)` in approval queue with explicit error logging.** Surface the asyncio loop boundary miss instead of hiding it. | [`subagents/_approval_queue.py:440`](../../teaagent/subagents/_approval_queue.py) |
| P1-MA-002 | **Verify `contextvars` propagation into `ThreadPoolExecutor` workers.** Explicitly `copy_context().run()` at submission site to ensure `parent_run_id` and `_parallel_approval` context vars are available in worker threads. | [`subagents/_tools.py:284`](../../teaagent/subagents/_tools.py) |
| P1-MA-003 | **Add admission control / global concurrency cap.** Introduce a configurable `MAX_GLOBAL_SUBAGENTS` semaphore in `SubagentManager` that blocks new spawns when the limit is reached. | [`subagents/_manager.py`](../../teaagent/subagents/_manager.py) |
| P1-MA-004 | **Make approval queue durable by default.** Require `_store` initialization (SQLite or JSON file) at `SubagentManager` construction, and auto-reload on startup. Remove the optional path. | [`subagents/_approval_queue.py:673`](../../teaagent/subagents/_approval_queue.py) |

### P2 — Long-term architecture

| # | Recommendation |
|---|---|
| P2-MA-001 | **Unify SwarmManager and SubagentManager.** One orchestration layer with shared approval routing, cost accounting, and heartbeat tracking. |
| P2-MA-002 | **Replace polling approval queue with true async push.** Use `asyncio.Queue` end-to-end, eliminating the 250 ms spin loop and the thread-event bridge. |
| P2-MA-003 | **Add circuit breaker.** If > N% of subagents in a batch fail within the last K seconds, pause new spawning and surface a degraded state signal to the parent. |
| P2-MA-004 | **Write missing tests.** Priority: shared-isolation concurrent write test, batch-with-no-timeout test, budget-cap-enforcement test, depth-without-def test, contextvars-propagation test. |

---

## Appendix: Key File Map

| File | Role |
|---|---|
| [`teaagent/subagents/_manager.py`](../../teaagent/subagents/_manager.py) | Core subagent lifecycle: spawn, permission cap, lineage, cost capture |
| [`teaagent/subagents/_tools.py`](../../teaagent/subagents/_tools.py) | Tool registration: `subagent`, `subagent_batch`, `team` |
| [`teaagent/subagents/_approval_queue.py`](../../teaagent/subagents/_approval_queue.py) | Centralized approval queue: async + sync paths, singleton registry |
| [`teaagent/subagents/_isolation.py`](../../teaagent/subagents/_isolation.py) | Isolation context: shared/worktree/snapshot/docker |
| [`teaagent/subagents/_review.py`](../../teaagent/subagents/_review.py) | Diff capture and patch application for isolated subagents |
| [`teaagent/subagents/_team_orchestrator.py`](../../teaagent/subagents/_team_orchestrator.py) | Team definition loading and specialist dispatch |
| [`teaagent/subagents/_types.py`](../../teaagent/subagents/_types.py) | `SubagentDef`, `SubagentLineage`, `SubagentSession` data classes |
| [`teaagent/subagent_run_context.py`](../../teaagent/subagent_run_context.py) | Context vars: `parent_run_id`, `parallel_approval` mode |
| [`teaagent/swarm.py`](../../teaagent/swarm.py) | Parallel `SwarmManager` layer (independent of `SubagentManager`) |
| [`teaagent/coordinator.py`](../../teaagent/coordinator.py) | Task routing and workflow planning (separate from spawning) |
