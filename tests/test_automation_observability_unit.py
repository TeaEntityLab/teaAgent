from __future__ import annotations

from dataclasses import replace

from teaagent.automation_chain import persist_automation_handoff
from teaagent.automation_observability import (
    automation_blocked_gate_reason,
    build_last_output_preview,
    build_token_contributors,
    enrich_automation_status_row,
    extract_run_prompt_ledger,
)
from teaagent.automations import AutomationStore
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_extract_run_prompt_ledger_from_audit(tmp_path) -> None:
    assert extract_run_prompt_ledger(tmp_path, None) == {}
    assert extract_run_prompt_ledger(tmp_path, 'missing')['error'] == 'run_not_found'

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-ledger')
    audit.record(
        'skill_load',
        'run-ledger',
        estimated_skill_tokens=10,
        selected_skills=['alpha'],
        skill_prompt_mode='eager',
        loaded=['alpha'],
    )
    audit.record(
        'run_completed',
        'run-ledger',
        answer='ok',
        cost_cents=1.5,
        input_tokens=100,
        output_tokens=20,
    )
    store.logger_for_result(
        RunResult(
            run_id='run-ledger',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    audit.record('run_failed', 'run-ledger', category='tool', message='boom')
    ledger = extract_run_prompt_ledger(tmp_path, 'run-ledger')
    assert ledger['skill_load']['loaded'] == ['alpha']
    assert ledger['run_completed']['input_tokens'] == 100
    assert ledger['run_failed']['message'] == 'boom'


def test_automation_observability_helpers(tmp_path) -> None:
    spec = replace(
        AutomationStore(tmp_path).draft(
            name='obs',
            task='Summarize repo changes with explicit output path notes.txt',
            schedule='every 30m',
            provider=None,
            model=None,
            permission_mode='read-only',
            context_profile='lean',
            max_iterations=3,
            max_tool_calls=3,
            delivery='background_log',
            max_cost_cents=1,
        ),
        last_status='cost_cap_exceeded',
    )
    assert 'max_cost_cents' in (automation_blocked_gate_reason(tmp_path, spec) or '')
    collector_spec = replace(spec, last_status='collector_failed')
    assert automation_blocked_gate_reason(tmp_path, collector_spec) == (
        'collector command exited non-zero'
    )
    runtime_spec = replace(
        spec, last_status='runtime_cap_exceeded', max_runtime_seconds=120
    )
    assert 'max_runtime_seconds' in (
        automation_blocked_gate_reason(tmp_path, runtime_spec) or ''
    )
    missing_spec = replace(spec, last_status='background_missing')
    assert automation_blocked_gate_reason(tmp_path, missing_spec) == (
        'background worker record missing'
    )
    contributors = build_token_contributors(tmp_path, spec)
    assert contributors
    row = enrich_automation_status_row(tmp_path, spec, log_tail='tail')
    assert row['automation_id'] == spec.automation_id
    assert build_last_output_preview(tmp_path, spec)

    upstream = AutomationStore(tmp_path).draft(
        name='upstream',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='background_log',
    )
    persist_automation_handoff(
        tmp_path, upstream, summary='upstream summary for chained automation'
    )
    chained = replace(spec, context_from=upstream.automation_id)
    chained_row = enrich_automation_status_row(tmp_path, chained)
    assert chained_row['upstream_handoff_preview']
