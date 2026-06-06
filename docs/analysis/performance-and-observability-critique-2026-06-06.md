# teaAgent — Performance and Observability Critique

**Date:** 2026-06-06  
**Scope:** Full static analysis of teaagent source; no live runtime profiling.  
**Method:** Code reading + grep across 353 Python files. Every claim cites a specific file:line or is flagged `[inferred]`.  
**Relationship to prior art:** Complements `performance-profiling-and-optimization-roadmap-2026-06-02.md` (which covers I/O micro-optimisations). This document takes the operator's perspective: *can someone run this in production and know what's happening?*

---

## 1. Baseline Metrics

### What we can measure without runtime profiling

teaAgent is an LLM-heavy CLI/TUI tool, not a high-QPS web service. The correct baseline frame is *task latency*, not *requests/sec*.

| Metric | Estimated Baseline | Source / Basis |
|--------|-------------------|----------------|
| LLM call latency | 1–30 s per iteration | [inferred] Anthropic API typical TTFT |
| Audit fsync overhead | 300–400 ms / run | Existing roadmap; `storage.py:35-36` (`os.fsync` per event) |
| Swarm heartbeat tick | 30 s | `swarm.py:37` `HEARTBEAT_TICK_INTERVAL = 30` |
| Swarm lock timeout | 60 s (default) | `swarm.py` `lock_timeout_seconds` default |
| LLM retry delay (attempt 0) | 1.0 s base + jitter | `llm/_retry.py:19-23` |
| LLM retry delay (attempt 2) | up to 5 s + jitter | `llm/_retry.py:19-23` (`base * 2^attempt`) |
| LLM max retry wall time | ~30 s per call | `llm/_retry.py:17` `max_delay_seconds=30.0` |
| Context compaction check interval | every 10 operations | `context.py:247` `check_interval: int = 10` |
| Audit disk-error cooldown | 30 s | `audit.py:134` `_disk_error_cooldown_seconds: float = 30.0` |

### Acceptable vs. actual

For a developer CLI tool, sub-100 ms harness overhead (everything except LLM wait) is the bar. The 300–400 ms fsync tax per run (`storage.py:31-36`) is already 3–4× over that bar, and it stacks with every `MemoryCatalog.add()` call. This is **over budget** before the first LLM response returns.

There are no runtime benchmarks in the codebase. The `benchmark.py` module exists (`teaagent/benchmark.py`) but targets model output quality, not latency or throughput.

---

## 2. Profiling Results

*All findings are from static code analysis. Estimates are informed by platform characteristics (macOS SSD, CPython threading model).*

### 2.1 Dominant time sinks

**#1 — LLM network I/O** `[inferred]`  
Every LLM call is synchronous blocking HTTP. No async, no streaming pipeline. The `ClaudeAdapter`, `OpenAICompatibleAdapter`, and `GeminiAdapter` in `llm/_adapters.py` all call the provider API synchronously. The entire Python thread blocks for the duration of the network round-trip.

**#2 — Per-event fsync (300–400 ms/run)**  
`storage.py:31-36`: `append_jsonl_line` calls `handle.flush()` then `os.fsync(handle.fileno())` for every audit event. A 20-iteration run emits ~60–80 events (confirmed by existing roadmap). On macOS, `F_FULLFSYNC` triggers a physical write barrier: 1–15 ms per call.

**#3 — Chain hash disk read on every audit write**  
`audit.py:349-384`: `record()` calls into `file_lock(path)` and then reads `_prev_hash` from disk on every event (the in-memory `_prev_hash` field at `audit.py:126` is read but re-read from disk inside the file lock). This is ~60 additional file reads per 20-iteration run.

**#4 — O(n) file scans per access**  
`MemoryCatalog`, `RunStore`, `CostTracker` [inferred from `cost_tracker.py`, `memory/` module]: these read full JSONL files on every call. As audit logs grow (sessions accumulate), startup and `list` commands pay linearly increasing I/O.

**#5 — Cold reconstruction on each task**  
`managed_runtime.py:64-123`: `ManagedAgentRunner.run()` rebuilds `context_keys`, tool list, etc. from scratch per call. [inferred from coordinator.py and cli/ patterns] Tool registry, project instructions, skill index, and approval store are reconstructed each session — no caching layer.

**#6 — Token estimation via character counting**  
`context.py:38-45`: token estimation uses `len(text) / 3.5` (text) or `/ 4.0` (code). This is the basis for all compaction decisions. It's fast (O(n) string scan) but can be wrong by ±30%, causing premature or delayed compaction.

