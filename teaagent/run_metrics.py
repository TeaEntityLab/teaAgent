"""Per-run latency metrics derived from audit events (WS4-001)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median
from typing import Any


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ms_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds() * 1000.0
    return max(delta, 0.0)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


@dataclass
class RunLatencyMetrics:
    llm_latencies_ms: list[float] = field(default_factory=list)
    tool_latencies_ms: list[float] = field(default_factory=list)
    approval_latencies_ms: list[float] = field(default_factory=list)
    audit_write_errors: int = 0

    @property
    def llm_count(self) -> int:
        return len(self.llm_latencies_ms)

    @property
    def tool_count(self) -> int:
        return len(self.tool_latencies_ms)

    @property
    def approval_count(self) -> int:
        return len(self.approval_latencies_ms)

    def llm_p50_ms(self) -> float | None:
        return median(self.llm_latencies_ms) if self.llm_latencies_ms else None

    def tool_p50_ms(self) -> float | None:
        return median(self.tool_latencies_ms) if self.tool_latencies_ms else None

    def approval_p50_ms(self) -> float | None:
        return (
            median(self.approval_latencies_ms) if self.approval_latencies_ms else None
        )

    def tool_p95_ms(self) -> float | None:
        return _percentile(self.tool_latencies_ms, 95.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            'llm': {
                'count': self.llm_count,
                'p50_ms': self.llm_p50_ms(),
            },
            'tool': {
                'count': self.tool_count,
                'p50_ms': self.tool_p50_ms(),
                'p95_ms': self.tool_p95_ms(),
            },
            'approval': {
                'count': self.approval_count,
                'p50_ms': self.approval_p50_ms(),
            },
            'audit_write_errors': self.audit_write_errors,
        }


def summarize_run_latencies(events: list[dict[str, Any]]) -> RunLatencyMetrics:
    """Compute latency samples from paired audit events."""
    metrics = RunLatencyMetrics()
    tool_started: dict[str, datetime] = {}
    approval_pending: dict[str, datetime] = {}
    iteration_started: datetime | None = None

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get('event_type', ''))
        created = _parse_timestamp(event.get('created_at'))
        payload = event.get('payload')
        if not isinstance(payload, dict):
            payload = {}

        if event_type == '_disk_write_error':
            metrics.audit_write_errors += 1
            continue

        if event_type == 'iteration_started':
            iteration_started = created
            continue

        if (
            event_type.startswith('tool_call_')
            and event_type != 'tool_call_started'
            and iteration_started is not None
            and created is not None
        ):
            sample = _ms_between(iteration_started, created)
            if sample is not None:
                metrics.llm_latencies_ms.append(sample)
            iteration_started = None

        if event_type == 'tool_call_started':
            call_id = payload.get('call_id')
            if isinstance(call_id, str) and created is not None:
                tool_started[call_id] = created
            continue

        if event_type in {'tool_call_completed', 'tool_call_failed'}:
            call_id = payload.get('call_id')
            duration = payload.get('duration_ms')
            if isinstance(duration, (int, float)):
                metrics.tool_latencies_ms.append(float(duration))
            elif isinstance(call_id, str) and call_id in tool_started:
                sample = _ms_between(tool_started.pop(call_id), created)
                if sample is not None:
                    metrics.tool_latencies_ms.append(sample)
            continue

        if event_type == 'tool_call_pending_approval':
            call_id = payload.get('call_id')
            if isinstance(call_id, str) and created is not None:
                approval_pending[call_id] = created
            continue

        if event_type in {'tool_call_approved', 'tool_call_denied'}:
            call_id = payload.get('call_id')
            if isinstance(call_id, str) and call_id in approval_pending:
                sample = _ms_between(approval_pending.pop(call_id), created)
                if sample is not None:
                    metrics.approval_latencies_ms.append(sample)

    return metrics


def format_latency_summary(metrics: RunLatencyMetrics) -> str:
    lines = ['Latency metrics:']
    if metrics.llm_count:
        lines.append(
            f'  LLM (iteration→decision): p50={metrics.llm_p50_ms():.0f}ms (n={metrics.llm_count})'
        )
    else:
        lines.append('  LLM: no samples')
    if metrics.tool_count:
        p95 = metrics.tool_p95_ms()
        p95_text = f', p95={p95:.0f}ms' if p95 is not None else ''
        lines.append(
            f'  Tools: p50={metrics.tool_p50_ms():.0f}ms{p95_text} (n={metrics.tool_count})'
        )
    else:
        lines.append('  Tools: no samples')
    if metrics.approval_count:
        lines.append(
            f'  Approvals: p50={metrics.approval_p50_ms():.0f}ms (n={metrics.approval_count})'
        )
    else:
        lines.append('  Approvals: no samples')
    if metrics.audit_write_errors:
        lines.append(f'  Audit write errors: {metrics.audit_write_errors}')
    return '\n'.join(lines)
