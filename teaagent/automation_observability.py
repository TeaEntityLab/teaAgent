"""Observability helpers for automation status and dry-run diagnostics."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any, Optional

from teaagent.automation_chain import handoff_preview, load_automation_handoff
from teaagent.automation_ticket import validate_automation_spec
from teaagent.automations import AutomationSpec, AutomationStore
from teaagent.run_store import RunStore
from teaagent.skill_loader import explain_skill_activation


def extract_run_prompt_ledger(
    root: str | Path, run_id: Optional[str]
) -> dict[str, Any]:
    """Summarize skill-load and completion fields from a run audit trail."""
    if not run_id:
        return {}
    try:
        events = RunStore(root).show_run(run_id)
    except FileNotFoundError:
        return {'error': 'run_not_found'}
    ledger: dict[str, Any] = {}
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        if event_type == 'skill_load':
            ledger['skill_load'] = {
                'estimated_skill_tokens': payload.get('estimated_skill_tokens'),
                'selected_skills': payload.get('selected_skills'),
                'skill_prompt_mode': payload.get('skill_prompt_mode'),
                'loaded': payload.get('loaded'),
            }
        elif event_type == 'run_completed':
            ledger['run_completed'] = {
                'cost_cents': payload.get('cost_cents'),
                'input_tokens': payload.get('input_tokens'),
                'output_tokens': payload.get('output_tokens'),
            }
        elif event_type == 'run_failed':
            ledger['run_failed'] = {
                'category': payload.get('category'),
                'message': payload.get('message'),
            }
    return ledger


def build_token_contributors(
    root: str | Path, spec: AutomationSpec
) -> list[dict[str, Any]]:
    """Token contribution per skill the automation would load on its next agent tick."""
    selected = frozenset(spec.selected_skills) if spec.selected_skills else frozenset()
    explain = explain_skill_activation(
        root,
        selected_names=selected if spec.selected_skills else frozenset(),
        skill_prompt_mode='eager',
    )
    rows: list[dict[str, Any]] = []
    for item in explain.loaded:
        rows.append(
            {
                'name': item.name,
                'estimated_tokens': item.estimated_tokens,
                'reason': item.reason,
                'path': str(item.path),
            }
        )
    if not rows and explain.estimated_skill_tokens == 0:
        rows.append(
            {
                'name': '(none)',
                'estimated_tokens': 0,
                'reason': explain.selection_mode,
                'path': '',
            }
        )
    return rows


def automation_blocked_gate_reason(
    root: str | Path, spec: AutomationSpec
) -> Optional[str]:
    """Human-readable reason when the last tick was blocked or capped."""
    status = (spec.last_status or '').strip()
    if status == 'runtime_cap_exceeded':
        return f'background run exceeded max_runtime_seconds={spec.max_runtime_seconds}'
    if status == 'cost_cap_exceeded':
        return f'run exceeded max_cost_cents={spec.max_cost_cents}'
    if status == 'collector_failed':
        return 'collector command exited non-zero'
    if status == 'background_missing':
        return 'background worker record missing'
    ticket = validate_automation_spec(spec, root=str(root))
    if ticket.errors:
        return '; '.join(ticket.errors[:2])
    store = AutomationStore(root)
    with contextlib.suppress(FileNotFoundError):
        store.show_quarantined(spec.automation_id)
        return 'automation is quarantined; promote after review'
    return None


def build_last_output_preview(root: str | Path, spec: AutomationSpec) -> str:
    handoff = load_automation_handoff(root, spec.automation_id)
    if handoff is not None:
        return handoff_preview(handoff)
    return (spec.last_status or '').strip()


def enrich_automation_status_row(
    root: str | Path,
    spec: AutomationSpec,
    *,
    log_tail: str = '',
) -> dict[str, Any]:
    """Build one automation row for ``build_automation_status``."""
    upstream_preview = ''
    if spec.context_from.strip():
        upstream = load_automation_handoff(root, spec.context_from.strip())
        if upstream is not None:
            upstream_preview = handoff_preview(upstream)
    explain = explain_skill_activation(
        root,
        selected_names=(
            frozenset(spec.selected_skills) if spec.selected_skills else frozenset()
        ),
        skill_prompt_mode='eager',
    )
    return {
        'automation_id': spec.automation_id,
        'name': spec.name,
        'enabled': spec.enabled,
        'next_run_at': spec.next_run_at,
        'last_status': spec.last_status,
        'last_run_id': spec.last_run_id,
        'running_background_id': spec.running_background_id,
        'collector_command': spec.collector_command,
        'no_agent': spec.no_agent,
        'selected_skills': list(spec.selected_skills),
        'delivery': spec.delivery,
        'context_from': spec.context_from,
        'requires_subagent': spec.requires_subagent,
        'max_cost_cents': spec.max_cost_cents,
        'max_runtime_seconds': spec.max_runtime_seconds,
        'log_tail': log_tail,
        'last_output_preview': build_last_output_preview(root, spec),
        'upstream_handoff_preview': upstream_preview,
        'prompt_ledger': extract_run_prompt_ledger(root, spec.last_run_id),
        'token_contributors': build_token_contributors(root, spec),
        'estimated_skill_tokens_next_tick': explain.estimated_skill_tokens,
        'blocked_gate_reason': automation_blocked_gate_reason(root, spec),
    }