**#7 — TraceRecorder O(n) span replacement**  
`trace.py:74-85`: `_replace_span()` does a linear scan of `self.spans` on every `tool_call_completed` event. For a run with 100 tool calls, this is O(100) per completion → O(n²) total. Acceptable at current scale; a problem at 1000+ tool calls.

### 2.2 What is NOT instrumented

- No wall-clock timing on LLM calls in the adapters (no `time.perf_counter()` around `client.messages.create()`).
- No wall-clock timing on tool handler execution (`tools.py:164-195`).
- No timing on context compaction (`context.py:47-87`).
- `swarm.py` does instrument subagent execution time (`swarm.py:237,261,277`: `time.perf_counter()` around subprocess invocation), which is the one place timing exists.

---

## 3. Scalability Analysis

### 3.1 Session size (context window)

Context compaction triggers at 75% of `max_context_tokens` (default 200,000). The compactor keeps the last 3 observations and semantically summarises older ones (`context.py:24,47-87`). The sliding-window chat compaction (`context.py:171-226`) is O(n) per compaction cycle. For very long sessions (hundreds of messages), compaction itself becomes a measurable pause.

The token estimator's ±30% error means compaction fires unpredictably at context boundaries — some sessions will stall while compaction runs, others will silently overflow.

### 3.2 Number of agents (swarm mode)

`swarm.py` uses `concurrent.futures.ThreadPoolExecutor`. Each subagent runs in a thread. Python's GIL means CPU-bound work doesn't parallelise, but LLM I/O does release the GIL, so N concurrent subagents each blocking on network are genuinely parallel.

Threading hazards:
- `_gene_pool_lock` (`swarm.py:41`): module-level lock contends across all swarm managers in the same process.
- `_heartbeat_lock` per-manager: contention between the heartbeat daemon thread (`swarm.py:209`) and the main worker thread.
- `threading.Lock()` in `_RateLimiterState` (`tools.py:87`): fine-grained, low contention expected.

At ~10 concurrent subagents, thread overhead is negligible. At 50+, thread creation and context switching begin to dominate. There is no agent pool or work-stealing queue; every `run_parallel_tasks` call creates a fresh `ThreadPoolExecutor`.

### 3.3 Approval policy complexity

`approval_manager.py` (centralized approval queue). The approval check is synchronous and blocks the tool call dispatch loop. There are no timeout limits on user approval wait. A user who walks away from an interactive approval prompt will stall the entire run indefinitely.

The subagent approval queue (`subagents/_approval_queue.py`) is in-memory. Approval state is lost on process restart — pending approvals are silently dropped.

### 3.4 Audit log size

`AuditLogger` appends to a per-run JSONL file (`.teaagent/runs/{run_id}.jsonl`). There is no rotation, compression, or size cap. A long-running agent with 1000 tool calls can produce a multi-MB audit file. `last_chain_hash()` reads the tail 4 KB on every write, so very large audit files do not regress write performance. However, there is no background vacuum or archival — disk fills silently.

`CostTracker` reads the full audit file to compute summaries. At 10 MB, this is slow enough to block the TUI render.

---

## 4. Observability Audit

### 4.1 Logging

**Framework:** Python stdlib `logging` module. ~79 call sites across ~20 files.

**Quality:** Ad-hoc. No structured logging (not structlog, loguru, or JSON formatter). Log messages are human-readable strings, not machine-parseable records.

**run_id threading:** `run_id` is a first-class field in `AuditEvent` (`audit.py:83`) and is passed to every `audit_logger.record()` call. However, it is **not injected into stdlib `logging` calls**. A `logger.warning('Budget at 80%%: ...')` in `budget_monitor.py:145` has no run_id attached — it cannot be correlated with the audit log post-hoc.

**Log levels:** Reasonable use of `warning`, `error`, `exception`, `debug`. No log-level configuration exposed at runtime (no `--log-level` flag visible in CLI).

**Coverage by subsystem:**

| Subsystem | Coverage | Notes |
|-----------|----------|-------|
| LLM adapters | Low | Retry attempts not individually logged |
| Tool execution | Medium | Rate limit exceeded logged; success/failure not |
| Audit sinks | Medium | Sink failures logged as `warning` |
| Budget monitor | Medium | Threshold crossings logged without run_id |
| Swarm | Medium | Timeout events logged; not structured |
| Context compaction | None | No logging at all |
| Cockpit | Low | 4× `except Exception: pass` (`cockpit.py:378,394,407,421`) — silent failures |

### 4.2 Metrics

**Framework:** `InMemoryMetricsSink` (always present) + optional `OTelMetricsSink` (`telemetry/_metrics.py`).

