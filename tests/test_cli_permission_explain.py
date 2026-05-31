"""Tests for the teaagent permission explain CLI command (US-016)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from teaagent.cli import main


def test_permission_explain_all_modes() -> None:
    """Running `teaagent permission explain` with no mode shows all 5 modes."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {
        'read-only',
        'workspace-write',
        'prompt',
        'allow',
        'danger-full-access',
    }


def test_permission_explain_read_only() -> None:
    """Running `teaagent permission explain read-only` shows only read-only."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain', 'read-only'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {'read-only'}
    entry = modes['read-only']
    assert 'summary' in entry
    assert 'when_to_use' in entry
    assert 'allows' in entry
    assert 'blocks' in entry
    assert 'risk' in entry
    assert entry['risk'] == 'low'


def test_permission_explain_danger_full_access() -> None:
    """Running `teaagent permission explain danger-full-access` shows correct info."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain', 'danger-full-access'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {'danger-full-access'}
    entry = modes['danger-full-access']
    assert 'summary' in entry
    assert 'risk' in entry
    assert entry['risk'] == 'high'


def test_permission_explain_workspace_write() -> None:
    """Running `teaagent permission explain workspace-write` shows correct fields."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain', 'workspace-write'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {'workspace-write'}
    entry = modes['workspace-write']
    assert entry['risk'] == 'medium'


def test_permission_explain_prompt() -> None:
    """Running `teaagent permission explain prompt` shows correct fields."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain', 'prompt'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {'prompt'}
    entry = modes['prompt']
    assert entry['risk'] == 'medium'


def test_permission_explain_allow() -> None:
    """Running `teaagent permission explain allow` shows correct fields."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain', 'allow'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    assert set(modes.keys()) == {'allow'}
    entry = modes['allow']
    assert entry['risk'] == 'high'


def test_permission_explain_help_works() -> None:
    """Running `teaagent permission explain --help` displays help text."""
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            main(['permission', 'explain', '--help'])
        except SystemExit as exc:
            assert exc.code == 0

    output = out.getvalue()
    assert 'read-only' in output
    assert 'danger-full-access' in output
    assert 'explain' in output


def test_all_mode_entries_have_required_fields() -> None:
    """Every mode entry in the full output has all required fields."""
    out = io.StringIO()
    with redirect_stdout(out):
        exit_code = main(['permission', 'explain'])

    assert exit_code == 0
    payload = json.loads(out.getvalue())
    modes = payload.get('permission_modes', {})
    required_fields = {
        'summary',
        'when_to_use',
        'allows',
        'blocks',
        'risk',
        'rollback',
        'tip',
    }
    for mode_name, entry in modes.items():
        missing = required_fields - set(entry.keys())
        assert not missing, f"Mode '{mode_name}' missing fields: {missing}"
