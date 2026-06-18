---
type: guide
audience: operator, developer
status: stable
version: 1.0.0
last_audit: 2026-06-02
---
# Performance Tuning

Configuration knobs and deployment patterns for different environments.

---

## Laptop (Interactive Developer)

**Goal:** Fast iteration, low latency, manageable cost.

```json
// .teaagent/config.json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "permission_mode": "prompt",
  "max_iterations": 15,
  "max_tool_calls": 20,
  "max_estimated_cost_cents": 25,
  "context_compaction": {
    "trigger_pct": 0.80,
    "strategy": "summarise"
  }
}
```

**Key choices:**
- Use a mid-tier model (Sonnet) for daily tasks; reserve Opus for complex one-shots.
- `max_estimated_cost_cents: 25` prevents runaway sessions.
- Context compaction at 80% keeps context usable without truncation.
- `permission_mode: prompt` gives you a review gate without slowing autonomous sub-tasks.

**Warm-up:** Run `teaagent preflight --root .` before long sessions to validate provider health and context pack.

---

## Server (Headless CI / Automation)

**Goal:** High throughput, no interactive prompts, auditable.

```json
{
  "provider": "gpt",
  "model": "gpt-4o-mini",
  "permission_mode": "workspace-write",
  "max_iterations": 50,
  "max_tool_calls": 100,
  "max_estimated_cost_cents": 200,
  "enable_jit_prompt": false,
  "audit_level": "L1",
  "run_parallelism": 4
}
```

**Key choices:**
- `enable_jit_prompt: false` — hard-fail on unapproved tool calls rather than hanging for TTY input.
- `audit_level: L1` — tool-call level logging without full content capture (reduces I/O).
- `run_parallelism` — multiple runs share the tool registry; keep tools stateless and idempotent.
- Pre-approve required tools via `teaagent approval grant` before the CI job starts.

**Concurrency:** `AgentRunner` is thread-safe per-instance. Create one runner per parallel job; do not share runner instances across threads.

```python
from concurrent.futures import ThreadPoolExecutor
from teaagent import AgentRunner, AuditLogger, RunBudget
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.workspace_tools import build_workspace_tool_registry
from pathlib import Path

def make_runner(workspace: Path) -> AgentRunner:
    return AgentRunner(
        registry=build_workspace_tool_registry(workspace),
        audit=AuditLogger(path=workspace / ".teaagent" / "audit.jsonl"),
        budget=RunBudget(max_iterations=50, max_tool_calls=100, max_estimated_cost_cents=200),
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            allow_all_destructive=True,
            enable_jit_prompt=False,
        ),
    )

# Each job gets its own runner and isolated workspace
with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(run_job, workspace=Path(f"/tmp/job-{i}")) for i in range(4)]
```

---

## Cloud / Kubernetes

**Goal:** Horizontal scale, shared audit storage, cost visibility across tenants.

**Architecture:**

```
┌──────────────────────────────────────┐
│  API Gateway / Load Balancer          │
└───────────────┬──────────────────────┘
                │ HTTP
        ┌───────▼────────┐
        │  teaagent       │   × N pods
        │  mcp serve      │
        │  --http         │
        └───────┬────────┘
                │
        ┌───────▼────────┐
        │  Shared audit   │   S3 / GCS / Azure Blob
        │  store (JSONL)  │
        └────────────────┘
```

**Pod config:**
```bash
teaagent mcp serve \
  --http \
  --port 7330 \
  --root /workspace \
  --audit-sink s3://my-bucket/teaagent-audit/ \
  --permission-mode workspace-write
```

**Cost control per tenant:**

```python
from teaagent.budget import RunBudget
from teaagent.control_plane_tenant import TenantConfig

budget = RunBudget(
    max_estimated_cost_cents=int(tenant.monthly_budget_cents / 30),
    max_iterations=100,
)
```

**Audit sink to S3:**

```python
from teaagent.audit import AuditLogger
from teaagent.webhook_sink import WebhookAuditSink

audit = AuditLogger(path=Path("/tmp/audit.jsonl"))
audit.add_sink(WebhookAuditSink(url="https://audit.internal/ingest").handle_event)
```

---

## Edge / Low-Memory

**Goal:** Minimal memory footprint, local models, no cloud dependency.

```json
{
  "provider": "ollama",
  "model": "qwen2.5-coder:7b",
  "permission_mode": "read-only",
  "max_iterations": 8,
  "max_tool_calls": 10,
  "max_estimated_cost_cents": 0,
  "context_compaction": {
    "trigger_pct": 0.70,
    "strategy": "drop_oldest"
  },
  "disable_knowledge_backend": true,
  "disable_hybrid_search": true
}
```

**Key choices:**
- Disable `hybrid_search` and `knowledge_backend` to avoid SQLite/tree-sitter overhead.
- `max_estimated_cost_cents: 0` disables cost pre-flight (local model has no token cost).
- Compact aggressively (`trigger_pct: 0.70`) to stay within small-model context windows.
- `read-only` mode avoids filesystem write overhead on constrained storage.

---

## Context Compaction Tuning

Compaction triggers when token usage reaches `trigger_pct` of the model's context window.

| Strategy | Description | Best for |
|----------|-------------|----------|
| `summarise` | LLM-generated summary of older turns | Long interactive sessions |
| `drop_oldest` | Remove oldest messages until under budget | Edge / low-memory |
| `keep_system` | Drop all but system + last N turns | Read-only queries |

```json
{
  "context_compaction": {
    "trigger_pct": 0.80,
    "strategy": "summarise",
    "keep_last_n": 10
  }
}
```

Acceptance coverage: `tests/test_context_compaction_slo_flow.py`.

---

## Budget Monitor

The `BudgetMonitor` watches cost and iteration counts in a background thread and can
send notifications or trigger graceful shutdown:

```python
from teaagent.budget_monitor import BudgetMonitor
from teaagent.notify import NotifyConfig

monitor = BudgetMonitor(
    budget=budget,
    notify=NotifyConfig(
        slack_webhook="https://hooks.slack.com/...",
        threshold_pct=0.80,   # notify at 80% budget consumed
    ),
)
monitor.start()
# ... run agent ...
monitor.stop()
```

---

## Heartbeat for Long Runs

Enable periodic heartbeat events to detect hung runs:

```python
from teaagent import ChatAgentConfig

config = ChatAgentConfig(
    root=Path("."),
    heartbeat_seconds=30.0,   # emit heartbeat every 30s
)
```

Monitor heartbeats via the audit log or your observability stack.

---

## Tool Call Rate Limiting

Protect external APIs from bursts during autonomous runs:

```python
from teaagent.tools import ToolRateLimit

registry.register(
    name="search_web",
    # ...
    rate_limit=ToolRateLimit(calls_per_minute=20, burst=5),
)
```

The rate limiter is per-registry-instance. In parallel CI scenarios, use
separate registry instances per job (which is the recommended pattern anyway).

---

## Profiling a Run

```bash
teaagent run gpt "task" --root . --profile
# outputs timing breakdown to .teaagent/profiles/
```

Or instrument programmatically:

```python
from teaagent.trace import TraceRecorder

recorder = TraceRecorder()
with recorder.span("agent-run"):
    result = runner.run(task="...", decide=decide)

print(recorder.summary())
```

---

## See Also

- [Cloud deployment](../cloud-deployment.md) — full Kubernetes deployment reference
- [Run evidence and audit guide](../run-evidence-and-audit-guide.md) — audit storage options
- [Cost tracker](../analysis/) — cost aggregation reports
