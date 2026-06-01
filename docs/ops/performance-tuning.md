# Performance Tuning

## Baseline Measurements

Before tuning, capture baselines:

```bash
# Measure a representative task end-to-end
time teaagent run "list all Python files in this repo" --max-iterations 3

# Check token usage per run
grep '"usage"' .teaagent/runs/<run_id>.jsonl | python3 -c "
import json, sys
totals = {'input': 0, 'output': 0}
for line in sys.stdin:
    u = json.loads(line).get('usage', {})
    totals['input'] += u.get('input_tokens', 0)
    totals['output'] += u.get('output_tokens', 0)
print(totals)
"
```

---

## Iteration and Tool Call Limits

The most impactful parameters for cost and latency:

| Parameter | Config key | Env var | Default | Effect |
|-----------|-----------|---------|---------|--------|
| Max iterations | `max_iterations` | `TEAAGENT_MAX_ITERATIONS` | 10 | Caps agent loop depth |
| Max tool calls | `max_tool_calls` | `TEAAGENT_MAX_TOOL_CALLS` | 10 | Caps tool calls per iteration |

For simple read-only tasks, reduce both to limit unnecessary loops:

```json
{
  "max_iterations": 5,
  "max_tool_calls": 5
}
```

For complex multi-file refactoring, increase both:

```json
{
  "max_iterations": 30,
  "max_tool_calls": 20
}
```

---

## Model Selection

Model choice dominates both cost and latency:

| Use case | Recommended model | Relative cost |
|----------|-----------------|---------------|
| Simple queries, CI lint checks | `claude-3-5-haiku-latest` or `gpt-4o-mini` | Low |
| Standard coding tasks | `claude-3-5-sonnet-latest` | Medium |
| Complex reasoning, architecture | `claude-opus-4-8` or `gpt-4o` | High |

Configure per-profile:

```json
{
  "profiles": {
    "fast": {
      "provider": "claude",
      "model": "claude-3-5-haiku-latest",
      "max_iterations": 5
    },
    "thorough": {
      "provider": "claude",
      "model": "claude-opus-4-8",
      "max_iterations": 30
    }
  }
}
```

---

## Context Window Management

Large context windows increase latency and cost. Strategies:

### 1. Focused workspace roots

Instead of running from the repo root, point at a subdirectory:

```bash
teaagent run "fix auth tests" --root src/auth/
```

This limits the agent's workspace scan to the relevant subtree.

### 2. Code analysis for targeted reads

Enable tree-sitter code analysis to avoid reading entire files:

```bash
pip install "teaagent[code-analysis]"
```

```json
{
  "code_analysis_enabled": true
}
```

With code analysis enabled, the agent can read only function signatures and class structures rather than full file content.

### 3. Graphqlite for semantic search

Enable graphqlite for vector-based code search instead of file scanning:

```bash
pip install "teaagent[graphqlite]"
```

Build the index once:

```bash
teaagent agent card --rebuild-index
```

The agent then uses semantic search instead of scanning directories, reducing tokens per query.

---

## Local Provider (Zero Latency API Overhead)

For development tasks where API latency dominates:

### Ollama

```bash
# Install and run Ollama locally
brew install ollama  # macOS
ollama pull llama3.2

export TEAAGENT_PROVIDER=ollama
teaagent run "task"
```

Ollama runs at `http://localhost:11434/v1` by default.

### vLLM

```bash
# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --port 8000

export TEAAGENT_PROVIDER=vllm
teaagent run "task"
```

Local providers eliminate network round-trip time but may be slower per token than cloud APIs on small hardware.

---

## Parallel Runs (Multiple Workspaces)

TeaAgent processes are independent. To parallelize across multiple tasks:

```bash
# Run two tasks in parallel on separate workspaces
teaagent run "fix auth" --root /workspace/auth-module &
teaagent run "fix billing" --root /workspace/billing-module &
wait
```

Each process has its own `.teaagent/` state and does not interfere with others.

**Resource contention note:** parallel runs share the same LLM provider rate limits. If hitting 429 errors, stagger starts:

```bash
teaagent run "fix auth" --root /workspace/auth-module &
sleep 5
teaagent run "fix billing" --root /workspace/billing-module &
wait
```

---

## Audit Log Performance

The audit log is append-only JSONL. At very high event rates, disk I/O can become a bottleneck.

### Mitigation

1. **Place `.teaagent/` on a fast disk** (NVMe SSD) — audit writes are synchronous
2. **Prune regularly** to keep file size manageable:

```bash
teaagent audit prune --older-than 30d
```

3. **Ship and prune** — export old events to object storage, then prune locally:

```bash
teaagent audit export --older-than 7d --output s3://bucket/audit-$(date +%Y%m%d).jsonl
teaagent audit prune --older-than 7d
```

---

## Capacity Planning

### Token budget per run

Estimate based on task type:

| Task type | Typical input tokens | Typical output tokens | Estimated cost (Claude Sonnet) |
|-----------|---------------------|----------------------|-------------------------------|
| Simple question | 500–2,000 | 200–500 | < $0.01 |
| Single file edit | 2,000–8,000 | 500–2,000 | $0.01–0.05 |
| Multi-file refactor | 10,000–50,000 | 2,000–10,000 | $0.05–0.50 |
| Large codebase analysis | 50,000–200,000 | 5,000–20,000 | $0.50–5.00 |

### Daily cost budget

Set `TEAAGENT_DAILY_COST_CAP_CENTS` to your expected daily budget with 20% headroom. For a team of 5 developers each running 10 tasks/day at ~$0.10/task:

```
5 × 10 × $0.10 = $5.00/day → set cap to 600 cents ($6.00)
```

### Disk capacity

| Component | Growth rate | 30-day estimate |
|-----------|------------|-----------------|
| Audit log | ~5 KB/event, ~100 events/run | 50 MB per 100 runs |
| Run logs | ~50 KB/run | 5 GB per 100,000 runs |
| Code index (graphqlite) | Depends on repo size | 100 MB–2 GB |

Plan for 5 GB minimum on the `.teaagent/` filesystem, with automated pruning enabled.

---

## Profiling a Slow Run

```bash
# Find slowest tool calls in a run
grep '"latency_ms"' .teaagent/runs/<run_id>.jsonl | \
  python3 -c "
import json, sys
events = [json.loads(l) for l in sys.stdin]
events.sort(key=lambda e: e.get('latency_ms', 0), reverse=True)
for e in events[:10]:
    print(f\"{e.get('latency_ms', 0):>8}ms  {e.get('tool', e.get('type', '?'))} \")
"
```

Common bottlenecks:
- **High LLM latency**: switch to a faster model or a local provider
- **High tool call count**: reduce `max_tool_calls` or enable code analysis
- **Slow file reads on large repos**: enable graphqlite semantic search
- **Approval wait**: use `workspace-write` mode for file-only tasks

---

## See Also

- [Configuration Reference](configuration-reference.md)
- [Monitoring and Alerting](monitoring-and-alerting.md)
- [Operations Manual](operations-manual.md)
