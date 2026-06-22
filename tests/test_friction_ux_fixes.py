"""Tests for owner-friction UX fixes (F1–F8)."""

from __future__ import annotations

import argparse
import sys

import pytest

from teaagent.approval.selectors import PendingApprovalView, format_pending_approvals
from teaagent.ergonomics.cli_output import wants_human_cli
from teaagent.governance.conversation_ux import soften_operator_copy
from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools._shell import run_shell_inspect


def test_wants_human_cli_tty_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    args = argparse_namespace(human=False, json=False, json_stream=False)
    assert wants_human_cli(args) is True


def test_wants_human_cli_json_forces_machine() -> None:
    args = argparse_namespace(human=False, json=True, json_stream=False)
    assert wants_human_cli(args) is False


def test_wants_human_cli_explicit_human() -> None:
    args = argparse_namespace(human=True, json=True, json_stream=False)
    assert wants_human_cli(args) is True


def test_soften_operator_copy() -> None:
    text = 'Open cockpit for tenant envelope trust tier'
    softened = soften_operator_copy(text)
    assert 'cockpit' not in softened.lower()
    assert 'tenant' not in softened.lower()
    assert 'status dashboard' in softened


def test_format_pending_approvals_shows_selector_hint() -> None:
    views = [
        PendingApprovalView(
            selector=1,
            run_id='run-1',
            task='fix tests',
            status='blocked',
            created_at='2026-06-22T00:00:00+00:00',
            age_seconds=12.0,
            call_id='call-abc',
            tool_name='workspace_write_file',
            reason='destructive write',
            path_summary='src/foo.py',
            risk_class='destructive',
            expires_at='2026-06-22T01:00:00+00:00',
        )
    ]
    text = format_pending_approvals(views)
    assert 'approval approve --selector 1' in text
    assert 'call-abc' in text


def test_shell_inspect_error_lists_allowed_commands(tmp_path) -> None:
    config = WorkspaceToolConfig(root=tmp_path, max_shell_output_bytes=1000)
    with pytest.raises(ValueError, match='workspace_run_shell_mutate'):
        run_shell_inspect(config, {'command': 'cat README.md'})


def argparse_namespace(**kwargs: object) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)