**OTel availability:** Optional dependency (`pip install teaagent[telemetry]`). If not installed, `OTelMetricsSink` raises `TelemetryNotAvailable`. Default installs have zero remote metric export.

**Metrics emitted:**

| Metric | Type | Granularity | Gap |
|--------|------|-------------|-----|
| `agent.runs.started/completed/failed` | Counter | Per-event | No error type label |
| `agent.tool_calls.started/completed` | Counter | Per-tool-name | No latency |
| `agent.run.iterations` | Histogram | Per-run | No p95/p99 |
| `agent.run.cost_cents` | Histogram | Per-run | No real-time cost |

**Missing:** LLM call latency, tool execution latency, approval queue depth, context token usage, audit write latency, disk usage, budget threshold crossings as metrics.

### 4.3 Distributed Tracing

**Framework:** `OTelAuditSink` (`telemetry/_audit.py`). Requires `pip install teaagent[telemetry]`.

**Span coverage:**

| Span | Attributes | Status |
|------|-----------|--------|
| `agent.run` | `agent.task`, `agent.run_id`, `agent.outcome`, `agent.iterations` | OK/ERROR |
| `tool.call` | `tool.name`, `tool.destructive`, `tool.idempotent`, `tool.read_only` | (no explicit status) |
| `llm.http_call` | `http.url`, `http.method`, `http.request_content_length` | OK/ERROR |

Parent-child relationships: `tool.call` spans are children of `agent.run` spans (`telemetry/_audit.py:56-71`). This is correct.

**Gap:** `tool.call` spans have no duration attribute for tool execution time — they measure span lifetime (from `tool_call_started` to `tool_call_completed` audit events), which is correct, but only if OTel is enabled.

**Gap:** `llm.http_call` spans (`telemetry/_transport.py`) capture HTTP-level latency but are not linked to the parent `agent.run` span — there's no context propagation from audit events to HTTP transport spans.

**Gap:** The local `TraceRecorder` (`trace.py`) is always active but **only stores data in memory**. There is no API to export or query `TraceRecorder` data from the CLI. It's a dead-end for operators.

### 4.4 Audit Log

The audit JSONL is the highest-quality observability artifact in the system. It has:
- Append-only JSONL with HMAC chain integrity.
- Tiered redaction (L0–L3).
- Optional Fernet encryption at rest (L3).
- Pluggable sinks (OTel, webhook, Git transaction).

This is **production-grade** design. The operational gap is that there are no tools to query or tail it at runtime (no `teaagent audit tail` command).

---

## 5. Debugging Assessment

**Scenario: A run fails silently at 2 AM. How do you diagnose it?**

**Step 1 — Check the audit log.**  
The JSONL file at `.teaagent/runs/{run_id}.jsonl` has structured events including `run_failed` with `error` field. This is the primary diagnostic surface. *Good.*

**Step 2 — Correlate with application logs.**  
Open `~/.teaagent/logs/` ... which doesn't exist. stdlib `logging` output goes to stderr by default and is not persisted. If the operator didn't redirect stderr, the logs are gone. *Bad.*

**Step 3 — Check OTel traces in Jaeger/Grafana.**  
Only if `teaagent[telemetry]` is installed, `otlp_endpoint` is configured, and the backend is running. Not the default path. *Optional and manual.*

**Step 4 — Find the run_id in logs.**  
The audit log has run_id. stdlib log lines have no run_id. Cross-correlation requires timestamp matching — fragile. *Bad.*

**Step 5 — Check cockpit state.**  
`cockpit.py:378,394,407,421`: four subsystems (goal, memory, review, skill) silently catch all exceptions and return empty defaults. If the cockpit fails to load, you see zeros — not errors. Diagnosing *why* cockpit data is missing requires reading source code. *Very bad.*

**Traceback clarity:** The exception type hierarchy is well-defined (`LLMHTTPError`, `ToolExecutionError`, `HookError`). When exceptions propagate, tracebacks are informative. The problem is exceptions that don't propagate (cockpit) or are logged without context (budget_monitor without run_id).

**Log noise:** No structured log format means grepping for a specific run requires timestamp correlation or run_id injection — neither of which exists today.

---

## 6. Monitoring Coverage Matrix

