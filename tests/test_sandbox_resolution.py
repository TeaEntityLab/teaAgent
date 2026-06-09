"""Tests for git sandbox lifecycle audit and evidence extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from teaagent.cli._handlers._agent.sandbox_resolution import (
    git_sandbox_audit_payload,
    record_git_sandbox_resolved,
    record_git_sandbox_started,
    resolve_git_sandbox_after_run,
)
from teaagent.run_evidence import extract_git_sandbox
from teaagent.sandbox import GitBranchSandbox


def test_git_sandbox_audit_payload_fields() -> None:
    sandbox = GitBranchSandbox('/tmp', run_id='abc123')
    sandbox._original_branch = 'main'
    sandbox._stash_id = 'stash@{0}'

    payload = git_sandbox_audit_payload(sandbox)

    assert 'run_id' not in payload
    assert payload['branch_name'] == 'teaagent-sandbox-abc123'
    assert payload['original_branch'] == 'main'
    assert payload['stash_id'] == 'stash@{0}'


def test_record_git_sandbox_started_writes_audit_event() -> None:
    audit = MagicMock()
    sandbox = GitBranchSandbox('/tmp', run_id='run1')

    record_git_sandbox_started(
        audit,
        'run1',
        sandbox,
        auto_stash=True,
        success=True,
    )

    audit.record.assert_called_once()
    args = audit.record.call_args
    assert args[0][0] == 'git_sandbox_started'
    assert args[0][1] == 'run1'
    assert args[1]['auto_stash'] is True
    assert args[1]['success'] is True


def test_record_git_sandbox_resolved_writes_audit_event() -> None:
    audit = MagicMock()
    sandbox = GitBranchSandbox('/tmp', run_id='run1')

    record_git_sandbox_resolved(
        audit,
        'run1',
        sandbox,
        resolution='discard',
        success=True,
    )

    audit.record.assert_called_once()
    args = audit.record.call_args
    assert args[0][0] == 'git_sandbox_resolved'
    assert args[1]['resolution'] == 'discard'


def test_extract_git_sandbox_from_audit_events() -> None:
    events = [
        {
            'event_type': 'git_sandbox_started',
            'payload': {
                'success': True,
                'auto_stash': True,
                'branch_name': 'teaagent-sandbox-run1',
                'original_branch': 'main',
                'stash_id': 'stash@{0}',
            },
        },
        {
            'event_type': 'git_sandbox_resolved',
            'payload': {
                'resolution': 'merge',
                'success': True,
                'branch_name': 'teaagent-sandbox-run1',
                'original_branch': 'main',
            },
        },
    ]

    evidence = extract_git_sandbox(events)

    assert evidence is not None
    assert evidence.started is True
    assert evidence.auto_stash is True
    assert evidence.resolution == 'merge'
    assert evidence.resolved is True
    assert evidence.success is True


def test_resolve_git_sandbox_discard_choice(monkeypatch) -> None:
    audit = MagicMock()
    sandbox = MagicMock()
    sandbox.is_available.return_value = True
    sandbox._original_branch = 'main'
    sandbox._branch_name = 'teaagent-sandbox-run1'
    sandbox._stash_id = None
    sandbox._run_id = 'run1'
    sandbox.discard.return_value = MagicMock(success=True, error=None)

    monkeypatch.setattr(
        'teaagent.cli._handlers._agent.sandbox_resolution.subprocess.run',
        MagicMock(return_value=MagicMock(stdout='')),
    )
    monkeypatch.setattr('builtins.input', lambda _prompt='': 'd')

    result = MagicMock(status='failed')
    args = MagicMock(root='/tmp')

    resolve_git_sandbox_after_run(
        audit=audit,
        run_id='run1',
        sandbox=sandbox,
        args=args,
        result=result,
        show_interactive_diff=lambda *_args, **_kwargs: True,
    )

    sandbox.discard.assert_called_once()
    audit.record.assert_called_once()
    assert audit.record.call_args[1]['resolution'] == 'discard'
