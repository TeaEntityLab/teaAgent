# TeaAgent Concurrency Model — 2026-06-02

How concurrent operations are handled, where locking exists, known race conditions,
and lock ordering rules.

---

## Overview

TeaAgent is primarily **single-threaded per TUI session**. The main REPL loop
is synchronous. The agent run loop inside `AgentRunner.run()` is synchronous.
Concurrency enters through:

1. `AuditLogger` — shared across threads (explicit lock).
2. File watcher thread — background daemon watching pinned files.
3. Heartbeat thread — background daemon emitting run heartbeats.
4. `ApprovalPolicy` multi-sig — optional background thread pool for peer signatures.
5. `AsyncBridge` — bridges async coroutines (LLM SSE streaming) into synchronous calls.

---

## 1. AuditLogger Thread Safety

```
AuditLogger._lock: threading.Lock
```

**Protected under lock:**
- `self.events.append(event)` — in-memory list append
- `path` and `sinks` snapshot for dispatch — snapshot taken inside lock, used outside

**NOT under lock:**
- File write (uses `file_lock` — a separate advisory file-level lock)
- Sink dispatch — intentionally outside lock to prevent holding the lock during
  potentially slow sink calls

**Lock ordering:** `_lock` must never be held while holding `file_lock` (the comment
at `audit.py:252` enforces this). The two locks serve different scopes:

| Lock | Protects | Scope |
|---|---|---|
| `AuditLogger._lock` | in-memory `events` list | process-local |
| `file_lock(path)` | JSONL file writes | file-system (cross-process) |

**Race condition:** Two threads calling `record()` simultaneously will both:
1. Acquire `_lock`, append to `events`, release lock.
2. Independently try to acquire `file_lock`. One wins, the other blocks.
3. The one that wins reads `last_chain_hash`, computes hash, writes, releases lock.
4. The second thread then reads the updated `last_chain_hash` and writes its event.

Result: events may appear out of creation order in the file if the file-lock contention
reorders them relative to the in-memory list. The in-memory `events` list preserves
creation order; the JSONL file order may differ.

---

## 2. TUI REPL — Single-Threaded Run Loop

```
while True:
    raw_command = input()          # blocks
    handle_command(raw_command)    # synchronous, may call _run_agent_task()
```

`_run_agent_task()` is **blocking** — the REPL is frozen while an agent run executes.
There is no async dispatch. Typing during a run is buffered by the terminal but not
processed until `handle_command` returns.

**Implication:** No two agent tasks can run concurrently in a single TUI session.
The TUI's `approved_call_ids` set and `_session_cost_cents` counter are safely
single-threaded and need no locking.

---

## 3. File Watcher Thread

```python
# tui/__init__.py: _start_file_watcher()
self._file_watcher = FileWatcher(root=…, callback=self._on_file_changed, debounce_ms=500)
self._file_watcher.start()     # starts daemon thread
self._watcher_running = True
```

**Concurrency pattern:** The file watcher runs in a daemon background thread.
The callback `_on_file_changed` is called from the watcher thread, but only
modifies `PinnedFileStorage` (file-backed) and calls `output_fn` (print — not
thread-safe in general, but acceptable for console output).

**Race condition:** If the user starts an agent run exactly while a file change event
fires, `output_fn` may interleave output lines between the run's progress output.
This is a cosmetic issue only; no shared mutable state is corrupted.

**Shutdown:** `_stop_file_watcher()` calls `self._file_watcher.stop()` which signals
the thread to exit. The daemon flag means the thread is killed on process exit even
if `stop()` is not called.

---

## 4. Heartbeat Thread

```python
# teaagent/heartbeat.py (inferred from chat_agent.py usage)
Heartbeat(run_id=…, root=…, interval_seconds=…)
```

Started during `run_chat_agent()` if `heartbeat_seconds > 0`. Writes a heartbeat
file to `.teaagent/runs/<run_id>.heartbeat` at the configured interval.

**Concurrency pattern:** Background daemon thread writing to a separate file.
No shared in-memory state; file writes are atomic or close enough (small JSON blobs).
The main run loop reads `heartbeat_for_run()` via the TUI `/status` command, which
reads the file (no lock needed — read is best-effort).

---

## 5. ApprovalPolicy — Multi-Sig Thread Pool

```python
# policy.py:57-68
_signature_executor: concurrent.futures.ThreadPoolExecutor(max_workers=2)
```

Used only when `multi_sig_config.enabled = True`. Collects peer SSH signatures via
federated sync. The `_run_async_signature_collection` method detects whether an event
loop is running and either:
- Uses `run_coroutine_sync(coro, executor=_signature_executor)` if inside a running loop.
- Falls back to `asyncio.run(coro)` otherwise.