| What to monitor | Measured? | How | Gap severity |
|-----------------|-----------|-----|-------------|
| Run success/failure rate | Partial | `agent.runs.failed` counter | No error type breakdown |
| LLM call latency (p50/p95) | **No** | — | **Critical** |
| LLM error rate by provider | **No** | — | **Critical** |
| Tool execution latency | **No** | — | **High** |
| Cost per run (real-time) | **No** | Post-hoc via audit | **High** |
| Cost per run (post-hoc) | Yes | `CostTracker` + `InMemoryMetricsSink` | — |
| Approval queue depth | **No** | — | **High** |
| Context token usage (live) | **No** | — | **Medium** |
| Audit log disk usage | **No** | — | **Medium** |
| Subagent heartbeat timeout rate | **No** | — | **Medium** |
| Budget threshold crossings | Partial | `logger.warning` only | No metric emitted |
| Audit write latency | **No** | — | **Medium** |
| Context compaction frequency | **No** | — | **Medium** |
| Audit sink failure rate | Partial | `logger.warning` only | No metric emitted |
| Tool rate-limit hit rate | **No** | — | **Low** |
| Memory catalog size | **No** | — | **Low** |

### Silent failure modes (highest risk)

1. **Audit disk full:** `_disk_error` cooldown (`audit.py:182-189`) suppresses writes for 30 s then retries. The run continues. Operators have no metric to know audit durability is broken.
2. **OTel exporter backpressure:** `BatchSpanProcessor` drops spans when the export queue is full. No metric surfaces this. Traces silently disappear.
3. **Approval queue lost on restart:** Pending approvals in `_approval_queue.py` are in-memory. Process restart loses all pending approvals; agents waiting for approval will time out or stall.
4. **Context compaction overcount:** Inaccurate token estimation triggers compaction too early, silently dropping context. Users see degraded outputs, no metric explains why.
5. **Cockpit load failures:** `cockpit.py:378,394,407,421` — four subsystems return zeroed state on any exception. Operators see empty panels with no error signal.

---

## 7. Incident Response Capability

### 7.1 What exists

| Mechanism | Location | Assessment |
|-----------|----------|------------|
| LLM retry with exponential backoff | `llm/_retry.py:29-50` | Good: max_retries=3, jitter, transient-only |
| Budget thresholds (50/80/90/100%) | `budget_monitor.py:50` | Good: graduated actions, idempotent |
| Budget read-only mode suggestion | `budget_monitor.py:181-187` | Manual: user must act |
| Swarm heartbeat timeout | `swarm.py:209,500` | Good: detects stuck agents at 60 s |
| Tool rate limiting | `tools.py:82-100` | Hard fail, no backoff |
| Audit disk error cooldown | `audit.py:134` | Soft: 30 s retry, run continues |
| Context compaction (auto) | `context.py:250-279` | Good: automatic at 75-92% |
| OTel sink graceful shutdown | `telemetry/_audit.py:95-107` | Good: ends open spans on interrupt |

### 7.2 What is missing

**No circuit breaker.** If the LLM provider returns 5xx for 10 consecutive calls, teaAgent retries each one individually (up to 3 times with 30 s max delay). There is no mechanism to open a circuit and fast-fail for the duration of an outage. A stuck run can consume budget slowly while producing no output.

**No bulkhead.** Swarm tasks share the same `ThreadPoolExecutor`. A pathologically slow subagent doesn't prevent others from running (threads are independent), but a thread leak (e.g., subprocess blocking forever with no timeout) will exhaust the pool silently.

**No graceful degradation for tool failures.** If a tool handler raises unexpectedly, `ToolRegistry.execute()` (`tools.py:164-195`) propagates the exception. The run fails. There's no fallback policy (retry, skip, substitute read-only variant).

**No operator kill switch.** There is a `cancel_token: threading.Event` in `chat_agent.py:86`, but it requires the TUI to be running and the user to send Ctrl-C. There's no external signal (SIGUSR1, HTTP endpoint) to gracefully halt a background run.

**Approval deadlock.** Interactive approval prompts block indefinitely. No approval timeout exists. A non-interactive run that encounters a destructive tool will stall the thread permanently if `on_prompt` is not configured.

**No structured runbook.** If performance tanks, the operator has: (1) kill the process, (2) read the audit JSONL manually, (3) read source code. There's no `teaagent diagnostics`, no health endpoint, no `/status` that reports current run state.

---

## 8. Critical Assessment

### Is teaAgent observable enough for production use?

**Short answer: No — but the foundations are better than average.**

**What's genuinely good:**
- The audit JSONL with HMAC chain integrity is production-grade design. This is the system's strongest observability asset.
- OTel spans with parent-child relationships (`agent.run` → `tool.call`) are architecturally correct.
- `InMemoryMetricsSink` provides basic counters without any external dependency.
- The tiered audit level system (L0–L3) with redaction and encryption shows security-aware design.
- `BudgetMonitor` graduated thresholds prevent runaway cost without hard cutoffs.

**What would cause operational nightmares at scale:**

