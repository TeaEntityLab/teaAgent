"""AC: HITL approval presets honor --root when cwd differs from workspace."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.cli import main


def test_hitl_preset_applies_when_cwd_differs_from_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'src').mkdir()
    (repo / '.teaagent').mkdir(parents=True)
    (repo / '.teaagent' / 'config.toml').write_text(
        'provider = "gpt"\n', encoding='utf-8'
    )
    other_cwd = tmp_path / 'other'
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    grant_out = io.StringIO()
    with redirect_stdout(grant_out):
        grant_code = main(
            [
                'approval',
                'grant',
                'workspace_write_file',
                '--root',
                str(repo),
                '--path-glob',
                'src/**',
                '--scope',
                'always',
            ]
        )
    assert grant_code == 0
    assert json.loads(grant_out.getvalue())['tool_name'] == 'workspace_write_file'

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"src/out.txt","content":"ok\\n"},"call_id":"write-src"}',
            '{"type":"final","content":"done"}',
        ]
    )

    def fail_input(_prompt: str = '') -> str:
        raise AssertionError('HITL prompt should not run when preset matches --root')

    monkeypatch.setattr('builtins.input', fail_input)

    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'run',
                'gpt',
                'Write src/out.txt',
                '--root',
                str(repo),
                '--permission-mode',
                'prompt',
                '--hitl-approval',
                '--max-iterations',
                '6',
                '--max-tool-calls',
                '6',
            ]
        )
    payload = json.loads(run_out.getvalue())
    assert run_code == 0, payload
    assert payload['status'] == 'completed'
