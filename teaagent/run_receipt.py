"""Human-readable run receipt (WS1-001).

Turns run evidence into an operator-facing receipt suitable for CLI/TUI output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.audit_health import assess_audit_health, format_audit_health
from teaagent.evidence_summary import RunEvidenceSummary, build_evidence_summary
from teaagent.run_evidence import RunEvidenceBundle, build_run_evidence_bundle
from teaagent.run_metrics import format_latency_summary, summarize_run_latencies
from teaagent.run_store import RunStore


@dataclass
class RunReceiptContext:
    goal: str = ''
    provider: str = ''
    model: str = ''
    audit_path: str = ''
    resume_state: str = 'none'
    tools_used: list[str] = field(default_factory=list)


def _safe_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get('payload')
    return payload if isinstance(payload, dict) else {}


def _collect_tools_used(events: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for event in events:
        if event.get('event_type') not in (
            'tool_call_started',
            'tool_call_completed',
            'tool_use',
        ):
            continue
        payload = _safe_payload(event)
        tool_name = str(payload.get('tool_name', '')).strip()
        if tool_name and tool_name not in tools:
            tools.append(tool_name)
    return tools


def _derive_resume_state(
    events: list[dict[str, Any]],
    *,
    summary: RunEvidenceSummary,
) -> str:
    event_types = {str(event.get('event_type', '')) for event in events}
    if summary.status == 'pending_approval' or 'run_paused' in event_types:
        return 'checkpointed_suspension'
    if 'run_suspended' in event_types or 'suspension_created' in event_types:
        return 'resumable_session'
    if summary.rollback_available:
        return 'checkpoint_available'
    return 'none'


def extract_run_receipt_context(
    events: list[dict[str, Any]],
    *,
    run_id: str,
    root: str | Path,
    store: RunStore,
) -> RunReceiptContext:
    goal = ''
    provider = ''
    model = ''
    for event in events:
        if event.get('event_type') != 'run_started':
            continue
        payload = _safe_payload(event)
        goal = str(payload.get('task', goal) or goal)
        provider = str(payload.get('provider', provider) or provider)
        model = str(payload.get('model', model) or model)

    for event in events:
        if event.get('event_type') != 'model_route':
            continue
        payload = _safe_payload(event)
        if not provider:
            provider = str(
                payload.get('resolved_provider', '')
                or payload.get('requested_provider', '')
            )
        if not model:
            model = str(
                payload.get('resolved_model', '') or payload.get('requested_model', '')
            )

    audit_path = str(store.run_path(run_id))

    return RunReceiptContext(
        goal=goal,
        provider=provider,
        model=model,
        audit_path=audit_path,
        resume_state='none',
        tools_used=_collect_tools_used(events),
    )


def _format_cost(summary: RunEvidenceSummary) -> str:
    if summary.cost_state == 'unlimited':
        cap = 'unlimited'
    elif summary.budget_cap_cents is None:
        cap = 'not set'
    else:
        cap = f'{summary.budget_cap_cents} cents'
    return f'{summary.total_cost_cents} cents ({summary.cost_state}); budget cap: {cap}'


def format_run_receipt(  # noqa: C901
    summary: RunEvidenceSummary,
    context: RunReceiptContext,
    *,
    bundle: RunEvidenceBundle | None = None,
    events: list[dict[str, Any]] | None = None,
) -> str:
    """Render a human-readable run receipt."""
    lines = [
        f'Run receipt: {summary.run_id}',
        f'Status: {summary.status}',
    ]
    if context.goal:
        lines.append(f'Goal: {context.goal}')
    if context.provider or context.model:
        lines.append(
            f'Provider/model: {context.provider or "?"} / {context.model or "?"}'
        )
    lines.append(f'Cost: {_format_cost(summary)}')
    lines.append(f'Audit log: {context.audit_path}')
    lines.append(f'Resume/checkpoint: {context.resume_state}')

    if summary.started_at:
        window = summary.started_at
        if summary.finished_at:
            window = f'{summary.started_at} → {summary.finished_at}'
        lines.append(f'Window: {window}')

    if context.tools_used:
        lines.append(
            f'Tools used ({len(context.tools_used)}): {", ".join(context.tools_used)}'
        )
    elif bundle and bundle.commands_run:
        tool_names = sorted(
            {cmd.tool_name for cmd in bundle.commands_run if cmd.tool_name}
        )
        if tool_names:
            lines.append(f'Tools used ({len(tool_names)}): {", ".join(tool_names)}')

    if summary.changed_files:
        lines.append('Files touched:')
        lines.extend(f'  - {path}' for path in summary.changed_files[:20])
        if len(summary.changed_files) > 20:
            lines.append(f'  ... and {len(summary.changed_files) - 20} more')

    if summary.commands_run:
        lines.append('Commands run:')
        for cmd in summary.commands_run[:10]:
            command = cmd.get('command', '')
            if command:
                lines.append(f'  - {command}')

    if summary.tests_executed:
        lines.append(f'Tests run: {summary.tests_executed} tool call(s)')

    if bundle and bundle.tests:
        lines.append('Test results:')
        for test in bundle.tests[:10]:
            lines.append(f'  - {test.test_name}: {test.status}')

    if summary.approvals:
        lines.append('Approvals:')
        for approval in summary.approvals[:10]:
            tool = approval.get('tool_name', '?')
            decision = approval.get('decision', '?')
            scope = approval.get('scope', '')
            suffix = f' ({scope})' if scope else ''
            lines.append(f'  - {tool}: {decision}{suffix}')

    if bundle and bundle.routes:
        route = bundle.routes[-1]
        lines.append(
            'Model route: '
            f'{route.resolved_provider}/{route.resolved_model} '
            f'({route.routing_reason or "no reason recorded"})'
        )

    rollback = 'available' if summary.rollback_available else 'not available'
    lines.append(f'Rollback/undo: {rollback}')

    metrics = summarize_run_latencies(events or [])
    lines.append(format_latency_summary(metrics))

    audit_path = Path(context.audit_path) if context.audit_path else None
    health = assess_audit_health(events or [], log_path=audit_path)
    lines.append(format_audit_health(health))

    if bundle and bundle.known_gaps:
        lines.append('Known gaps:')
        for gap in bundle.known_gaps[:5]:
            lines.append(f'  - [{gap.category}] {gap.description}')

    return '\n'.join(lines)


def build_run_receipt(
    store: RunStore,
    run_id: str,
    root: str | Path,
    *,
    budget_cap_cents: int | None = None,
) -> str:
    """Build a formatted run receipt for *run_id*."""
    try:
        events = store.show_run(run_id)
    except FileNotFoundError:
        return f'Run receipt: {run_id}\nStatus: not found'

    summary = build_evidence_summary(
        store,
        run_id,
        root,
        budget_cap_cents=budget_cap_cents,
    )
    context = extract_run_receipt_context(events, run_id=run_id, root=root, store=store)
    context.resume_state = _derive_resume_state(events, summary=summary)
    bundle = build_run_evidence_bundle(root, run_id)
    return format_run_receipt(summary, context, bundle=bundle, events=events)
