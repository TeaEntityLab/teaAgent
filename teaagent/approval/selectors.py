"""Human-readable pending approval selectors (WS1-002)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from teaagent.ergonomics._approval_grants import APPROVAL_TTL_HOURS
from teaagent.run_store import RunStore


@dataclass(frozen=True)
class PendingApprovalView:
    selector: int
    run_id: str
    task: str
    status: str
    created_at: str
    age_seconds: float | None
    call_id: str
    tool_name: str
    reason: str
    path_summary: str
    risk_class: str
    expires_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_tool_arguments(arguments: dict[str, Any]) -> str:
    path = arguments.get('path')
    if isinstance(path, str) and path.strip():
        return path.strip()
    command = arguments.get('command')
    if isinstance(command, str) and command.strip():
        command_text = ' '.join(command.strip().split())
        if len(command_text) > 80:
            return command_text[:77] + '...'
        return command_text
    keys = sorted(arguments)
    if not keys:
        return '(no arguments)'
    preview = ', '.join(f'{key}={arguments[key]!r}' for key in keys[:3])
    if len(keys) > 3:
        preview += ', ...'
    return preview


def classify_risk_class(
    *,
    tool_name: str,
    annotations: dict[str, Any] | None,
    reason_code: str | None,
) -> str:
    if reason_code:
        return reason_code.replace('_', '-')
    annotations = annotations or {}
    if annotations.get('destructive'):
        return 'destructive'
    if annotations.get('read_only'):
        return 'read-only'
    if 'shell' in tool_name or 'mutate' in tool_name:
        return 'shell-mutate'
    if 'write' in tool_name or 'patch' in tool_name:
        return 'workspace-write'
    return 'standard'


def _parse_event_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _pending_age_seconds(
    created_at: str, *, now: datetime | None = None
) -> float | None:
    created = _parse_event_timestamp(created_at)
    if created is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max((current - created).total_seconds(), 0.0)


def _pending_expires_at(created_at: str) -> str:
    created = _parse_event_timestamp(created_at)
    if created is None:
        return 'open-ended'
    expires = created + timedelta(hours=APPROVAL_TTL_HOURS)
    return expires.replace(microsecond=0).isoformat()


def _pending_detail_from_events(
    store: RunStore,
    run_id: str,
) -> dict[str, Any] | None:
    pending: dict[str, Any] | None = None
    for event in store.show_run(run_id):
        if not isinstance(event, dict):
            continue
        event_type = event.get('event_type')
        payload = event.get('payload')
        if not isinstance(payload, dict):
            payload = {}
        if event_type == 'tool_call_pending_approval':
            call_id = payload.get('call_id')
            tool_name = payload.get('tool_name')
            if not isinstance(call_id, str) or not isinstance(tool_name, str):
                continue
            arguments = payload.get('arguments')
            pending = {
                'call_id': call_id,
                'tool_name': tool_name,
                'arguments': arguments if isinstance(arguments, dict) else {},
                'reason': payload.get('reason'),
                'reason_code': payload.get('reason_code'),
                'annotations': payload.get('annotations'),
                'created_at': event.get('created_at') or event.get('timestamp'),
            }
        elif event_type in {
            'tool_call_approved',
            'tool_call_denied',
            'run_completed',
            'run_failed',
        }:
            if pending and pending.get('call_id') == payload.get('call_id'):
                pending = None
    return pending


def collect_pending_approval_views(
    store: RunStore,
    *,
    limit: int = 20,
) -> list[PendingApprovalView]:
    views: list[PendingApprovalView] = []
    selector = 1
    for summary in store.list_runs(limit=limit):
        pending = _pending_detail_from_events(store, summary.run_id)
        if not pending:
            continue
        arguments = pending.get('arguments')
        if not isinstance(arguments, dict):
            arguments = {}
        reason = pending.get('reason')
        reason_text = (
            reason.strip()
            if isinstance(reason, str) and reason.strip()
            else 'approval required'
        )
        reason_code = pending.get('reason_code')
        reason_code_text = reason_code if isinstance(reason_code, str) else None
        annotations = pending.get('annotations')
        annotation_dict = annotations if isinstance(annotations, dict) else {}
        created_at = pending.get('created_at')
        created_at_text = (
            created_at if isinstance(created_at, str) and created_at else 'unknown'
        )
        views.append(
            PendingApprovalView(
                selector=selector,
                run_id=summary.run_id,
                task=summary.task,
                status=summary.status,
                created_at=created_at_text,
                age_seconds=_pending_age_seconds(created_at_text),
                call_id=str(pending['call_id']),
                tool_name=str(pending['tool_name']),
                reason=reason_text,
                path_summary=summarize_tool_arguments(arguments),
                risk_class=classify_risk_class(
                    tool_name=str(pending['tool_name']),
                    annotations=annotation_dict,
                    reason_code=reason_code_text,
                ),
                expires_at=_pending_expires_at(created_at_text),
            )
        )
        selector += 1
    return views


def resolve_selector(
    views: list[PendingApprovalView],
    selector: int,
) -> PendingApprovalView | None:
    for view in views:
        if view.selector == selector:
            return view
    return None


def format_pending_approvals(views: list[PendingApprovalView]) -> str:
    if not views:
        return 'No pending destructive tool approvals.'
    lines = [
        f'{len(views)} action(s) need your approval:',
        '',
    ]
    for view in views:
        age = f'{view.age_seconds:.0f}s' if view.age_seconds is not None else 'unknown'
        lines.extend(
            [
                f'{view.selector}. Approve "{view.tool_name}" — {view.path_summary}',
                f'   Task: {view.task}',
                f'   Why: {view.reason}',
                f'   Risk: {view.risk_class} · age {age} · expires {view.expires_at}',
                f'   → teaagent approval approve --selector {view.selector}',
                f'   (advanced call_id: {view.call_id})',
                '',
            ]
        )
    return '\n'.join(lines).rstrip()


def pending_approvals_payload(views: list[PendingApprovalView]) -> dict[str, Any]:
    return {
        'queue_depth': len(views),
        'pending': [view.to_dict() for view in views],
    }
