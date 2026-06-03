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


# ── TASK-DD2-004: Harden path-scoped approvals ───────────────────────────────


def test_approval_rejects_parent_traversal(tmp_path: Path) -> None:
    """Test that approvals reject paths with parent traversal (..)."""
    from teaagent.ergonomics._approval_grants import _normalize_and_validate_path

    # Parent traversal should be rejected
    assert _normalize_and_validate_path('../etc/passwd', tmp_path) is None
    assert _normalize_and_validate_path('src/../../etc/passwd', tmp_path) is None
    assert _normalize_and_validate_path('..', tmp_path) is None


def test_approval_rejects_absolute_path_outside_workspace(tmp_path: Path) -> None:
    """Test that approvals reject absolute paths outside workspace."""
    from teaagent.ergonomics._approval_grants import _normalize_and_validate_path

    # Absolute path outside workspace should be rejected
    assert _normalize_and_validate_path('/etc/passwd', tmp_path) is None
    assert _normalize_and_validate_path('/tmp/test', tmp_path) is None


def test_approval_normalizes_valid_paths(tmp_path: Path) -> None:
    """Test that approvals normalize and accept valid paths within workspace."""
    from teaagent.ergonomics._approval_grants import _normalize_and_validate_path

    # Valid relative paths should be normalized
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'test.py').touch()

    result = _normalize_and_validate_path('src/test.py', tmp_path)
    assert result == 'src/test.py'

    # Backslashes should be normalized
    result = _normalize_and_validate_path('src\\test.py', tmp_path)
    assert result == 'src/test.py'


def test_approval_path_matches_with_workspace_validation(tmp_path: Path) -> None:
    """Test that _path_matches uses workspace validation."""
    from teaagent.ergonomics._approval_grants import _path_matches

    (tmp_path / 'src').mkdir()

    # Valid path should match
    args = {'path': 'src/test.py'}
    assert _path_matches(('src/**',), args, workspace_root=tmp_path) is True

    # Parent traversal should not match
    args = {'path': '../etc/passwd'}
    assert _path_matches(('**',), args, workspace_root=tmp_path) is False

    # Absolute path outside workspace should not match
    args = {'path': '/etc/passwd'}
    assert _path_matches(('**',), args, workspace_root=tmp_path) is False
