"""CLI coverage for teaagent.cli._handlers._ergonomics."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from teaagent.cli import main
from teaagent.cli._handlers._ergonomics import (
    daily_journal_command,
    recipes_run_command,
    session_resume_command,
    status_short_command,
)
from teaagent.daily import build_daily_brief
from teaagent.ergonomics.daily_cost import daily_spend_cents, estimate_run_cost_cents
from teaagent.ergonomics.daily_journal import (
    render_daily_journal_markdown,
    write_daily_journal,
)
from teaagent.external_backends import register_code_parse_backend
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore
from teaagent.runner import RunResult
from tests.test_external_backends import _FakeCodeParse


def _git_env() -> dict[str, str]:
    import os

    return {
        **os.environ,
        'GIT_AUTHOR_NAME': 'TeaAgent Test',
        'GIT_AUTHOR_EMAIL': 'test@teaagent.test',
        'GIT_COMMITTER_NAME': 'TeaAgent Test',
        'GIT_COMMITTER_EMAIL': 'test@teaagent.test',
    }


def test_yesterday_recall_and_status_commands(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-ergo-cli')
    audit.record('run_started', 'run-ergo-cli', task='hello')
    audit.record('run_completed', 'run-ergo-cli', answer='ok')
    store.logger_for_result(
        RunResult(
            run_id='run-ergo-cli',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    (tmp_path / '.teaagent' / 'config.toml').parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / '.teaagent' / 'config.toml').write_text(
        'provider = "gpt"\n', encoding='utf-8'
    )

    for cmd in (
        ['yesterday', '--root', str(tmp_path)],
        ['recall', '--root', str(tmp_path), '--limit', '3'],
        ['status', '--root', str(tmp_path), '--provider', 'gpt'],
        ['guidance', '--root', str(tmp_path)],
        ['recipes', 'list'],
    ):
        out = io.StringIO()
        with redirect_stdout(out):
            assert main(cmd) == 0
        assert out.getvalue().strip()


def test_background_session_and_approval_commands(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['background', 'list', '--root', str(tmp_path)]) == 0
    assert json.loads(out.getvalue()) == []

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['background', 'show', 'missing', '--root', str(tmp_path)])
    assert code == 1

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-sess')
    audit.record('run_started', 'run-sess', task='t')
    store.logger_for_result(
        RunResult(
            run_id='run-sess',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['session', 'list', '--root', str(tmp_path)]) == 0
    rows = json.loads(out.getvalue())
    assert rows[0]['run_id'] == 'run-sess'

    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['session', 'show', 'run-sess', '--root', str(tmp_path)]) == 0
    assert json.loads(out.getvalue())['run_id'] == 'run-sess'

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'grant',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--scope',
                    'session',
                ]
            )
            == 0
        )
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'list', '--root', str(tmp_path)]) == 0
    policy = json.loads(out.getvalue())
    assert 'policy_order' in policy
    assert isinstance(policy['grants'], list)
    assert policy['grants'][0]['grant_id']

    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'list', '--grants-only', '--root', str(tmp_path)]) == 0
    grants_only = json.loads(out.getvalue())
    assert isinstance(grants_only, list)
    assert grants_only[0]['grant_id'] == policy['grants'][0]['grant_id']


def test_approval_check_and_revoke_cli(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'grant',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--scope',
                    'always',
                    '--path-glob',
                    'src/**',
                ]
            )
            == 0
        )
    grant_id = json.loads(out.getvalue())['grant_id']

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'check',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--path',
                    'src/a.py',
                ]
            )
            == 0
        )
    check_payload = json.loads(out.getvalue())
    assert check_payload['decision'] == 'allow'
    assert check_payload['allowed'] is True
    assert check_payload['matched_grant']['grant_id'] == grant_id
    assert check_payload['policy_order']

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'revoke',
                    grant_id,
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    assert json.loads(out.getvalue())['status'] == 'revoked'

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'approval',
                'revoke',
                'missing-grant-id',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 1
    assert json.loads(out.getvalue())['status'] == 'error'


def test_ci_review_print_only_and_journal(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    readme = tmp_path / 'README.md'
    readme.write_text('hello\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'init'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_git_env(),
    )
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'ci',
                    'review',
                    '--root',
                    str(tmp_path),
                    '--print-only',
                    '--diff-only',
                ]
            )
            == 0
        )
    payload = json.loads(out.getvalue())
    assert payload['recipe'] == 'review-staged'

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['journal', 'gpt', '--root', str(tmp_path), '--task', 'daily note'])
    assert code in (0, 2)
    journal_payload = json.loads(out.getvalue())
    assert journal_payload.get('ok') is True
    assert Path(journal_payload['path']).is_file()


def test_status_short_and_resume_missing_provider(tmp_path: Path) -> None:
    assert (
        status_short_command(
            argparse.Namespace(
                root=tmp_path,
                provider=None,
                model=None,
                run_id=None,
                permission_mode=None,
            )
        )
        == 1
    )
    out = io.StringIO()
    with redirect_stdout(out):
        code = session_resume_command(
            argparse.Namespace(
                root=tmp_path,
                run_id='run-x',
                provider=None,
                model=None,
                fresh_restart=False,
                permission_mode='prompt',
                _adapter_factory=None,
            )
        )
    assert code == 1
    assert 'provider required' in out.getvalue()

    out = io.StringIO()
    with redirect_stdout(out):
        code = recipes_run_command(
            argparse.Namespace(
                name='review-staged',
                root=tmp_path,
                provider=None,
                model=None,
                extra='',
                print_only=True,
                _adapter_factory=None,
            )
        )
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload['recipe'] == 'review-staged'


def test_recipes_run_invokes_agent_when_provider_set(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')
    with patch(
        'teaagent.cli._handlers._agent.agent_run_task', return_value=0
    ) as run_task:
        code = recipes_run_command(
            argparse.Namespace(
                name='review-staged',
                root=tmp_path,
                provider='gpt',
                model=None,
                extra='extra context',
                print_only=False,
                _adapter_factory=None,
            )
        )
    assert code == 0
    run_task.assert_called_once()


def test_ci_review_runs_agent_with_staged_diff(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    readme = tmp_path / 'README.md'
    readme.write_text('hello\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'init'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_git_env(),
    )
    readme.write_text('hello world\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=tmp_path, check=True, capture_output=True
    )
    with patch(
        'teaagent.cli._handlers._agent.agent_run_task', return_value=0
    ) as run_task:
        code = main(
            [
                'ci',
                'review',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--diff-only',
            ]
        )
    assert code == 0
    run_task.assert_called_once()


def test_daily_journal_command_requires_provider(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = daily_journal_command(
            argparse.Namespace(
                root=tmp_path,
                provider=None,
                task=None,
                model=None,
                permission_mode='prompt',
                context_profile='balanced',
            )
        )
    assert code == 1
    assert 'provider required' in out.getvalue()


def test_register_code_parse_backend_rejects_empty_name() -> None:
    import pytest

    with pytest.raises(ValueError, match='non-empty'):
        register_code_parse_backend('  ', _FakeCodeParse())


def test_daily_journal_render_and_cost_helpers(tmp_path: Path) -> None:
    brief = build_daily_brief(
        task='cost',
        root=tmp_path,
        provider='gpt',
        permission_mode=PermissionMode.PROMPT,
    )
    text = render_daily_journal_markdown(brief)
    assert 'TeaAgent Daily' in text
    path = write_daily_journal(brief, root=tmp_path, payload={'ok': True})
    assert path.with_suffix('.json').is_file()
    assert (
        estimate_run_cost_cents(
            [
                {
                    'event_type': 'run_started',
                    'payload': {'provider': 'gpt', 'model': 'm'},
                }
            ]
        )
        >= 0.0
    )
    assert daily_spend_cents(tmp_path) >= 0.0


def test_approval_check_with_arg_flags(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Grant with path glob
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'grant',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--scope',
                    'always',
                    '--path-glob',
                    'src/**',
                ]
            )
            == 0
        )

    # Check with --arg flag
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'check',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arg',
                    'path=src/a.py',
                ]
            )
            == 0
        )
    check_payload = json.loads(out.getvalue())
    assert check_payload['decision'] == 'allow'
    assert check_payload['allowed'] is True

    # Check with --arguments-json flag
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'check',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arguments-json',
                    '{"path": "src/b.py"}',
                ]
            )
            == 0
        )
    check_payload = json.loads(out.getvalue())
    assert check_payload['decision'] == 'allow'

    # Check with mismatching path
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'check',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arg',
                    'path=other/file.txt',
                ]
            )
            == 0
        )
    check_payload = json.loads(out.getvalue())
    assert check_payload['decision'] == 'prompt'


def test_approval_explain_with_mismatch_reasons(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Grant with specific path
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'grant',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--scope',
                    'always',
                    '--path-glob',
                    'src/**',
                ]
            )
            == 0
        )

    # Explain with matching path
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'explain',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arg',
                    'path=src/a.py',
                ]
            )
            == 0
        )
    explain_payload = json.loads(out.getvalue())
    assert explain_payload['decision'] == 'allow'
    assert explain_payload['summary']
    assert 'Allowed by matching' in explain_payload['summary']

    # Explain with mismatching path
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'explain',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arg',
                    'path=other/file.txt',
                ]
            )
            == 0
        )
    explain_payload = json.loads(out.getvalue())
    assert explain_payload['decision'] == 'prompt'
    assert explain_payload['summary']
    assert 'reason' in explain_payload['evaluated_grants'][0]


def test_approval_pending_and_approve_workflow(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Create a run with pending approval
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-pending')
    audit.record('run_started', 'run-pending', task='test')
    audit.record(
        'tool_call_pending_approval',
        'run-pending',
        call_id='call-123',
        tool_name='workspace_write_file',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-pending',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )

    # List pending approvals
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--root', str(tmp_path)]) == 0
    pending_payload = json.loads(out.getvalue())
    assert len(pending_payload) == 1
    assert pending_payload[0]['run_id'] == 'run-pending'
    assert pending_payload[0]['pending_approval']['call_id'] == 'call-123'

    # Approve without resume
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'approve', 'call-123', '--root', str(tmp_path)]) == 0
    approve_payload = json.loads(out.getvalue())
    assert approve_payload['status'] == 'approved'
    assert approve_payload['call_id'] == 'call-123'


def test_approval_preset_and_doctor(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Apply dev-safe preset
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'preset', 'dev-safe', '--root', str(tmp_path)]) == 0
    preset_payload = json.loads(out.getvalue())
    assert preset_payload['status'] == 'applied'
    assert preset_payload['preset'] == 'dev-safe'
    assert len(preset_payload['grants_applied']) > 0

    # Run doctor
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'doctor', '--root', str(tmp_path)]) == 0
    doctor_payload = json.loads(out.getvalue())
    assert doctor_payload['status'] in ('healthy', 'issues_found')
    assert 'total_grants' in doctor_payload
    assert 'issues' in doctor_payload
    assert 'suggestions' in doctor_payload


def test_approval_check_invalid_json(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Invalid JSON
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'approval',
                'check',
                'workspace_write_file',
                '--root',
                str(tmp_path),
                '--arguments-json',
                'invalid json',
            ]
        )
    assert code == 1
    error_payload = json.loads(out.getvalue())
    assert error_payload['status'] == 'error'

    # Invalid --arg format
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'approval',
                'check',
                'workspace_write_file',
                '--root',
                str(tmp_path),
                '--arg',
                'invalid-format',
            ]
        )
    assert code == 1
    error_payload = json.loads(out.getvalue())
    assert error_payload['status'] == 'error'


def test_approval_preset_uses_correct_tool_names(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Apply dev-safe preset
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'preset', 'dev-safe', '--root', str(tmp_path)]) == 0
    preset_payload = json.loads(out.getvalue())
    assert preset_payload['status'] == 'applied'

    # Verify workspace_run_shell_mutate is used instead of bash
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'list', '--root', str(tmp_path)]) == 0
    list_payload = json.loads(out.getvalue())
    tool_names = [g['tool_name'] for g in list_payload['grants']]
    assert 'workspace_run_shell_mutate' in tool_names
    assert 'bash' not in tool_names


def test_approval_approve_persists_state(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Create a run with pending approval
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-approve-persist')
    audit.record('run_started', 'run-approve-persist', task='test')
    audit.record(
        'tool_call_pending_approval',
        'run-approve-persist',
        call_id='call-456',
        tool_name='workspace_write_file',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-approve-persist',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )

    # Approve without resume
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'approve', 'call-456', '--root', str(tmp_path)]) == 0
    approve_payload = json.loads(out.getvalue())
    assert approve_payload['status'] == 'approved'

    # Verify pending approval is cleared
    out = io.StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--root', str(tmp_path)]) == 0
    pending_payload = json.loads(out.getvalue())
    assert len(pending_payload) == 0


def test_approval_explain_shows_expired_and_mode_mismatch(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    # Create an expired grant using ttl_hours
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    store = ApprovalPresetStore(tmp_path)
    # Use negative ttl_hours to create an expired grant
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['src/**'],
        ttl_hours=-1.0,
    )

    # Create a mode-mismatched grant
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['src/**'],
        permission_mode='read-only',
    )

    # Explain should show these inactive grants with reasons
    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'explain',
                    'workspace_write_file',
                    '--root',
                    str(tmp_path),
                    '--arg',
                    'path=src/a.py',
                ]
            )
            == 0
        )
    explain_payload = json.loads(out.getvalue())
    # Should have evaluated grants including expired/mode-mismatched ones
    assert len(explain_payload['evaluated_grants']) >= 2
    # Check for expired reason
    reasons = [
        g.get('reason') for g in explain_payload['evaluated_grants'] if g.get('reason')
    ]
    assert 'expired' in reasons or 'permission_mode_mismatch' in reasons