This is the only point where a coroutine runs in a separate thread. The result
(list of `PeerSignature`) is returned synchronously to the caller.

---

## 6. AsyncBridge — LLM Streaming

```python
# teaagent/async_bridge.py
run_coroutine_sync(coro, executor, timeout_seconds)
```

The LLM adapters may use `httpx` async streaming. When called from the synchronous
run loop, `async_bridge` submits the coroutine to a `ThreadPoolExecutor` thread that
runs its own event loop. The calling thread blocks on a `Future`.

**Race condition surface:** None — the bridge is purely synchronous from the caller's
perspective. The background thread has its own event loop and does not share state
with the main thread except through the returned `Future` result.

---

## 7. Approval Store File Lock

```python
# policy.py:248-261
@contextmanager
def _flock_store(self) -> Iterator[None]:
    lock_path = store_path.with_suffix('.flock')
    fd = open(lock_path, 'a+')
    fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
    yield
    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
    fd.close()
```

`ApprovalPolicy.assert_allowed()` wraps the inner `_approval_manager.assert_allowed()`
in an exclusive flock. This serializes approval checks across processes (e.g.,
multiple subagent processes sharing the same workspace).

**Lock ordering:** `_flock_store` → `_approval_manager` (in-process). Never held
simultaneously with `AuditLogger._lock`.

---

## 8. Checkpoint Store

`checkpoint_store.save(run_id, context)` is called from:
1. Tool execution success path.
2. Approval pending path.

The `context` dict is written as-is. No lock is held during the write. If two runs
attempted to use the same `run_id` (which cannot happen with UUID-based IDs), there
would be a race. In practice this is safe.

---

## 9. Known Race Conditions

| ID | Location | Scenario | Severity | Mitigated? |
|---|---|---|---|---|
| RC-1 | `AuditLogger` file write ordering | Two threads calling `record()` simultaneously may reorder JSONL lines relative to in-memory list | Low | No — cosmetic only; chain integrity preserved |
| RC-2 | TUI `output_fn` + FileWatcher | File change callback interleaves with run progress output | Low | No — cosmetic only |
| RC-3 | `_session_cost_cents` | Only accessed from the main REPL thread; no concurrency issue | N/A | Enforced by single-threaded REPL |
| RC-4 | `approved_call_ids` set | Mutated only from main REPL thread and `_approval_handler` (called from run, which is synchronous) | N/A | Enforced by single-threaded REPL |
| RC-5 | `UndoJournal._pending` dict | Only accessed within `__call__`, which is called from `AuditLogger.record()` sink dispatch — outside `_lock`, but still single-writer in the REPL context | Low | Single-threaded REPL prevents concurrent access |

---

## 10. Subagent Concurrency

When `subagent=True` in `ChatAgentConfig`, the LLM can invoke a `subagent` tool
which calls `SubagentManager.run_subagent()`. Each subagent runs with its own:
- `AgentRunner` instance (fresh state)
- `AuditLogger` instance (separate JSONL file)
- `UndoJournal` instance

Subagent runs are **synchronous** relative to the parent run — the parent is blocked
waiting for the subagent result. There is no subagent parallelism within a single
parent run. Multiple subagents cannot run concurrently.

The parent run ID is propagated via `bind_parent_run_id` (context var), enabling
subagent approval queues to be linked to the parent.

---

## 11. Parallel Experiment Stack

`ParallelExperimentStack` creates separate git branches via `git checkout -b` (shell
subprocess). Branch operations are sequential (one per option). The branches
themselves are isolated filesystem states, so concurrent `git` operations on
different branches are inherently safe at the git level.

The TUI does not run agent tasks in parallel across branches — users run tasks
manually on each branch in separate TUI invocations or sequentially with `/run`.

---

## 12. Lock Ordering Summary

To prevent deadlocks, always acquire locks in this order when multiple must be held:

```
1. AuditLogger._lock        (in-memory events list)
2. file_lock(audit_path)    (JSONL file append)
3. flock(approval_store)    (approval preset file)
```

These three locks are never currently held simultaneously in the same call stack
(the code is explicit about releasing `_lock` before calling `file_lock`). The
ordering rule exists to prevent future regressions.

---

## 13. Thread-Local Context Vars

`teaagent/tool_call_context.py` and `teaagent/subagent_run_context.py` use
`contextvars.ContextVar` for per-call-stack binding:

- `_tool_call_context_var`: current `ToolCallContext` (audit + run_id + call_id)
- `_parent_run_id_var`: run_id of the parent agent (for subagent attribution)

These are `contextvars` (not `threading.local`), which means they work correctly in
both sync and async contexts and are properly isolated per-task in async code.
In the synchronous REPL these behave identically to `threading.local`.
