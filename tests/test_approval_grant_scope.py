# test-type: adversarial
"""Approval grant scope: matcher fails closed on rejected paths and the
"always for this tool" confirmation states the real scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.ergonomics._approval_grants import _path_matches
from teaagent.runner import ApprovalRequest

SCOPE_TEXT = 'all paths in this workspace, this session, 8h'


# --- matcher: a '*' grant must not match a path that failed validation ---


def test_star_grant_does_not_match_absolute_path_outside_workspace(
    tmp_path: Path,
) -> None:
    assert _path_matches(('*',), {'path': '/etc/passwd'}, tmp_path) is False


def test_star_grant_does_not_match_parent_traversal(tmp_path: Path) -> None:
    assert _path_matches(('*',), {'path': '../x'}, tmp_path) is False


def test_star_grant_matches_valid_workspace_path(tmp_path: Path) -> None:
    assert _path_matches(('*',), {'path': 'a.txt'}, tmp_path) is True


def test_star_grant_still_applies_to_tools_without_path_argument(
    tmp_path: Path,
) -> None:
    assert _path_matches(('*',), {}, tmp_path) is True
    assert _path_matches(('*',), {'command': 'ls'}, tmp_path) is True


def test_star_grant_rejects_lone_path_key_under_alternate_name(tmp_path: Path) -> None:
    # The key is a recognised path argument; its rejection must fail closed.
    assert _path_matches(('*',), {'file': '../x'}, tmp_path) is False
    assert _path_matches(('*',), {'target_path': '/etc/passwd'}, tmp_path) is False


# --- CLI confirmation text must state the real scope of 't' ---


@pytest.mark.parametrize(
    'module_path, handler_name',
    [
        ('teaagent.cli._handlers.agent_helpers', 'make_cli_approval_handler'),
        ('teaagent.cli._handlers._agent.approval', 'make_cli_approval_handler'),
    ],
)
def test_always_for_tool_prints_real_scope_and_grants_all_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    handler_name: str,
) -> None:
    import importlib

    factory = getattr(importlib.import_module(module_path), handler_name)
    monkeypatch.setattr('builtins.input', lambda *_a, **_k: 't')
    handler = factory(tmp_path, permission_mode='prompt')

    request = ApprovalRequest(
        call_id='call-1',
        tool_name='workspace_write_file',
        arguments={'path': 'a.txt'},
        reason='test',
        annotations={'destructive': True},
    )
    assert handler(request) is True

    err = capsys.readouterr().err
    assert SCOPE_TEXT in err
    assert 'current directory' not in err

    # The grant covers a different workspace path ...
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    store = ApprovalPresetStore(tmp_path)
    assert (
        store.is_allowed(
            'workspace_write_file',
            permission_mode='prompt',
            arguments={'path': 'b.txt'},
        )
        is True
    )
    # ... but not a path that escapes the workspace.
    assert (
        store.is_allowed(
            'workspace_write_file',
            permission_mode='prompt',
            arguments={'path': '/etc/passwd'},
        )
        is False
    )
