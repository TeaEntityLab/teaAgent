# test-type: behavior
"""Observe-only foreign hook: metadata in, tool arguments out, enforce refused."""

from __future__ import annotations

import io
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from teaagent.audit_chain import verify_audit_chain
from teaagent.foreign_hook import hook_command, main, prove_install_command


def test_observe_records_metadata_and_drops_tool_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audit = tmp_path / 'observe.jsonl'
    secret = 'rm -rf /must-not-land-in-the-audit-log'
    raw = json.dumps(
        {
            'hook_event_name': 'PreToolUse',
            'tool_name': 'Bash',
            'session_id': 'sess-1',
            'permission_mode': 'default',
            'tool_input': {'command': secret, 'file_path': '/etc/passwd'},
            'tool_response': {'stdout': secret},
        }
    ).encode()

    code = main(['--audit', str(audit)], stdin=io.BytesIO(raw))
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == '{}'
    text = audit.read_text(encoding='utf-8')
    assert secret not in text
    assert '/etc/passwd' not in text
    assert 'tool_input' not in text
    assert 'PreToolUse' in text
    assert 'Bash' in text
    result = verify_audit_chain(audit, strict=True)
    assert result.valid, result.error
    assert result.event_count == 1


def test_enforce_flag_exits_2_and_does_not_emit_a_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audit = tmp_path / 'observe.jsonl'
    raw = json.dumps(
        {'hook_event_name': 'PreToolUse', 'tool_name': 'Write', 'session_id': 'sess-2'}
    ).encode()

    code = main(['--audit', str(audit), '--enforce'], stdin=io.BytesIO(raw))
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ''
    assert 'permissionDecision' not in captured.err
    assert 'not implemented' in captured.err
    text = audit.read_text(encoding='utf-8')
    assert 'enforce_refused' in text


def test_enforce_exits_2_when_audit_logger_cannot_be_constructed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A parent that is a file makes AuditLogger mkdir/chmod fail closed."""
    occupied = tmp_path / 'not-a-directory'
    occupied.write_text('occupied', encoding='utf-8')
    audit = occupied / 'observe.jsonl'
    raw = json.dumps(
        {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'session_id': 'sess-3'}
    ).encode()

    code = main(['--audit', str(audit), '--enforce'], stdin=io.BytesIO(raw))
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ''
    assert 'permissionDecision' not in captured.err
    assert 'not implemented' in captured.err
    assert 'was not recorded' in captured.err
    assert not audit.exists()


def test_observe_exits_0_when_the_audit_parent_is_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed audit write loses the line. It does not fail the hook."""
    occupied = tmp_path / 'not-a-directory'
    occupied.write_text('occupied', encoding='utf-8')
    audit = occupied / 'observe.jsonl'
    raw = json.dumps(
        {'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'session_id': 'sess-4'}
    ).encode()

    code = main(['--audit', str(audit)], stdin=io.BytesIO(raw))
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == '{}'
    assert 'permissionDecision' not in captured.out
    assert 'was not recorded' in captured.err
    assert not audit.exists()


def test_observe_reports_when_the_append_falls_back_to_memory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swallowed append error is not a recorded observation.

    With compliance mode off, AuditLogger.record catches the OSError, sets
    disk_error, and keeps the event in memory. The constructor succeeded.
    """
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '0')
    audit = tmp_path / 'observe.jsonl'
    audit.mkdir()
    raw = json.dumps(
        {'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'session_id': 'sess-5'}
    ).encode()

    code = main(['--audit', str(audit)], stdin=io.BytesIO(raw))
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == '{}'
    assert 'permissionDecision' not in captured.out
    assert 'was not recorded' in captured.err
    assert 'IsADirectoryError' in captured.err
    assert audit.is_dir()
    assert list(audit.iterdir()) == []


def test_print_install_is_async_post_tool_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audit = tmp_path / 'observe.jsonl'
    code = main(
        ['--print-install', '--audit', str(audit)],
        stdin=io.BytesIO(b'{"tool_input":{"command":"rm -rf /"}}'),
    )
    captured = capsys.readouterr()
    snippet = json.loads(captured.out)

    assert code == 0
    assert 'PreToolUse' not in captured.out
    assert 'permissionDecision' not in captured.out
    assert '--enforce' not in captured.out
    assert 'not on the allow path' in captured.err
    hook = snippet['hooks']['PostToolUse'][0]['hooks'][0]
    command = hook['command']
    assert hook['async'] is True
    assert command == hook_command()
    interpreter = shlex.split(command)[0]
    assert Path(interpreter) == Path(sys.executable).absolute()
    assert interpreter != 'python'
    assert command.endswith(' -m teaagent.foreign_hook')
    assert 'installed in this interpreter' in captured.err
    assert not audit.exists()


def test_hook_command_quotes_an_interpreter_path_with_spaces() -> None:
    command = hook_command('/tmp/Python 3/bin/python')
    assert shlex.split(command) == [
        str(Path('/tmp/Python 3/bin/python').absolute()),
        '-m',
        'teaagent.foreign_hook',
    ]
    assert command.startswith("'")


def test_install_command_records_from_an_unrelated_directory(tmp_path: Path) -> None:
    """A user-level hook runs in the project cwd, not in the checkout."""
    unrelated = tmp_path / 'other-project'
    unrelated.mkdir()
    command = hook_command()
    secret = '/etc/passwd'
    proc = subprocess.run(
        ['/bin/bash', '-c', command],
        cwd=unrelated,
        input=json.dumps(
            {
                'hook_event_name': 'PostToolUse',
                'tool_name': 'Read',
                'tool_input': {'file_path': secret},
            }
        ).encode(),
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == b'{}'
    audit = unrelated / '.teaagent' / 'foreign-hooks' / 'observe.jsonl'
    text = audit.read_text(encoding='utf-8')
    assert 'Read' in text
    assert secret not in text
    assert 'tool_input' not in text


def test_prove_install_rejects_a_probe_that_only_kept_the_event_in_memory() -> None:
    """A file plus exit 0 is not success when the hook says the write was missed."""
    command = (
        'mkdir -p .teaagent/foreign-hooks && '
        "printf '%s\\n' '{}' > .teaagent/foreign-hooks/observe.jsonl && "
        "echo 'teaagent foreign_hook: observation was not recorded (OSError)' >&2 && "
        "printf '%s' '{}'"
    )

    problem = prove_install_command(command)

    assert problem is not None
    assert 'was not recorded' in problem


def test_print_install_refuses_to_combine_with_enforce(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(['--print-install', '--enforce'], stdin=io.BytesIO(b'{}'))
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ''
    assert 'cannot be combined' in captured.err


def test_oversize_stdin_is_not_parsed_for_fields(tmp_path: Path) -> None:
    audit = tmp_path / 'observe.jsonl'
    secret = 'SECRET-PAST-THE-CAP'
    raw = (
        b'{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"'
        + secret.encode()
        + b'"}}'
    )

    code = main(
        ['--audit', str(audit), '--max-bytes', '32'],
        stdin=io.BytesIO(raw),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == 0
    text = audit.read_text(encoding='utf-8')
    assert secret not in text
    assert 'truncated' in text
