"""Working example: custom metrics, audit events, and telemetry.

Demonstrates:
- InMemoryMetricsSink for unit-test-style metric assertions
- Custom audit event emission
- CostTracker for post-run cost aggregation
- OTel wiring stub (no real endpoint needed)

Run without API keys:

    python3 docs/guides/examples/metrics_telemetry.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from teaagent.cost_tracker import CostTracker
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.telemetry import InMemoryMetricsSink
from teaagent.types import AuditEvent, AuditLogger, PermissionMode, RunBudget
from teaagent.workspace_tools import build_workspace_tool_registry

# ── 1. Custom metric counter via InMemoryMetricsSink ──────────────────────────


def demo_metrics(workspace: Path) -> None:
    print('=== Custom Metrics ===')

    metrics = InMemoryMetricsSink()

    # The metrics sink handles audit events; increment counters by emitting events
    audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')
    audit.add_sink(metrics.handle_event)

    # Emit a custom event
    audit.log(
        AuditEvent(
            event_type='custom_metric',
            run_id='demo-run-001',
            payload={
                'metric': 'pages_indexed',
                'value': 42,
                'labels': {'source': 'docs'},
            },
        )
    )

    audit.log(
        AuditEvent(
            event_type='run_completed',
            run_id='demo-run-001',
            payload={
                'status': 'completed',
                'cost_cents': 3.14,
                'input_tokens': 1200,
                'output_tokens': 300,
                'label': 'demo-task',
            },
        )
    )

    snap = metrics.snapshot()
    print(f'  counters: {dict(snap.counters)}')
    print(f'  events recorded: {len(snap.events)}')


# ── 2. Full run with audit + cost tracking ────────────────────────────────────


def demo_cost_tracking(workspace: Path) -> None:
    print('\n=== Cost Tracking ===')

    metrics = InMemoryMetricsSink()
    audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')
    audit.add_sink(metrics.handle_event)

    registry = build_workspace_tool_registry(workspace)
    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    budget = RunBudget(max_iterations=3, max_tool_calls=2)

    step = [0]

    def decide(context):
        step[0] += 1
        if step[0] == 1:
            return ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'out.txt', 'content': 'hello'},
            )
        return FinalAnswer(content='done')

    runner = AgentRunner(
        registry=registry, audit=audit, budget=budget, approval_policy=policy
    )
    result = runner.run(task='write a file', decide=decide)
    print(f'  run_id:  {result.run_id}')
    print(f'  status:  {result.status}')
    print(f'  cost:    {result.cost_cents:.2f}c')

    # Aggregate via CostTracker (reads JSONL from .teaagent/runs/)
    tracker = CostTracker(root=workspace)
    summary = tracker.summary()
    print(f'  tracker total runs:  {summary.get("total_runs", 0)}')


# ── 3. Emit custom structured audit events ────────────────────────────────────


def demo_custom_audit(workspace: Path) -> None:
    print('\n=== Custom Audit Events ===')

    audit = AuditLogger(path=workspace / '.teaagent' / 'custom_audit.jsonl')

    # Emit domain events alongside standard run events
    for page in ['index.md', 'guide.md', 'api.md']:
        audit.log(
            AuditEvent(
                event_type='doc_page_indexed',
                run_id='indexer-run-001',
                payload={'page': page, 'words': 500 + len(page) * 10},
            )
        )

    # Read back and display
    log_path = workspace / '.teaagent' / 'custom_audit.jsonl'
    if log_path.exists():
        events = [
            json.loads(line) for line in log_path.read_text().splitlines() if line
        ]
        print(f'  logged {len(events)} custom events')
        for evt in events:
            print(f'    {evt["event_type"]:30s}  page={evt["payload"].get("page")}')


# ── 4. OpenTelemetry wiring (stub — no real endpoint needed) ──────────────────


def demo_otel_stub() -> None:
    print('\n=== OpenTelemetry (stub) ===')
    try:
        from teaagent.telemetry import TelemetryConfig, configure_telemetry

        # In production: replace endpoint with your OTLP collector URL
        configure_telemetry(
            TelemetryConfig(
                service_name='teaagent-demo',
                otlp_endpoint='http://localhost:4317',  # no-op if collector not running
            )
        )
        print('  OTel configured (no-op if collector not running)')
    except Exception as exc:
        print(f'  OTel not available: {exc}')


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)

        demo_metrics(workspace)
        demo_cost_tracking(workspace)
        demo_custom_audit(workspace)
        demo_otel_stub()

    print('\nAll metrics/telemetry demos complete.')


if __name__ == '__main__':
    main()
