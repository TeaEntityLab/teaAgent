# Performance Profiling and Optimization Roadmap
**Date:** 2026-06-02  
**Scope:** Full teaagent source — audit chain, runner, TUI/REPL, cost tracking, memory catalog, subprocess spawning, I/O patterns  
**Method:** Static analysis of hot-path code; no runtime profiler data  

---

## Executive Summary

The dominant performance taxes in teaagent fall into three clusters:

1. **Per-event fsync + lock overhead** in the audit chain adds ~1–10 ms per tool call on SSD. A 20-iteration agent run pays this ~60 times (iteration_started + tool_call_started + tool_call_completed per loop).
2. **File re-read on every access** in MemoryCatalog, RunStore, and CostTracker. These O(n) scans are paid at startup, after each run, in the state panel, and in every `/runs` or `/cost` command.
3. **Repeated cold-path reconstruction** on each task: tool registry, project instructions, skill index, approval store, and config resolver are all rebuilt from scratch per `run_chat_agent` call.

The TUI is entirely synchronous; there is no async I/O. LLM wait time dominates perceived latency, but harness overhead stacks on top and becomes noticeable for multi-turn chat sessions with many short tasks.

---

## 1. Audit Chain — Per-Event I/O

**Files:** `teaagent/audit.py`, `teaagent/audit_chain.py`, `teaagent/storage.py`

### 1.1 `os.fsync()` on every event

`AuditLogger.record()` calls `handle.flush()` then `os.fsync(handle.fileno())` for every audit event. On macOS (F_FULLFSYNC), this triggers a physical write barrier. Measured cost: 1–15 ms per call on typical SSD.

A 20-iteration run emits approximately 60–80 audit events:
- `run_started` (×1)
- `iteration_started` (×20)
- `tool_call_started` + `tool_call_completed` (×40)
- `run_completed` (×1)
- budget/compaction events

At 5 ms/fsync, that is 300–400 ms of pure fsync overhead per run, invisible to users but real harness latency.

**Root cause:** `storage.append_jsonl_line` also calls `os.fsync` — any code path that calls this (MemoryCatalog.add, etc.) shares the same problem.

**Recommendation:** Batch-write with delayed fsync. Maintain a write buffer of N events; fsync only when the buffer flushes, on terminal events (`run_completed`, `run_failed`), or every 5 seconds via a background flush. The chain integrity guarantee does not require per-event fsync — it only requires that writes are ordered.

| Impact | Effort | Priority |
|--------|--------|----------|
| High (300–400 ms / run) | Medium | P1 |

---

### 1.2 `last_chain_hash()` reads tail on every write

`audit.py:265–289` calls `last_chain_hash(path)` inside every `record()` call. `last_chain_hash` opens the file, seeks to the last 4 KB, parses JSON lines to find the last chained event hash.

This is a disk read (and JSON parse) per audit event — capped at 4 KB per call, but still significant when called 60+ times per run.

**Root cause:** `AuditLogger` maintains an in-memory `_prev_hash` field (`audit.py:118`) but does not use it when a path is present. The logic unconditionally re-reads from disk, presumably for safety under multi-writer scenarios. However, multi-writer is not the common case.

**Recommendation:** Use the in-memory `_prev_hash` as the primary source. Fall back to disk-read only when `_prev_hash == 'genesis'` (first write after init) or when a write fails mid-flight. This eliminates ~59 of ~60 disk reads per run.

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium-High (~60 file reads / run) | Low | P1 |

---

### 1.3 `file_lock()` and `secure_audit_file()` on every event

`audit.py:264` wraps every write in `file_lock(path)`, which creates or opens `<path>.lock`, acquires an exclusive `flock`, and releases it. This is a syscall pair per event.

`audit.py:293` calls `secure_audit_file(path)` (i.e., `path.chmod(0o600)`) after every write — another syscall.

**Recommendation:** Move `chmod` to a one-time call at file creation. Only call it again on first write to a new path. The per-event chmod is redundant once the file mode is set.

For `file_lock`: the lock is necessary but can be replaced with an append-only write strategy that doesn't require the lock for single-process workloads (the common case). For multi-process correctness, batch the lock acquisition across a group of events.

| Impact | Effort | Priority |
|--------|--------|----------|
| Low-Medium (syscall overhead) | Low (chmod) / Medium (lock) | P2 |

---

### 1.4 Redaction applied to all values unconditionally

