# test-type: behavior
"""Focused regression tests for G2, G3 and G22 dogfood decisions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli._handlers._agent.resume import suspend_to_background
from teaagent.cli._handlers._agent.sandbox_resolution import (
    record_git_sandbox_resolved,
)
from teaagent.git_sandbox import GitBranchSandbox
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_rollback_refuses_when_head_not_on_sandbox_branch(tmp_path: Path) -> None:
    """G2: rollback() must not reset the original branch after keep()."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    file = tmp_path / 'notes.txt'
    file.write_text('original\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'notes.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    sandbox = GitBranchSandbox(tmp_path, run_id='g2-run')
    start = sandbox.start()
    assert start.success

    # Simulate a completed headless run: switch back to main and add new work.
    subprocess.run(
        ['git', 'checkout', 'main'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    file.write_text('new uncommitted work\n', encoding='utf-8')

    rollback = sandbox.rollback()
    assert not rollback.success
    assert 'not the sandbox branch' in rollback.error.lower()

    # The uncommitted work on main must survive.
    assert file.read_text(encoding='utf-8') == 'new uncommitted work\n'


def test_sandbox_stores_original_sha_for_preview_diff(tmp_path: Path) -> None:
    """G2: sandbox captures the original SHA at start."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    (tmp_path / 'notes.txt').write_text('original\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'notes.txt'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Record the original SHA before starting the sandbox.
    head = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    sandbox = GitBranchSandbox(tmp_path, run_id='g2-run')
    start = sandbox.start()
    assert start.success
    assert sandbox._original_sha == head


def test_git_sandbox_resolved_lands_in_real_run_file(tmp_path: Path) -> None:
    """G22: git_sandbox_resolved must be promoted with the run's audit file."""
    store = RunStore(tmp_path)
    pending_audit = store.audit_logger()

    # Record a tool event during the run.
    pending_audit.record(
        'tool_call_started',
        'g22-run',
        tool_name='workspace_write_file',
        call_id='write-1',
    )

    # Sandbox resolution happens while the audit is still the pending temp.
    sandbox = GitBranchSandbox(tmp_path, run_id='g22-run')
    sandbox._original_branch = 'main'
    sandbox._stash_id = None
    record_git_sandbox_resolved(
        pending_audit,
        'g22-run',
        sandbox,
        resolution='keep',
        success=True,
    )

    # Promote the pending audit to the real run file.
    result = RunResult(
        run_id='g22-run',
        final_answer=None,
        iterations=1,
        tool_calls=1,
        status='completed',
    )
    store.logger_for_result(result, pending_audit)

    events = store.show_run('g22-run')
    types = {e.get('event_type') for e in events}
    assert 'tool_call_started' in types
    assert 'git_sandbox_resolved' in types


def test_session_suspended_lands_in_run_file(tmp_path: Path) -> None:
    """G22: REPL suspension writes session_suspended to the real run file."""
    config = ChatAgentConfig(root=tmp_path)
    run_id = suspend_to_background(
        config,
        {'observations': [], 'compaction_count': 0},
        set(),
        output=lambda _m: None,
    )
    assert run_id

    store = RunStore(tmp_path)
    events = store.show_run(run_id)
    assert any(e.get('event_type') == 'session_suspended' for e in events)
