from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.automations import AutomationSpec, AutomationStore, compute_next_run_at
from teaagent.cli import main


def test_compute_next_run_at_supports_every_and_daily() -> None:
    every = compute_next_run_at('every 30m')
    daily = compute_next_run_at('daily 09:00')
    assert every.endswith('+00:00')
    assert daily.endswith('+00:00')


def test_agent_automation_crud_flow(tmp_path: Path) -> None:
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'daily-doc-check',
                'check docs drift',
                '--schedule',
                'every 30m',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    created = json.loads(add_out.getvalue())
    automation_id = created['automation']['automation_id']

    list_out = io.StringIO()
    with redirect_stdout(list_out):
        list_code = main(['agent', 'automation', 'list', '--root', str(tmp_path)])
    assert list_code == 0
    rows = json.loads(list_out.getvalue())
    assert rows and rows[0]['automation_id'] == automation_id

    pause_out = io.StringIO()
    with redirect_stdout(pause_out):
        pause_code = main(
            ['agent', 'automation', 'pause', automation_id, '--root', str(tmp_path)]
        )
    assert pause_code == 0
    paused = json.loads(pause_out.getvalue())
    assert paused['automation']['enabled'] is False

    resume_out = io.StringIO()
    with redirect_stdout(resume_out):
        resume_code = main(
            ['agent', 'automation', 'resume', automation_id, '--root', str(tmp_path)]
        )
    assert resume_code == 0
    resumed = json.loads(resume_out.getvalue())
    assert resumed['automation']['enabled'] is True

    delete_out = io.StringIO()
    with redirect_stdout(delete_out):
        delete_code = main(
            ['agent', 'automation', 'delete', automation_id, '--root', str(tmp_path)]
        )
    assert delete_code == 0
    deleted = json.loads(delete_out.getvalue())
    assert deleted['status'] == 'deleted'


def test_automation_run_skips_when_background_alive(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.create(
        name='alive-check',
        task='noop',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='balanced',
        max_iterations=10,
        max_tool_calls=10,
    )
    bg_dir = tmp_path / '.teaagent' / 'background'
    bg_dir.mkdir(parents=True, exist_ok=True)
    bg_id = 'alive-bg'
    log_path = bg_dir / f'{bg_id}.log'
    log_path.write_text('', encoding='utf-8')
    (bg_dir / f'{bg_id}.json').write_text(
        json.dumps(
            {
                'background_id': bg_id,
                'pid': os.getpid(),
                'command': ['noop'],
                'started_at': '2026-05-24T00:00:00+00:00',
                'log_path': str(log_path),
            }
        ),
        encoding='utf-8',
    )
    store.update(AutomationSpec(**{**spec.to_dict(), 'running_background_id': bg_id}))

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            ['agent', 'automation', 'run', spec.automation_id, '--root', str(tmp_path)]
        )
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload['status'] == 'skipped_running'


def test_automation_serve_emits_health_snapshot(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'automation',
                'serve',
                '--max-ticks',
                '1',
                '--interval-seconds',
                '0.01',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 0
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    tick_payload = json.loads(lines[0])
    assert tick_payload['status'] == 'serve_tick'
    assert 'uptime_seconds' in tick_payload
    health = tick_payload['health']
    assert set(health.keys()) == {
        'automation_count',
        'enabled_count',
        'due_count',
        'running_count',
    }