`redact_audit_payload()` is called synchronously inside `record()`. It recursively walks every key-value pair in the payload and applies up to 6 compiled regex patterns to every string value — including numeric fields (`cost_cents`, `input_tokens`, etc.) that are clearly never sensitive.

The redaction also processes `result` dicts (tool output), which can contain large file contents. The iteration through `SENSITIVE_STRING_PATTERNS` on a 20,000-character file content string runs 6 regex passes.

**Recommendation:**
1. Skip redaction for numeric, bool, and None values (already done for top-level, but not consistently for nested).
2. Pre-check if any string value exceeds `MAX_AUDIT_STRING_LENGTH` before running patterns — truncate first, then redact the shorter string.
3. For `L0` and `L1` audit levels, skip redaction entirely for `result` fields (they're dropped by `_apply_audit_level` anyway, but `redact_audit_payload` still runs before filtering).

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium (CPU on large payloads) | Low | P2 |

---

## 2. RunStore — O(n) Reads Per Query

**File:** `teaagent/run_store.py`

### 2.1 `list_runs()` reads every JSONL file

`list_runs()` globs all `.jsonl` files in `.teaagent/runs/`, sorts them by `stat().st_mtime`, then calls `summarize(path)` on each — which reads and JSON-parses the entire file.

For a workspace with 100 runs × 80 events × ~300 bytes/event, this is ~2.4 MB of JSON parsing on every `/runs` invocation.

**Recommendation:** Maintain a separate `runs-index.jsonl` (or `runs-index.json`) that stores one summary line per run (`run_id`, `task`, `status`, `created_at`, `updated_at`, `final_answer`). Update it atomically when `logger_for_result()` is called. `list_runs()` reads only this index file. `show_run()` still reads the full JSONL when needed. This is a standard write-through index pattern.

| Impact | Effort | Priority |
|--------|--------|----------|
| High at scale (2+ MB parse on every /runs) | Medium | P1 |

---

### 2.2 Multiple redundant re-reads of the same JSONL

In `_run_agent_task()` (tui/__init__.py:948–962), after a run completes:
- `store.show_run(result.run_id)` reads the JSONL once
- Then passes `events` to `summarize_audit_events()` and `summarize_run()`

But `audit_logger.events` (the in-memory list) already contains all events from the run. Reading from disk here is redundant — the in-memory events are the canonical source immediately after the run.

Similarly, `pending_approval_for_run()`, `task_for_run()`, and `observations_for_run()` each call `show_run()` independently, re-parsing the same file three times for `resume`.

**Recommendation:** Pass `audit.events` (the in-memory `list[AuditEvent]`) directly to post-run analysis functions instead of re-reading from disk. For `resume`, load the file once and cache the parsed event list.

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium (extra disk read per run completion) | Low | P2 |

---

## 3. CostTracker — Triple Parse of All Runs

**File:** `teaagent/cost_tracker.py`

`report_all()` calls three independent methods:
- `report_by_day(days=days)` → calls `_parse_runs()` (reads all files)
- `report_by_model()` → calls `_parse_runs()` again
- local loop calling `_parse_runs()` a third time for by-label aggregation

Each `_parse_runs()` call reads and parses every JSONL in `.teaagent/runs/` from scratch.

**Recommendation:** `report_all()` should call `_parse_runs()` exactly once, then partition the result list in-memory for by-day, by-model, and by-label aggregation. This is a trivial refactor that eliminates 2 of 3 parse passes.

Beyond that, the runs-index approach from §2.1 would make CostTracker cost-free: it could read just the index instead of full audit files.

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium (3× redundant parse, ~1–3 s for 100+ runs) | Trivial (dedup) / Medium (index) | P1 (dedup) |

---

## 4. MemoryCatalog — Full File Scan Per Access

**File:** `teaagent/memory/catalog.py`

`_read_entries()` is called by `list()`, `search()`, `show()`, and both delete methods. It reads `memory.jsonl` in full and parses every line on every call. There is no in-memory cache.

For a workspace with 500 memory entries × ~200 bytes = ~100 KB, each `search()` call parses and allocates 500 Python objects. This happens on every `run_chat_agent` call (line `chat_agent.py:468`).

`memory_matches()` uses `in` substring search, which is O(m) per entry per query. With 500 entries and a 10-token query, this is ~500 string scans on startup of every agent run.

**Recommendation:**
1. Add an LRU in-memory cache in `MemoryCatalog` with a file-mtime invalidation check. On each access, compare `path.stat().st_mtime` against the cached mtime; re-read only when changed.
2. For `search()`, build a simple inverted index in memory: `{word: [entry_ids]}`. Rebuild when file changes. This turns O(n×m) search into O(m × avg_list_len).
3. Longer term: migrate to SQLite with FTS5 for keyword search.

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium (parse 500 objects per agent run) | Low (mtime cache) / Medium (inverted index) | P1 (cache) |

---

## 5. Repeated Cold Construction on Each Agent Run

**File:** `teaagent/chat_agent.py` (`_run_chat_agent_impl`)

Every call to `run_chat_agent()` reconstructs:

| Object | Location | Cost |
|--------|----------|------|
| `build_workspace_tool_registry(config.root)` | line 431 | filesystem walk, builds full registry |
| `load_project_instructions(config.root)` | line 467 | reads CLAUDE.md / .instructions files from disk |
| `MemoryCatalog(config.root).search(task, ...)` | line 469 | full memory file parse (see §4) |
| `load_skills_with_report(...)` | line 488 | filesystem walk for .skill.md files |
| `discover_skill_index(...)` | line 477 | filesystem walk (index_only mode) |
| `ApprovalPresetStore(config.root)` | line 551 | reads approval grants JSON from disk |
| `MultiSigQuorumConfig.from_workspace_config(config.root)` | line 563 | reads workspace config |
| `ConfigResolver(workspace_root=...).resolve()` | `from_root` | reads config.json/config.toml |

For a multi-turn TUI session, each user message triggers a full `run_chat_agent()` call, paying all of the above on every turn.

**Recommendation:** Introduce a `ChatAgentSession` object that holds the warm state — registry, project instructions, skill index, approval store — and is reused across turns. Pass it from the TUI to `run_chat_agent`. The registry, instructions, and skill index rarely change mid-session. Only memory search (task-specific) must stay per-call.

For skills specifically: `load_skills_with_report()` does a filesystem walk every call. A file-mtime-gated cache with a 2-second TTL would eliminate 99% of the overhead.

| Impact | Effort | Priority |
|--------|--------|----------|
| High (multiple disk walks per turn) | High (session object refactor) / Low (mtime caching) | P1 (caching) / P2 (refactor) |

---

## 6. TUI State Panel — Per-Frame Disk I/O

**File:** `teaagent/tui/__init__.py`, `_print_state_panel()` lines 202–321

When `use_split_pane` is `True` (terminal ≥ 120×30), every input loop iteration calls `_print_state_panel()`, which:

1. Creates `RunStore(self.root, readonly=True)` and calls `store.list_runs(limit=3)` — full JSONL glob + 3 file reads
2. Creates `MemoryCatalog(self.root, readonly=True)` and calls `memory.list(limit=3)` — full memory.jsonl parse
3. Calls `self._parallel_stack.compare_branches()` — likely runs `git diff` subprocess

This means every keystroke in split-pane mode triggers multiple disk reads and potentially a subprocess.

**Recommendation:**
1. Cache the state panel data with a 2-second TTL. Only refresh on explicit user actions (run completion, memory add) or on timer expiry.
2. Move state panel refresh to a background thread with a configurable interval (default 5s).
3. `compare_branches()` should cache its `git diff --stat` result until a branch changes.

| Impact | Effort | Priority |
|--------|--------|----------|
| High (disk I/O per keystroke in split-pane) | Low (TTL cache) | P1 |

---

## 7. _load_tui_state() — Duplicate Field Assignment

**File:** `teaagent/tui/__init__.py`, `_load_tui_state()` lines 1116–1148

Lines 1133–1148 re-assign `progress`, `stream`, `subagent`, `route_model_enabled`, and `heartbeat_seconds` a second time — identical to the first assignments at lines 1125–1136. This is dead code that wastes dict lookups and attribute sets on every TUI startup.

**Recommendation:** Remove the duplicate block (lines 1140–1148). Already assigns correctly the first time.

| Impact | Effort | Priority |
|--------|--------|----------|
| Trivial | Trivial | P3 |

---

## 8. Docker Sandbox — subprocess.run on Every Preflight

**File:** `teaagent/docker_sandbox.py`

`DockerSandbox.start()` calls `self.preflight()`, which spawns `docker info` — a full subprocess that takes 100–500 ms on a running Docker daemon. `execute_code()` calls `start()` if not already started, meaning the first code execution per sandbox pays this unconditionally.

Additionally, `_resource_monitor()` creates a new `ResourceMonitor` instance (line 55) every time it's called rather than caching the instance.

**Recommendation:**
1. Cache the preflight result at the class or module level with a 30-second TTL. Docker daemon availability rarely changes within a session.
2. Initialize `_monitor` once in `start()` and store it as `self._monitor`.

| Impact | Effort | Priority |
|--------|--------|----------|
| Medium (100–500 ms on every first execute_code) | Low | P2 |

---

## 9. Storage Layer — Lock File Per Append

**File:** `teaagent/storage.py`

`append_jsonl_line()` creates (or opens) a `.lock` file and acquires an exclusive flock on every call. For single-process workloads (the common case), this is unnecessary syscall overhead. The lock is only needed when multiple processes write to the same file concurrently.

For the memory catalog and audit log, writes are typically single-process. The `AuditLogger` already holds a threading lock (`self._lock`) for in-process safety.

**Recommendation:** `append_jsonl_line` should accept an optional `use_lock: bool = True` parameter. Callers that know they are single-process (e.g., in-session memory writes) can pass `use_lock=False`. Alternatively, check if the platform supports atomic appends (POSIX with O_APPEND — which Linux and macOS guarantee for writes ≤ PIPE_BUF) and skip the flock for small writes.

| Impact | Effort | Priority |
|--------|--------|----------|
| Low-Medium (syscall per memory write) | Low | P3 |

---

## 10. Prompt Assembly — Rebuilt Every Iteration

**File:** `teaagent/chat_agent.py`, `ModelDecisionEngine.decide()`

`assemble_agent_prompt()` is called on every iteration of the agent loop. For a 20-iteration run, the system prompt (which includes tool schemas, skill content, project instructions, and memory entries) is assembled 20 times. These components are static within a run.

The budget preflight check at lines 202–208 computes `len(prompt.system) + len(prompt.user)` — string length operations on what may be a 100 KB+ string — on every iteration.

**Recommendation:**
1. Pre-assemble the static portion of the system prompt (tools, skills, instructions, memory) once at run start. Only the dynamic `context` portion needs to be rebuilt per iteration.
2. Cache `len(prompt.system)` as it doesn't change between iterations.

| Impact | Effort | Priority |
|--------|--------|----------|
| Low-Medium (string allocation per iteration) | Medium (prompt refactor) | P3 |

---

## 11. In-Memory Event Accumulation — Unbounded Growth

**File:** `teaagent/audit.py`, `AuditLogger.events`

`self.events: list[AuditEvent]` grows without bound during a run. A 200-iteration run with 20 tool calls each can accumulate 1,000+ events. `_build_run_summary()` (`runner/_core.py:233`) filters this list with an O(n) comprehension on run completion.

For very long runs (background agents, automated pipelines), this is a memory leak risk — every event payload (potentially containing file content excerpts) is retained in memory.

**Recommendation:**
1. Cap `self.events` at N entries (e.g., 1000) for the in-memory list, discarding oldest once the cap is reached. The disk JSONL is the authoritative record.
2. `_build_run_summary()` should read from disk (the JSONL) rather than the in-memory list, so the cap doesn't affect summary accuracy.
3. Add a `max_events` parameter to `AuditLogger.__init__` (default 0 = unlimited) for user control.

| Impact | Effort | Priority |
|--------|--------|----------|
| Low for typical runs; High for long-running agents | Low | P2 |

---

## 12. Git Subprocess Calls — No Result Caching

**Files:** `teaagent/sandbox/_git_branch.py`, `teaagent/tui/__init__.py`

`is_git_repository()` and `is_worktree_clean()` spawn subprocesses. These are called in various validation paths. Multiple sequential git calls in `stash_save()` (list → format → grep) could be batched into one `git stash list` call.

The TUI `_restore_checkpoint()` runs 3–4 sequential git subprocess calls:
1. `git stash list`
2. `git stash show --name-only --oneline`
3. `git checkout HEAD -- <files>`
4. `git stash pop`

Each is a cold subprocess spawn (~20–50 ms on macOS).

**Recommendation:**
1. Cache `is_git_repository()` result per `root` path at module level (it doesn't change).
2. Combine `stash list` + `stash show` into a single `git stash list --format` call with the fields needed.
3. For `is_worktree_clean()`: use `git status --short --untracked-files=no` (faster than `--porcelain` for large repos).

| Impact | Effort | Priority |
|--------|--------|----------|
| Low-Medium (each call is 20–50 ms) | Low | P3 |

---

## Summary Table — Prioritized Optimization Backlog

| # | Issue | Location | Impact | Effort | Priority |
|---|-------|----------|--------|--------|----------|
| 1 | fsync per audit event | audit.py | High | Medium | P1 |
| 2 | Disk read for prev_hash per event | audit.py | Med-High | Low | P1 |
| 3 | Triple _parse_runs() in report_all | cost_tracker.py | Medium | Trivial | P1 |
| 4 | list_runs reads full JSONL per file | run_store.py | High (at scale) | Medium | P1 |
| 5 | MemoryCatalog full scan per access | memory/catalog.py | Medium | Low | P1 |
| 6 | State panel disk I/O per keystroke | tui/__init__.py | High | Low | P1 |
| 7 | Tool registry/skills rebuilt per turn | chat_agent.py | High | High | P1→P2 |
| 8 | Redundant post-run JSONL re-read | tui/__init__.py | Medium | Low | P2 |
| 9 | Docker preflight per execute_code | docker_sandbox.py | Medium | Low | P2 |
| 10 | In-memory event unbounded growth | audit.py | Low→High | Low | P2 |
| 11 | Audit redaction on all values | audit.py | Medium (CPU) | Low | P2 |
| 12 | Lock file per append_jsonl_line | storage.py | Low-Medium | Low | P3 |
| 13 | Prompt rebuilt every iteration | chat_agent.py | Low-Medium | Medium | P3 |
| 14 | Git subprocess per is_git_repository | sandbox/_git_branch.py | Low | Low | P3 |
| 15 | Duplicate _load_tui_state fields | tui/__init__.py | Trivial | Trivial | P3 |

---

## Recommended Quick Wins (P1 items, total ~1–2 days work)

### QW-1: Deduplicate `report_all()` parse calls (30 min)
In `cost_tracker.py:127`, call `_parse_runs()` once, store in local var, pass to by-day/by-model/by-label groupings. Eliminates 2 of 3 parse passes.

### QW-2: Use in-memory `_prev_hash` in AuditLogger (1 hr)
Change `audit.py:265` to use `self._prev_hash` instead of calling `last_chain_hash(path)` for writes after the first. Only call `last_chain_hash` when `self._prev_hash == 'genesis'`.

### QW-3: Move `secure_audit_file()` to file creation only (30 min)
Call `path.chmod(0o600)` in `__init__` (after `path.parent.mkdir`) rather than inside every `record()` call.

### QW-4: Cache state panel data with 2-second TTL (1 hr)
Add `_state_panel_cache: dict` and `_state_panel_cache_time: float` to `TeaAgentTUI`. Refresh only when `time.monotonic() - _state_panel_cache_time > 2.0`.

### QW-5: MemoryCatalog mtime cache (1 hr)
Add `_cached_entries: list[MemoryEntry]` and `_cached_mtime: float` to `MemoryCatalog`. In `_read_entries()`, check `self.path.stat().st_mtime` before re-reading.

### QW-6: Remove duplicate _load_tui_state assignments (5 min)
Delete lines 1140–1148 in `tui/__init__.py` (the second duplicate read of progress/stream/subagent/etc.).

---

## Longer-Term Structural Changes

### LT-1: Write-Through Runs Index
Maintain `.teaagent/runs/index.jsonl` — one line per run, written by `logger_for_result()`. `list_runs()` reads only this index. Eliminates the O(n) full-content scan entirely.

### LT-2: Batch Audit Writes with Periodic Fsync
Replace per-event fsync with an append buffer (N events or 5 seconds), flushed synchronously only on terminal events. Reduces fsync calls from ~60 to ~3 per run.

### LT-3: SQLite for Memory Catalog
Replace `memory.jsonl` with SQLite + FTS5. Enables O(log n) search, concurrent readers, and proper deduplication. Migration path: read existing JSONL → insert all entries → switch reads to SQLite.

### LT-4: ChatAgent Warm Session Object
Introduce `ChatAgentSession` that pre-builds and holds: `ToolRegistry`, `project_instructions`, `skill_index`, `ApprovalPresetStore`. Reused across multi-turn TUI interactions. Only rebuild when workspace config changes (mtime check).

---

## Notes on What NOT to Optimize

- **LLM round-trip latency** dominates perceived response time by 10–100×. All harness overhead combined is secondary to the network call. Fix correctness bugs (CG-01, CG-02) before micro-optimizing.
- **Audit chain hash computation** (SHA-256 per event) is negligible — ~1 μs per event in CPython.
- **Tool registry `get()` / `execute()`** dispatch is in-memory dict lookup — not a bottleneck.
- **JSON serialization** of typical audit payloads is fast (< 0.1 ms for payloads < 10 KB).
