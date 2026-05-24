"""Automation context_from chaining — upstream handoff to downstream runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.automations import AutomationSpec, AutomationStore
from teaagent.storage import atomic_write_text


@dataclass(frozen=True)
class AutomationHandoff:
    automation_id: str
    name: str
    last_status: Optional[str]
    summary: str
    log_tail: str
    collector_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'automation_id': self.automation_id,
            'name': self.name,
            'last_status': self.last_status,
            'summary': self.summary,
            'log_tail': self.log_tail,
            'collector_summary': self.collector_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AutomationHandoff:
        return cls(
            automation_id=str(payload.get('automation_id', '')).strip(),
            name=str(payload.get('name', '')).strip(),
            last_status=(
                str(payload.get('last_status')).strip()
                if payload.get('last_status') is not None
                else None
            ),
            summary=str(payload.get('summary', '')).strip(),
            log_tail=str(payload.get('log_tail', '')).strip(),
            collector_summary=str(payload.get('collector_summary', '')).strip(),
        )


def handoff_path(root: str | Path, automation_id: str) -> Path:
    return (
        Path(root).resolve()
        / '.teaagent'
        / 'automation-handoff'
        / f'{automation_id}.json'
    )


def persist_automation_handoff(
    root: str | Path,
    spec: AutomationSpec,
    *,
    collector_summary: str = '',
    log_tail: str = '',
    summary: str = '',
) -> AutomationHandoff:
    handoff = AutomationHandoff(
        automation_id=spec.automation_id,
        name=spec.name,
        last_status=spec.last_status,
        summary=summary.strip()
        or collector_summary.strip()
        or (spec.last_status or ''),
        log_tail=log_tail.strip(),
        collector_summary=collector_summary.strip(),
    )
    path = handoff_path(root, spec.automation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(handoff.to_dict(), sort_keys=True))
    return handoff


def load_automation_handoff(
    root: str | Path, automation_id: str
) -> Optional[AutomationHandoff]:
    path = handoff_path(root, automation_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return AutomationHandoff.from_dict(payload)


def validate_context_from(
    spec: AutomationSpec,
    *,
    root: str,
    store: Optional[AutomationStore] = None,
) -> list[str]:
    upstream_id = spec.context_from.strip()
    if not upstream_id:
        return []
    errors: list[str] = []
    if upstream_id == spec.automation_id:
        errors.append('context_from cannot reference the same automation_id')
        return errors
    automation_store = store or AutomationStore(root)
    try:
        automation_store.show(upstream_id)
    except FileNotFoundError:
        errors.append(f"context_from automation '{upstream_id}' not found")
    return errors


def resolve_chained_task(
    root: str | Path,
    spec: AutomationSpec,
    *,
    collector_summary: str = '',
) -> tuple[str, Optional[AutomationHandoff]]:
    upstream_id = spec.context_from.strip()
    if not upstream_id:
        return spec.task, None
    handoff = load_automation_handoff(root, upstream_id)
    if handoff is None:
        try:
            upstream = AutomationStore(root).show(upstream_id)
        except FileNotFoundError:
            return spec.task, None
        handoff = AutomationHandoff(
            automation_id=upstream.automation_id,
            name=upstream.name,
            last_status=upstream.last_status,
            summary=upstream.last_status or '',
            log_tail='',
            collector_summary='',
        )
    if collector_summary.strip():
        handoff = AutomationHandoff(
            automation_id=handoff.automation_id,
            name=handoff.name,
            last_status=handoff.last_status,
            summary=collector_summary.strip() or handoff.summary,
            log_tail=handoff.log_tail,
            collector_summary=collector_summary.strip(),
        )
    return compose_chained_task(spec.task, handoff), handoff


def compose_chained_task(task: str, handoff: AutomationHandoff) -> str:
    lines = [
        '## Upstream automation context',
        f'- Source automation: {handoff.name} ({handoff.automation_id})',
    ]
    if handoff.last_status:
        lines.append(f'- Last status: {handoff.last_status}')
    if handoff.summary:
        lines.append(f'- Summary: {handoff.summary}')
    if handoff.collector_summary and handoff.collector_summary != handoff.summary:
        lines.append(f'- Collector: {handoff.collector_summary}')
    if handoff.log_tail:
        lines.append('- Recent log tail:')
        lines.append(handoff.log_tail.strip())
    lines.extend(['', '## Task', task.strip()])
    return '\n'.join(lines)


def handoff_preview(handoff: AutomationHandoff, *, max_chars: int = 400) -> str:
    text = compose_chained_task('<task>', handoff)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + '...'
