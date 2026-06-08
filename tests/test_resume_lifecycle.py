"""Acceptance tests for resume/background lifecycle (P1-A-004).

Tests cover:
- resumable flag on RunSummary
- --background rejects run/suspension IDs
- Help text clarifies suspend vs background execution
- Suspend to review to resume state transitions
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli._agent_parsers import _interactive_review
from teaagent.cli._handlers._agent import agent_run_task
from teaagent.run_store import RunStore, RunSummary
from teaagent.types import FinalAnswer, RunResult

# ---- resumable flag on RunSummary (P1-A-003) ----


def test_run_summary_resumable_for_running_run():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'run-r', task='in-progress task')
        store.logger_for_result(
            RunResult(
                run_id='run-r',
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='running',
            ),
            audit,
        )
        summaries = store.list_runs()
        assert len(summaries) == 1
        assert summaries[0].resumable is True


def test_run_summary_resumable_for_paused_run():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'run-p', task='write')
        audit.record(
            'run_paused',
            'run-p',
            status='pending_approval',
            approval={'call_id': 'write-1'},
        )
        store.logger_for_result(
            RunResult(
                run_id='run-p',
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='pending_approval',
            ),
            audit,
        )
        summaries = store.list_runs()
        assert len(summaries) == 1
        assert summaries[0].resumable is True


def test_run_summary_not_resumable_for_completed_run():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'run-c', task='done')
        audit.record('run_completed', 'run-c', answer='ok', metadata={})
        store.logger_for_result(
            RunResult(
                run_id='run-c',
                final_answer=FinalAnswer('ok'),
                iterations=1,
                tool_calls=0,
                status='completed',
            ),
            audit,
        )
        summaries = store.list_runs()
        assert len(summaries) == 1
        assert summaries[0].resumable is False


def test_run_summary_not_resumable_for_failed_run():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'run-f', task='bad')
        audit.record('run_failed', 'run-f', category='model_logic', message='x')
        store.logger_for_result(
            RunResult(
                run_id='run-f',
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='failed:model_logic',
            ),
            audit,
        )
        summaries = store.list_runs()
        assert len(summaries) == 1
        assert summaries[0].resumable is False


def test_run_summary_to_dict_includes_resumable():
    summary = RunSummary(
        run_id='test-id',
        task='test task',
        status='running',
        created_at='2026-01-01T00:00:00Z',
        updated_at='2026-01-01T00:00:00Z',
        path=Path('/tmp/test.jsonl'),
        resumable=True,
    )
    d = summary.to_dict()
    assert 'resumable' in d
    assert d['resumable'] is True


def test_run_summary_default_resumable_is_false():
    summary = RunSummary(
        run_id='test-id',
        task='test task',
        status='completed',
        created_at='2026-01-01T00:00:00Z',
        updated_at='2026-01-01T00:00:00Z',
        path=Path('/tmp/test.jsonl'),
    )
    assert summary.resumable is False


# ---- --background rejects run/suspension IDs (P1-A-002) ----


def test_background_rejects_existing_run_id_in_task_position(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'existing-run', task='some task')
        audit.record('run_completed', 'existing-run', answer='done', metadata={})
        store.logger_for_result(
            RunResult(
                run_id='existing-run',
                final_answer=FinalAnswer('done'),
                iterations=1,
                tool_calls=0,
                status='completed',
            ),
            audit,
        )

        args = _make_background_args(tmp, task='existing-run')
        result = agent_run_task(args)
        captured = capsys.readouterr()

        assert result == 2
        assert 'existing run id' in captured.out.lower()
        assert 'agent resume' in captured.out


def test_background_rejects_existing_run_id_in_provider_position(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'provider-run', task='some task')
        audit.record('run_completed', 'provider-run', answer='done', metadata={})
        store.logger_for_result(
            RunResult(
                run_id='provider-run',
                final_answer=FinalAnswer('done'),
                iterations=1,
                tool_calls=0,
                status='completed',
            ),
            audit,
        )

        args = _make_background_args(tmp, provider='provider-run', task=None)
        result = agent_run_task(args)
        captured = capsys.readouterr()

        assert result == 2
        assert 'existing run id' in captured.out.lower()


def test_background_rejects_suspension_id_in_task_position(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        tea_dir = Path(tmp) / '.teaagent'
        tea_dir.mkdir()
        (tea_dir / 'suspension-sus-1.json').write_text('{}', encoding='utf-8')

        args = _make_background_args(tmp, task='sus-1')
        result = agent_run_task(args)
        captured = capsys.readouterr()

        assert result == 2
        assert 'suspension id' in captured.out.lower()
        assert 'interactive-review' in captured.out


def test_background_rejects_suspension_id_in_provider_position(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        tea_dir = Path(tmp) / '.teaagent'
        tea_dir.mkdir()
        safe_id = 'sus-provider'.replace('.', '-')
        (tea_dir / f'suspension-{safe_id}.json').write_text('{}', encoding='utf-8')

        args = _make_background_args(tmp, provider=safe_id, task=None)
        result = agent_run_task(args)
        captured = capsys.readouterr()

        assert result == 2
        assert 'suspension id' in captured.out.lower()


def test_background_allows_legitimate_task(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        args = _make_background_args(tmp, task='legitimate task string')

        with patch(
            'teaagent.ergonomics.background_run.BackgroundRunStore'
        ) as mock_bg_store_class:
            mock_bg_store = MagicMock()
            mock_bg_store.start.return_value = MagicMock(
                to_dict=lambda: {
                    'background_id': 'bg-1',
                    'pid': 12345,
                    'log_path': '/tmp/log',
                }
            )
            mock_bg_store_class.return_value = mock_bg_store

            with (
                patch(
                    'teaagent.cli._handlers._agent._prepare_task',
                    return_value='legitimate task string',
                ),
                patch(
                    'teaagent.ergonomics.background_run.build_agent_run_command',
                    return_value='fake-command',
                ),
            ):
                result = agent_run_task(args)
                captured = capsys.readouterr()

                assert result == 0
                assert 'background_started' in captured.out


# ---- Help text clarifies suspend vs background (P1-A-001) ----


def test_background_flag_help_text_mentions_detached_subprocess():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='agent_command', required=True)
    p = subs.add_parser('run')
    from teaagent.cli._agent_parsers import add_agent_run_arguments

    add_agent_run_arguments(p)
    help_text = p.format_help()
    assert 'detached subprocess' in help_text
    assert 'Run detached' not in help_text


def test_interactive_review_help_text_uses_suspended():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='agent_command', required=True)

    def dummy_handler(_args):
        pass

    _interactive_review(subs, dummy_handler)
    help_text = parser.format_help()
    assert 'suspended' in help_text
    assert 'background task' not in help_text.lower()


# ---- Suspend, review, resume state transitions (P1-A-004) ----


def test_suspend_to_background_preserves_resumability(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        config = ChatAgentConfig.from_root(tmp)
        from teaagent.cli._handlers.chat_repl import suspend_to_background

        session_context = {
            'observations': [{'task': 'test suspension'}],
            'compaction_count': 0,
        }
        run_id = suspend_to_background(config, session_context, set())
        captured = capsys.readouterr()

        assert run_id
        assert 'suspension checkpoint' in captured.out
        assert 'interactive-review' in captured.out
        assert '--background' not in captured.out
        assert 'Session suspended successfully' in captured.out

        suspension_file = Path(tmp) / '.teaagent' / f'suspension-{run_id}.json'
        assert suspension_file.exists()
        data = json.loads(suspension_file.read_text())
        assert data['mode'] == 'suspended_from_repl'


def test_interactive_review_with_suspended_run_no_changes(capsys):
    import subprocess

    from teaagent.cli._handlers.agent_review import interactive_review_mode

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['git', 'init'], cwd=tmp, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmp,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmp, capture_output=True
        )
        (Path(tmp) / 'test.txt').write_text('initial')
        subprocess.run(['git', 'add', '.'], cwd=tmp, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmp, capture_output=True)

        tea_dir = Path(tmp) / '.teaagent'
        tea_dir.mkdir(parents=True, exist_ok=True)
        (tea_dir / 'suspension-suspended-1.json').write_text(
            json.dumps(
                {
                    'run_id': 'suspended-1',
                    'timestamp': __import__('time').time(),
                    'acp_version': '1.0.0',
                    'mode': 'suspended_from_repl',
                    'config': {},
                    'session_context': {'observations_count': 0, 'compaction_count': 0},
                    'targeted_files': [],
                }
            )
        )

        result = interactive_review_mode(tmp, 'suspended-1')
        captured = capsys.readouterr()
        assert result == 0
        assert 'No changes detected to review' in captured.out


def test_interactive_review_missing_suspension_file(capsys):
    import subprocess

    from teaagent.cli._handlers.agent_review import interactive_review_mode

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['git', 'init'], cwd=tmp, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmp,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmp, capture_output=True
        )
        (Path(tmp) / 'test.txt').write_text('content')
        subprocess.run(['git', 'add', '.'], cwd=tmp, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmp, capture_output=True)

        result = interactive_review_mode(tmp, 'nonexistent-run')
        captured = capsys.readouterr()
        assert result == 1
        assert 'Suspension file not found' in captured.out


def test_resume_requires_run_started_task():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger()
        audit.record('run_started', 'no-task-run', task='')
        audit.record('run_completed', 'no-task-run', answer='done', metadata={})
        store.logger_for_result(
            RunResult(
                run_id='no-task-run',
                final_answer=FinalAnswer('done'),
                iterations=1,
                tool_calls=0,
                status='completed',
            ),
            audit,
        )
        with pytest.raises(ValueError, match='no run_started task'):
            store.task_for_run('no-task-run')


def test_full_lifecycle_suspend_review_refuse_background(capsys):
    import subprocess

    from teaagent.cli._handlers.agent_review import interactive_review_mode
    from teaagent.cli._handlers.chat_repl import suspend_to_background

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['git', 'init'], cwd=tmp, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmp,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmp, capture_output=True
        )
        (Path(tmp) / 'test.txt').write_text('initial')
        subprocess.run(['git', 'add', '.'], cwd=tmp, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=tmp, capture_output=True)

        config = ChatAgentConfig.from_root(tmp)
        session_context = {'observations': [], 'compaction_count': 0}
        run_id = suspend_to_background(config, session_context, set())
        assert run_id

        result = interactive_review_mode(tmp, run_id)
        _ = capsys.readouterr()
        assert result == 0

        safe_id = run_id.replace('.', '-')
        tea_dir = Path(tmp) / '.teaagent'
        (tea_dir / f'suspension-{safe_id}.json').write_text(
            json.dumps(
                {
                    'run_id': run_id,
                    'timestamp': __import__('time').time(),
                    'acp_version': '1.0.0',
                    'mode': 'suspended_from_repl',
                }
            )
        )

        args = _make_background_args(tmp, task=run_id)
        result = agent_run_task(args)
        captured = capsys.readouterr()
        assert result == 2
        assert (
            'suspension id' in captured.out.lower()
            or 'existing run id' in captured.out.lower()
        )


# ---- Helpers ----


def _make_background_args(root, *, task='test task', provider='gpt', model=None):
    return argparse.Namespace(
        root=root,
        task=task,
        provider=provider,
        model=model,
        background=True,
        route_model=False,
        max_iterations=10,
        max_tool_calls=10,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode='prompt',
        subagent=False,
        max_subagent_depth=1,
        heartbeat=0.0,
        code_analysis=False,
        context_profile='balanced',
        max_estimated_cost_cents=0,
    )
