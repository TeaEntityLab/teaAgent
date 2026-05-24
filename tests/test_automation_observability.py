from __future__ import annotations

import json
from pathlib import Path

from teaagent.automation_observability import (
    automation_blocked_gate_reason,
    enrich_automation_status_row,
    extract_run_prompt_ledger,
)
from teaagent.automations import (
    AutomationSpec,
    AutomationStore,
    build_automation_status,
)


def test_status_row_includes_observability_fields(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.create(
        name='obs',
        task='Check repo and write summary to notes.txt with acceptance criteria',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        max_runtime_seconds=60,
        requires_subagent=True,
    )
    row = enrich_automation_status_row(tmp_path, spec)
    assert row['requires_subagent'] is True
    assert 'token_contributors' in row
    assert 'prompt_ledger' in row
    assert row['estimated_skill_tokens_next_tick'] == 0


def test_blocked_gate_reason_for_runtime_cap(tmp_path: Path) -> None:
    spec = AutomationSpec(
        automation_id='a1',
        name='cap',
        task='do work',
        schedule='every 30m',
        last_status='runtime_cap_exceeded',
        max_runtime_seconds=30,
    )
    reason = automation_blocked_gate_reason(tmp_path, spec)
    assert reason is not None
    assert 'max_runtime_seconds' in reason


def test_build_automation_status_lists_quarantined(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    draft = store.draft(
        name='q',
        task='Summarize feed with explicit scope and output path',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
    )
    store.create_quarantined(
        draft, provenance={'source_kind': 'web_message', 'action': 'quarantine'}
    )
    payload = build_automation_status(tmp_path, store=store)
    assert payload['quarantined_count'] == 1


def test_extract_prompt_ledger_from_audit(tmp_path: Path) -> None:
    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True)
    run_id = 'run-1'
    events = [
        {
            'run_id': run_id,
            'event_type': 'skill_load',
            'payload': {'estimated_skill_tokens': 42, 'selected_skills': ['a']},
        },
        {
            'run_id': run_id,
            'event_type': 'run_completed',
            'payload': {'cost_cents': 3.5, 'input_tokens': 100, 'output_tokens': 50},
        },
    ]
    path = runs_dir / f'{run_id}.jsonl'
    path.write_text(
        '\n'.join(json.dumps(event) for event in events) + '\n', encoding='utf-8'
    )
    ledger = extract_run_prompt_ledger(tmp_path, run_id)
    assert ledger['skill_load']['estimated_skill_tokens'] == 42
    assert ledger['run_completed']['cost_cents'] == 3.5