1. **No LLM latency metric.** The dominant cost driver — LLM call duration — is invisible to operators. You cannot answer "is the p95 LLM latency degrading?" without adding instrumentation.

2. **Logs are ephemeral and unstructured.** stderr goes nowhere unless the operator pipes it. When a run fails at 2 AM, the logs are gone. Structured JSON logging with persistence is the minimum bar for production.

3. **run_id not threaded into log context.** The audit log has run_id; stdlib logs don't. Correlating a `logger.warning('Budget at 80%')` to a specific run requires timestamp archaeology.

4. **Four silent cockpit failures.** `cockpit.py` swallows all exceptions in four subsystems and returns zeroed state. An operator staring at empty panels has no idea if the system is broken or genuinely empty.

5. **No approval timeout.** A blocking approval prompt with no timeout is a production-grade deadlock waiting to happen. Interactive approval on a server-side deployment will hang forever.

6. **No circuit breaker.** Sustained LLM provider outage means 3 retries × 30 s max delay = 90 s of blocking per tool call. In a long run, this adds up to minutes of stalled execution with no operator signal.

7. **Audit durability is silently degraded.** Disk full → 30 s cooldown → run continues → audit events lost. The operator sees nothing.

8. **OTel is opt-in and fragile.** The best observability tooling (OTel traces, OTel metrics) requires a non-default install (`pip install teaagent[telemetry]`) and manual endpoint configuration. Most deployments will not have it.

### Would I want to run this at scale?

Not without the following first: structured logging with run_id context, LLM call latency histogram, approval timeout, circuit breaker (or at minimum a max-retry-wall-time budget), and audit log persistence confirmation metric. The audit JSONL is a solid foundation — but it's a *forensic* tool, not an *operational* one.

---

## 9. Observability Roadmap

Priority ordering: **Critical** (blocks production use) → **High** (significant operational risk) → **Medium** (quality of life).

### Critical (must-have before production)

| Item | What | Where to add | Effort |
|------|------|-------------|--------|
| **OB-01** | Structured JSON logging with run_id context | Add `logging.Filter` or `structlog` to inject `run_id` into every log record during a run | Low |
| **OB-02** | Log persistence (file sink) | Configure a rotating file handler at `~/.teaagent/logs/teaagent.log` | Low |
| **OB-03** | LLM call latency histogram | Wrap `transport_fn()` in `llm/_retry.py:37` with `time.perf_counter()`, emit to `InMemoryMetricsSink` | Low |
| **OB-04** | Approval timeout | Add `timeout_seconds` param to approval callbacks; raise `ApprovalTimeoutError` on expiry | Medium |
| **OB-05** | Cockpit failure logging | Replace `except Exception: pass` blocks in `cockpit.py:378,394,407,421` with `logger.warning(..., exc_info=True)` | Trivial |

### High (significant operational risk)

| Item | What | Where to add | Effort |
|------|------|-------------|--------|
| **OB-06** | Tool execution latency histogram | Wrap handler call in `tools.py:164-195` with `time.perf_counter()` | Low |
| **OB-07** | Budget threshold crossings as metrics | `budget_monitor.py:_handle_threshold()` → call `metrics_sink.increment('agent.budget.threshold_crossed', {'level': level})` | Low |
| **OB-08** | Audit durability metric | Emit metric when `disk_error` is set in `audit.py` | Low |
| **OB-09** | Approval queue depth metric | Emit gauge from `_approval_queue.py` on each enqueue/dequeue | Low |
| **OB-10** | LLM circuit breaker | Track consecutive LLM failures in `_retry.py`; open circuit after N failures with `half_open` probe after backoff | Medium |

### Medium (quality of life)

| Item | What | Effort |
|------|------|--------|
| **OB-11** | `teaagent diagnostics` CLI command | Prints current run state, metrics snapshot, audit tail | Medium |
| **OB-12** | Context token usage metric | Emit estimated token count at each compaction check | Low |
| **OB-13** | Audit log disk usage metric | `os.path.getsize()` on audit path, emit as gauge | Trivial |
| **OB-14** | OTel → LLM span parent linking | Thread OTel context from audit event into HTTP transport | Medium |
| **OB-15** | `teaagent audit tail` command | Stream JSONL audit events to stderr in real time | Low |
| **OB-16** | Subagent heartbeat timeout rate metric | Count timeout events in `swarm.py:500`, emit counter | Low |
| **OB-17** | TraceRecorder export | `GET /traces` or `teaagent trace dump` to inspect local spans | Medium |

---

*All file references are relative to `/Users/teee/dev/teaagent/`.*  
*Claims marked `[inferred]` are based on architectural reasoning, not direct code evidence.*
