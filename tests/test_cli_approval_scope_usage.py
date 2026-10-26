# test-type: behavior
"""approval CLI: scoped grant/deny usage errors and check argument leakage."""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.cli import main


def _seed_root(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')


def _assert_classified_usage_error(err: str, *, fix_flag: str) -> None:
    assert fix_flag in err
    assert 'Unexpected error' not in err
    assert 'report this' not in err.lower()
    assert 'github.com' not in err


def test_approval_deny_without_scope_is_usage_error(tmp_path, capsys) -> None:
    _seed_root(tmp_path)

    code = main(['approval', 'deny', 'workspace_write_file', '--root', str(tmp_path)])

    captured = capsys.readouterr()
    assert code != 0
    _assert_classified_usage_error(captured.err, fix_flag='--path-glob')
    assert '--command-prefix' in captured.err
    # Nothing was written: no grant exists after the refused deny.
    capsys.readouterr()
    assert main(['approval', 'list', '--grants-only', '--root', str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_approval_grant_non_session_without_scope_names_fix(tmp_path, capsys) -> None:
    _seed_root(tmp_path)

    for scope in ('always', 'deny'):
        code = main(
            [
                'approval',
                'grant',
                'workspace_write_file',
                '--scope',
                scope,
                '--root',
                str(tmp_path),
            ]
        )
        captured = capsys.readouterr()
        assert code != 0, scope
        _assert_classified_usage_error(captured.err, fix_flag='--path-glob')
        assert '--command-prefix' in captured.err


def test_approval_check_does_not_inject_cli_namespace_as_command(
    tmp_path, capsys
) -> None:
    _seed_root(tmp_path)
    assert (
        main(
            [
                'approval',
                'deny',
                'workspace_write_file',
                '--root',
                str(tmp_path),
                '--command-prefix',
                'approval',
            ]
        )
        == 0
    )
    capsys.readouterr()

    # No command argument given: the argparse subcommand name must not be
    # evaluated as the tool's `command`, so the prefix deny must not match.
    assert (
        main(['approval', 'check', 'workspace_write_file', '--root', str(tmp_path)])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert 'command' not in payload['arguments']
    assert payload['matched_grant'] is None
    assert payload['decision'] != 'deny'

    # Positive control: a real --command that starts with the prefix still matches.
    assert (
        main(
            [
                'approval',
                'check',
                'workspace_write_file',
                '--root',
                str(tmp_path),
                '--command',
                'approval run',
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload['arguments'] == {'command': 'approval run'}
    assert payload['decision'] == 'deny'
