"""WS4 observability and operations tests."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from teaagent.audit_health import assess_audit_health, format_audit_health
from teaagent.audit_tail import (
    classify_audit_event,
    format_audit_tail_human,
    tail_audit_events,
)
from teaagent.cli import main
from teaagent.config_lint import lint_runtime_config
from teaagent.run_metrics import summarize_run_latencies
from teaagent.run_receipt import build_run_receipt
from teaagent.run_store import RunResult, RunStore
from teaagent.types import AuditLogger, PermissionMode


def test_summarize_run_latencies_from_audit_pairs() -> None:
    events = [
        {
            'event_type': 'iteration_started',
            'created_at': '2026-06-06T10:00:00+00:00',
            'payload': {},
        },
        {
            'event_type': 'tool_call_started',
            'created_at': '2026-06-06T10:00:01+00:00',
            'payload': {'call_id': 'c1', 'tool_name': 'grep'},
        },
        {
            'event_type': 'tool_call_completed',
            'created_at': '2026-06-06T10:00:02+00:00',
            'payload': {'call_id': 'c1', 'duration_ms': 250},
        },
        {
            'event_type': 'tool_call_pending_approval',
            'created_at': '2026-06-06T10:00:03+00:00',
            'payload': {'call_id': 'c2', 'tool_name': 'workspace_write_file'},
        },
        {
            'event_type': 'tool_call_approved',
            'created_at': '2026-06-06T10:00:13+00:00',
            'payload': {'call_id': 'c2'},
        },
        {'event_type': '_disk_write_error', 'payload': {}},
    ]
    metrics = summarize_run_latencies(events)
    assert metrics.llm_count == 1
    assert metrics.llm_latencies_ms == [pytest.approx(2000.0)]
    assert metrics.tool_count == 1
    assert metrics.tool_latencies_ms == [250.0]
    assert metrics.approval_count == 1
    assert metrics.approval_latencies_ms == [pytest.approx(10000.0)]
    assert metrics.audit_write_errors == 1


def test_assess_audit_health_with_chain_and_cooldown(tmp_path: Path) -> None:
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'run-health', task='observe')
    events = audit.events
    health = assess_audit_health(events, log_path=log, live_logger=audit)
    assert health.disk_write_errors == 0
    assert health.chain_valid is True
    assert health.cooldown_active is False
    assert 'Chain: valid' in format_audit_health(health)


def test_audit_tail_classifies_and_redacts() -> None:
    events = [
        {
            'created_at': '2026-06-06T10:00:00+00:00',
            'event_type': 'run_started',
            'run_id': 'run-tail',
            'payload': {'task': 'demo', 'api_key': 'sk-secret-value-1234567890'},
        },
        {
            'created_at': '2026-06-06T10:00:01+00:00',
            'event_type': 'tool_call_completed',
            'run_id': 'run-tail',
            'payload': {'tool_name': 'grep', 'status': 'ok'},
        },
    ]
    assert classify_audit_event('run_started') == 'lifecycle'
    assert classify_audit_event('tool_call_completed') == 'tool'
    rows = tail_audit_events(events, limit=5)
    assert rows[0]['classification'] == 'lifecycle'
    assert rows[1]['classification'] == 'tool'
    payload = rows[0]['payload']
    assert isinstance(payload, dict)
    assert payload.get('api_key') != 'sk-secret-value-1234567890'
    human = format_audit_tail_human(events, limit=5)
    assert 'Audit tail' in human
    assert 'tool_call_completed' in human


def test_audit_tail_cli_human_and_json(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-tail-cli')
    audit.record('run_started', 'run-tail-cli', task='tail test')
    audit.record(
        'tool_call_completed',
        'run-tail-cli',
        tool_name='grep',
        status='ok',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-tail-cli',
            final_answer='done',
            iterations=1,
            tool_calls=1,
            status='completed',
        ),
        audit,
    )

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'audit',
                    'tail',
                    'run-tail-cli',
                    '--human',
                    '--limit',
                    '5',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    assert 'Audit tail' in out.getvalue()

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'audit',
                    'tail',
                    'run-tail-cli',
                    '--limit',
                    '5',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    payload = json.loads(out.getvalue())
    assert payload['run_id'] == 'run-tail-cli'
    assert len(payload['events']) >= 2


def test_config_lint_flags_unsafe_combinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv('TEAAGENT_MAX_ESTIMATED_COST_CENTS', raising=False)
    monkeypatch.delenv('TEAAGENT_BUDGET_CAP_CENTS', raising=False)
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '0')
    findings = lint_runtime_config(
        root=tmp_path,
        permission_mode=PermissionMode.ALLOW,
        allow_destructive=True,
        subagent_isolation='shared',
    )
    codes = {finding.code for finding in findings}
    assert 'missing_audit_path' in codes
    assert 'permissive_destructive' in codes
    assert 'shared_subagent_isolation' in codes
    assert 'unclear_cost_policy' in codes
    assert 'compliance_mode_off' in codes


def test_doctor_config_lint_cli(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        result = main(['doctor', 'config-lint', '--root', str(tmp_path)])
    payload = json.loads(out.getvalue())
    assert payload['status'] in {'ok', 'error'}
    assert 'findings' in payload
    assert isinstance(payload['finding_count'], int)
    assert result in {0, 1}


def test_run_receipt_includes_latency_and_audit_health(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-metrics')
    audit.record('run_started', 'run-metrics', task='metrics demo')
    audit.record(
        'tool_call_completed',
        'run-metrics',
        call_id='c1',
        tool_name='grep',
        duration_ms=100,
    )
    store.logger_for_result(
        RunResult(
            run_id='run-metrics',
            final_answer='ok',
            iterations=1,
            tool_calls=1,
            status='completed',
        ),
        audit,
    )
    receipt = build_run_receipt(store, 'run-metrics', str(tmp_path))
    assert 'Latency metrics:' in receipt
    assert 'Audit durability:' in receipt


def test_pending_approvals_payload_includes_queue_depth(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-depth')
    audit.record('run_started', 'run-depth', task='queue depth')
    audit.record(
        'tool_call_pending_approval',
        'run-depth',
        call_id='call-depth',
        tool_name='workspace_write_file',
        created_at='2026-06-06T10:00:00+00:00',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-depth',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--root', str(tmp_path)]) == 0
    payload = json.loads(out.getvalue())
    assert payload['queue_depth'] == 1
    assert payload['pending'][0]['age_seconds'] is not None


def test_subagent_list_includes_queue_depth_and_age(tmp_path: Path) -> None:
    import threading

    from teaagent.subagents._approval_queue import get_approval_queue

    queue = get_approval_queue('parent-ws4', workspace_root=tmp_path)
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            queue.submit_request_sync(
                subagent_id='sub-ws4',
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'x.py'},
                permission_mode='workspace-write',
                isolation='worktree',
                batch_index=0,
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    request_id: str | None = None
    for _ in range(50):
        out = io.StringIO()
        with redirect_stdout(out):
            assert (
                main(
                    [
                        'approval',
                        'subagents',
                        'list',
                        '--root',
                        str(tmp_path),
                    ]
                )
                == 0
            )
        payload = json.loads(out.getvalue())
        if payload.get('queue_depth') == 1:
            pending = payload['pending'][0]
            assert pending.get('age_seconds') is not None
            assert pending.get('risk_class') == 'destructive'
            assert payload['count'] == 1
            request_id = pending['request_id']
            break
        thread.join(timeout=0.05)

    assert request_id is not None

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'subagents',
                    'list',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    human = out.getvalue()
    assert 'queue depth: 1' in human.lower()
    assert 'age=' in human

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'subagents',
                    'approve',
                    request_id,
                    '--parent-run-id',
                    'parent-ws4',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    thread.join(timeout=2)
    assert results == [True]
