"""Human-readable run receipt (WS1-001).

Turns run evidence into an operator-facing receipt suitable for CLI/TUI output.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.audit_health import assess_audit_health, format_audit_health
from teaagent.evidence_summary import RunEvidenceSummary, build_evidence_summary
from teaagent.governance.conversation_ux import plain_run_receipt_summary
from teaagent.run_evidence import RunEvidenceBundle, build_run_evidence_bundle
from teaagent.run_metrics import format_latency_summary, summarize_run_latencies
from teaagent.run_store import RunStore


@dataclass
class RunReceiptContext:
    goal: str = ''
    provider: str = ''
    model: str = ''
    permission_mode: str = ''
    plan_path: str = ''
    plan_content_hash: str = ''
    final_result: str = ''
    audit_path: str = ''
    resume_state: str = 'none'
    tools_used: list[str] = field(default_factory=list)


def _truncate_text(text: str, *, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'


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


def receipt_completeness_checklist(*, include_plan: bool = False) -> tuple[str, ...]:
    """Return required fragments for a minimum complete human run receipt."""
    fragments = (
        'Run receipt:',
        'Goal:',
        'Provider/model:',
        'Permission mode:',
        'Cost:',
        'Audit log:',
        'Resume/checkpoint:',
        'Final result:',
        'Tools used (',
        'Files touched:',
        'Commands run:',
        '[exit ',
        'Approvals:',
        'Rollback/undo:',
    )
    if include_plan:
        return fragments[:4] + ('Plan:', 'Plan hash:') + fragments[4:]
    return fragments


def check_receipt_completeness(
    receipt_text: str, *, include_plan: bool = False
) -> list[str]:
    """Return missing fragments from the human-readable receipt text."""
    return [
        fragment
        for fragment in receipt_completeness_checklist(include_plan=include_plan)
        if fragment not in receipt_text
    ]


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
    permission_mode = ''
    plan_path = ''
    plan_content_hash = ''
    final_result = ''
    for event in events:
        if event.get('event_type') != 'run_started':
            continue
        payload = _safe_payload(event)
        goal = str(payload.get('task', goal) or goal)
        provider = str(payload.get('provider', provider) or provider)
        model = str(payload.get('model', model) or model)
        permission_mode = str(
            payload.get('permission_mode', permission_mode) or permission_mode
        )
        plan_path = str(payload.get('plan_path', plan_path) or plan_path)
        plan_content_hash = str(
            payload.get('plan_content_hash', plan_content_hash) or plan_content_hash
        )

    for event in events:
        if event.get('event_type') != 'run_completed':
            continue
        payload = _safe_payload(event)
        final_result = str(payload.get('answer', final_result) or final_result)

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
        permission_mode=permission_mode,
        plan_path=plan_path,
        plan_content_hash=plan_content_hash,
        final_result=final_result,
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
        plain_run_receipt_summary(status=summary.status, goal=context.goal),
        f'Run receipt: {summary.run_id}',
        f'Status: {summary.status}',
    ]
    if context.goal:
        lines.append(f'Goal: {context.goal}')
    if context.provider or context.model:
        lines.append(
            f'Provider/model: {context.provider or "?"} / {context.model or "?"}'
        )
    lines.append(f'Permission mode: {context.permission_mode or "?"}')
    if context.plan_path:
        lines.append(f'Plan: {context.plan_path}')
    if context.plan_content_hash:
        lines.append(f'Plan hash: {context.plan_content_hash}')
    lines.append(f'Cost: {_format_cost(summary)}')
    lines.append(f'Audit log: {context.audit_path}')
    lines.append(f'Resume/checkpoint: {context.resume_state}')

    if summary.started_at:
        window = summary.started_at
        if summary.finished_at:
            window = f'{summary.started_at} → {summary.finished_at}'
        lines.append(f'Window: {window}')

    if context.final_result:
        lines.append(f'Final result: {_truncate_text(context.final_result)}')

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

    commands_run: list[Any] = []
    if bundle and bundle.commands_run:
        commands_run = list(bundle.commands_run)
    elif summary.commands_run:
        commands_run = list(summary.commands_run)

    if commands_run:
        lines.append('Commands run:')
        for cmd in commands_run[:10]:
            command = getattr(cmd, 'command', '') or (
                cmd.get('command', '') if isinstance(cmd, dict) else ''
            )
            if command:
                exit_code = getattr(cmd, 'exit_code', None)
                if isinstance(cmd, dict):
                    exit_code = cmd.get('exit_code', exit_code)
                suffix = f' [exit {exit_code}]' if exit_code is not None else ''
                lines.append(f'  - {command}{suffix}')

    if summary.tests_executed:
        lines.append(f'Tests run: {summary.tests_executed} tool call(s)')

    if bundle and bundle.tests:
        lines.append('Test results:')
        for test in bundle.tests[:10]:
            lines.append(f'  - {test.test_name}: {test.status}')

    approval_rows: list[dict[str, Any]] = list(summary.approvals)
    if not approval_rows and bundle and bundle.approvals:
        for approval in bundle.approvals:
            decision = (
                'denied'
                if approval.denied
                else 'granted'
                if approval.approved
                else 'pending'
            )
            approval_rows.append(
                {
                    'tool_name': approval.tool_name,
                    'decision': decision,
                    'scope': approval.scope_path,
                }
            )

    if approval_rows:
        lines.append('Approvals:')
        for app in approval_rows[:10]:
            tool = app.get('tool_name', '?')
            decision = app.get('decision', '?')
            scope = app.get('scope', '')
            suffix = f' ({scope})' if scope else ''
            lines.append(f'  - {tool}: {decision}{suffix}')

    if events:
        shadow_events = [
            event
            for event in events
            if event.get('event_type') == 'h4_governance_shadow'
        ]
        if shadow_events:
            lines.append('H4 governance (shadow):')
            for event in shadow_events[:10]:
                payload = _safe_payload(event)
                surface = payload.get('surface', '?')
                allowed = payload.get('allowed', '?')
                mode = payload.get('mode', 'shadow')
                reason = payload.get('reason', '')
                lines.append(f'  - {surface}: allowed={allowed} mode={mode} ({reason})')

    if bundle and bundle.routes:
        route = bundle.routes[-1]
        lines.append(
            'Model route: '
            f'{route.resolved_provider}/{route.resolved_model} '
            f'({route.routing_reason or "no reason recorded"})'
        )

    if summary.rollback_available:
        rollback = (
            'available (partial — shell mutations not reversed)'
            if summary.rollback_shell_partial
            else 'available'
        )
    else:
        rollback = 'not available'
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _record_receipt_event_derived_mismatch(
    store: RunStore,
    run_id: str,
    *,
    event_stream_receipt: str,
    legacy_receipt: str,
) -> None:
    """Best-effort audit warning for ADR32-M2 receipt parity drift."""
    try:
        audit = store.audit_logger(run_id)
        audit.record(
            'receipt_event_derived_mismatch',
            run_id,
            event_stream_receipt_sha256=_sha256_text(event_stream_receipt),
            legacy_receipt_sha256=_sha256_text(legacy_receipt),
        )
    except Exception:
        # Receipt rendering must remain read-only/recoverable even if the warning
        # cannot be persisted (e.g. read-only RunStore). The parity test catches
        # the mismatch; this audit path is only an operator breadcrumb.
        return


def build_run_receipt(
    store: RunStore,
    run_id: str,
    root: str | Path,
    *,
    budget_cap_cents: int | None = None,
    use_event_stream: bool = True,
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
    bundle = build_run_evidence_bundle(
        root,
        run_id,
        use_event_stream=use_event_stream,
        raw_audit_events=events,
    )
    receipt = format_run_receipt(summary, context, bundle=bundle, events=events)
    if use_event_stream:
        legacy_bundle = build_run_evidence_bundle(
            root,
            run_id,
            use_event_stream=False,
            raw_audit_events=events,
        )
        legacy_receipt = format_run_receipt(
            summary, context, bundle=legacy_bundle, events=events
        )
        if legacy_receipt != receipt:
            _record_receipt_event_derived_mismatch(
                store,
                run_id,
                event_stream_receipt=receipt,
                legacy_receipt=legacy_receipt,
            )
    return receipt
