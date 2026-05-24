from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.automation_limits import (
    automation_run_cost_cents,
    background_runtime_seconds,
    cost_cap_exceeded,
    enforce_runtime_cap,
    terminate_background_pid,
)
from teaagent.automations import AutomationStore
from teaagent.daily import DailyBrief, HarnessHealthReport, RunRollup, TokenBudgetReport
from teaagent.ergonomics.daily_cost import (
    check_daily_cost_cap,
    daily_spend_cents,
    estimate_run_cost_cents,
)
from teaagent.ergonomics.notify import _escape, notify
from teaagent.ergonomics.run_history import (
    _parse_day,
    list_recall_runs,
    list_yesterday_runs,
)
from teaagent.ergonomics.status_short import build_status_short
from teaagent.ergonomics.workspace_defaults import _read_json, _read_toml
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_notify_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('teaagent.ergonomics.notify.platform.system', lambda: 'Darwin')
    calls: list[list[str]] = []

    def _run(cmd: list[str], **kwargs: object) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr('teaagent.ergonomics.notify.subprocess.run', _run)
    assert notify('Title', 'Message "quoted"', sound=True) is True
    assert calls and 'osascript' in calls[0]
    assert 'Glass' in calls[0][-1]


def test_notify_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('teaagent.ergonomics.notify.platform.system', lambda: 'Linux')
    calls: list[list[str]] = []

    def _run(cmd: list[str], **kwargs: object) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr('teaagent.ergonomics.notify.subprocess.run', _run)
    assert notify('Title', 'Body') is True
    assert calls[0][:2] == ['notify-send', 'Title']


def test_notify_returns_false_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('teaagent.ergonomics.notify.platform.system', lambda: 'Darwin')

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError('nope')

    monkeypatch.setattr('teaagent.ergonomics.notify.subprocess.run', _boom)
    assert notify('t', 'm') is False


def test_notify_unknown_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('teaagent.ergonomics.notify.platform.system', lambda: 'Windows')
    assert notify('t', 'm') is False


def test_escape_quotes() -> None:
    assert _escape('say "hi"') == 'say \\"hi\\"'


def test_parse_day_handles_invalid() -> None:
    assert _parse_day('not-a-date') is None
    assert _parse_day('2026-05-23T12:00:00+00:00') == date(2026, 5, 23)


def test_list_yesterday_and_recall_runs(tmp_path: Path) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    store = RunStore(tmp_path)

    for run_id, created in (
        ('run-yesterday', yesterday + 'T10:00:00+00:00'),
        ('run-today', today + 'T10:00:00+00:00'),
    ):
        audit = store.audit_logger(run_id)
        audit.record('run_started', run_id, task=f'task {run_id}')
        audit.record('run_completed', run_id, answer='ok')
        store.logger_for_result(
            RunResult(
                run_id=run_id,
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='completed',
            ),
            audit,
        )
        path = store.run_path(run_id)
        lines = path.read_text(encoding='utf-8').splitlines()
        patched = []
        for line in lines:
            event = json.loads(line)
            event['created_at'] = created
            patched.append(json.dumps(event))
        path.write_text('\n'.join(patched) + '\n', encoding='utf-8')

    yesterday_runs = list_yesterday_runs(tmp_path, limit=5)
    assert any(item['run_id'] == 'run-yesterday' for item in yesterday_runs)
    recall = list_recall_runs(tmp_path, limit=2)
    assert len(recall) <= 2
    assert recall[0]['run_id'] in {'run-today', 'run-yesterday'}


