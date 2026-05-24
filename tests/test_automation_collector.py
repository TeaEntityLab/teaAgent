from __future__ import annotations

import json
import sys

from teaagent.automation_collector import parse_collector_payload, run_collector_command


def test_parse_collector_payload_wake_agent_false() -> None:
    wake, summary, err = parse_collector_payload(
        json.dumps({'wake_agent': False, 'summary': 'no changes'})
    )
    assert wake is False
    assert summary == 'no changes'
    assert err is None


def test_run_collector_command_executes_in_workspace(tmp_path) -> None:
    script = tmp_path / 'collector.py'
    script.write_text(
        'import json\nprint(json.dumps({"wake_agent": False, "summary": "unchanged"}))\n',
        encoding='utf-8',
    )
    result = run_collector_command(f'{sys.executable} {script}', root=tmp_path)
    assert result.exit_code == 0
    assert result.wake_agent is False
    assert result.summary == 'unchanged'


def test_run_collector_command_redacts_and_caps_output(tmp_path) -> None:
    script = tmp_path / 'collector.py'
    script.write_text(
        'print("token=sk-secret1234567890 " + "A" * 100)\n',
        encoding='utf-8',
    )
    result = run_collector_command(
        f'{sys.executable} {script}',
        root=tmp_path,
        max_output_bytes=40,
    )
    assert result.exit_code == 0
    assert result.stdout_truncated is True
    assert 'sk-secret' not in result.stdout
    assert '[REDACTED]' in result.stdout
    assert result.to_dict()['stdout_truncated'] is True


def test_run_collector_command_timeout_returns_structured_result(tmp_path) -> None:
    script = tmp_path / 'collector.py'
    script.write_text('import time\ntime.sleep(5)\n', encoding='utf-8')

    result = run_collector_command(
        f'{sys.executable} {script}',
        root=tmp_path,
        timeout_seconds=0.01,
    )

    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.wake_agent is False
    assert result.parse_error == 'timeout'
