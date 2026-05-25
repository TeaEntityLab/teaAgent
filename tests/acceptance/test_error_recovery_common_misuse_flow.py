"""Common misuse paths return actionable remediation, not silent failure."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.cli import main
from teaagent.errors import BudgetExceededError, ToolPermissionError


def test_provider_missing_exits_with_setup_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('TEAAGENT_PROVIDER', raising=False)
    with pytest.raises(SystemExit) as exc:
        main(['agent', 'run', 'fix tests', '--root', str(tmp_path)])
    assert 'provider required' in str(exc.value).lower()
    assert 'teaagent setup' in str(exc.value).lower()


def test_budget_and_permission_errors_include_hints() -> None:
    budget = BudgetExceededError('iteration cap')
    permission = ToolPermissionError('denied by policy')
    assert '→' in str(budget)
    assert budget.hint
    assert '→' in str(permission)
    assert permission.hint


def test_preflight_surfaces_actionable_validation_for_empty_task(
    tmp_path: Path,
) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'preflight',
                'gpt',
                '',
                '--root',
                str(tmp_path),
            ]
        )
    text = out.getvalue().strip()
    assert code != 0 or 'task' in text.lower() or 'error' in text.lower()


def test_run_reports_adapter_failure_with_context(tmp_path: Path) -> None:
    class _BoomAdapter:
        def complete(self, request):  # noqa: ANN001, ARG002
            raise RuntimeError('provider unavailable')

    out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=_BoomAdapter()),
        redirect_stdout(out),
    ):
        code = main(
            [
                'agent',
                'run',
                'gpt',
                'Summarize README',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
                '--max-iterations',
                '2',
            ]
        )
    payload_text = out.getvalue()
    assert (
        code != 0
        or 'unavailable' in payload_text.lower()
        or 'error' in payload_text.lower()
    )


def test_read_only_run_blocks_workspace_write_via_cli(tmp_path: Path) -> None:
    (tmp_path / 'blocked.txt').write_text('keep\n', encoding='utf-8')
    adapter_calls = []

    class _WriteAttemptAdapter:
        def complete(self, request):  # noqa: ANN001
            adapter_calls.append(request)
            return (
                '{"type":"tool","tool_name":"workspace_write_file",'
                '"arguments":{"path":"blocked.txt","content":"changed\\n"},'
                '"call_id":"w1"}'
            )

    out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=_WriteAttemptAdapter()),
        redirect_stdout(out),
    ):
        code = main(
            [
                'agent',
                'run',
                'gpt',
                'Write blocked.txt',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
                '--max-iterations',
                '3',
                '--max-tool-calls',
                '3',
            ]
        )
    assert (tmp_path / 'blocked.txt').read_text(encoding='utf-8') == 'keep\n'
    assert code != 0 or 'permission' in out.getvalue().lower()