def test_list_recall_enrich_handles_pending_errors(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-enrich')
    audit.record('run_started', 'run-enrich', task='hello')
    store.logger_for_result(
        RunResult(
            run_id='run-enrich',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    with patch.object(
        RunStore, 'pending_approval_for_run', side_effect=RuntimeError('boom')
    ):
        payload = list_recall_runs(tmp_path, limit=1)[0]
    assert payload['pending_approval'] is None


def test_estimate_run_cost_and_daily_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        {
            'event_type': 'run_started',
            'payload': {'provider': 'gpt', 'model': 'default'},
        }
    ]
    monkeypatch.setattr(
        'teaagent.ergonomics.daily_cost.estimate_cost_preflight',
        lambda *args, **kwargs: 12.5,
    )
    assert estimate_run_cost_cents(events) == 12.5

    monkeypatch.setattr(
        'teaagent.ergonomics.daily_cost.estimate_cost_preflight',
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('bad')),
    )
    assert estimate_run_cost_cents(events) == 0.0

    store = RunStore(tmp_path)
    today = date.today().isoformat()
    audit = store.audit_logger('run-cost')
    audit.record('run_started', 'run-cost', task='cost', provider='gpt', model='m')
    audit.record('run_completed', 'run-cost', answer='ok')
    store.logger_for_result(
        RunResult(
            run_id='run-cost',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    path = store.run_path('run-cost')
    lines = [
        json.dumps({**json.loads(line), 'created_at': today + 'T09:00:00+00:00'})
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    monkeypatch.setattr(
        'teaagent.ergonomics.daily_cost.estimate_cost_preflight',
        lambda *args, **kwargs: 50.0,
    )
    assert daily_spend_cents(tmp_path) >= 50.0
    with pytest.raises(SystemExit):
        check_daily_cost_cap(tmp_path, 1)


def test_build_status_short(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    brief = DailyBrief(
        task='status',
        provider='gpt',
        model=None,
        permission_mode='prompt',
        ready=True,
        context_profile={},
        preflight=None,
        token_budget=TokenBudgetReport(
            provider='gpt',
            model=None,
            profile='lean',
            estimated_input_tokens=100,
            output_reserve_tokens=50,
            estimated_total_tokens=150,
            max_context_tokens=1000,
            usage_ratio=0.1,
            usage_level='yellow',
            estimated_cost_cents=0.0,
            contributors={},
        ),
        harness_health=HarnessHealthReport(
            healthy=True,
            failures=[],
            warnings=[],
            optional_indexes={},
            docs_drift_check_available=False,
        ),
        recent_runs=[
            RunRollup(
                run_id='run-active',
                task='t',
                status='running',
                updated_at='now',
                pending_approval={'call_id': 'c1'},
            )
        ],
        recommendations=[],
    )
    monkeypatch.setattr(
        'teaagent.ergonomics.status_short.build_daily_brief', lambda **kw: brief
    )
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-active')
    audit.record('run_started', 'run-active', task='t')
    store.logger_for_result(
        RunResult(
            run_id='run-active',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    line = build_status_short(
        root=tmp_path,
        provider='gpt',
        run_id='run-active',
        permission_mode=PermissionMode.PROMPT,
    )
    assert line.startswith('teaagent:Y')
    assert 'pending=1' in line


def test_build_status_short_missing_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brief = DailyBrief(
        task=None,
        provider='gpt',
        model=None,
        permission_mode='prompt',
        ready=True,
        context_profile={},
        preflight=None,
        token_budget=TokenBudgetReport(
            provider='gpt',
            model=None,
            profile='lean',
            estimated_input_tokens=1,
            output_reserve_tokens=1,
            estimated_total_tokens=2,
            max_context_tokens=None,
            usage_ratio=None,
            usage_level='green',
            estimated_cost_cents=0.0,
            contributors={},
        ),
        harness_health=HarnessHealthReport(
            healthy=True,
            failures=[],
            warnings=[],
            optional_indexes={},
            docs_drift_check_available=False,
        ),
        recent_runs=[],
        recommendations=[],
    )
    monkeypatch.setattr(
        'teaagent.ergonomics.status_short.build_daily_brief', lambda **kw: brief
    )
    line = build_status_short(root=tmp_path, provider='gpt', run_id='missing-run')
    assert 'status=missing' in line


def test_read_toml_and_json_edge_cases(tmp_path: Path) -> None:
    bad_toml = tmp_path / 'bad.toml'
    bad_toml.write_text('not valid [[[', encoding='utf-8')
    assert _read_toml(bad_toml) == {}

    missing = tmp_path / 'missing.toml'
    assert _read_toml(missing) == {}

    bad_json = tmp_path / 'bad.json'
    bad_json.write_text('{not json', encoding='utf-8')
    assert _read_json(bad_json) == {}


def test_automation_limits_runtime_and_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert background_runtime_seconds({}) is None
    assert background_runtime_seconds({'started_at': 'bad'}) is None
    started = '2020-01-01T00:00:00+00:00'
    elapsed = background_runtime_seconds({'started_at': started})
    assert elapsed is not None and elapsed > 0

    monkeypatch.setattr(
        'teaagent.automation_limits.terminate_background_pid', lambda pid: True
    )
    assert (
        enforce_runtime_cap(
            {'alive': True, 'started_at': started, 'pid': 99999},
            max_runtime_seconds=1,
        )
        is True
    )
    assert enforce_runtime_cap({'alive': False}, max_runtime_seconds=1) is False
    assert terminate_background_pid(999_999_999) in {True, False}

    store = RunStore(tmp_path)
    audit = store.audit_logger('auto-cost')
    audit.record('run_started', 'auto-cost', task='t', provider='gpt', model='m')
    store.logger_for_result(
        RunResult(
            run_id='auto-cost',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    monkeypatch.setattr(
        'teaagent.automation_limits.estimate_run_cost_cents', lambda events: 100.0
    )
    assert automation_run_cost_cents(str(tmp_path), 'auto-cost') == 100.0
    spec = AutomationStore(tmp_path).draft(
        name='cap',
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
    )
    assert cost_cap_exceeded(str(tmp_path), spec, run_id='auto-cost') is True
