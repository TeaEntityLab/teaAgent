"""P0-C-002: Regression tests for undo mechanism labeling."""

from __future__ import annotations

import base64
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import FakeAdapter

from teaagent.cli import main


def _run_agent_that_writes_files(tmp_path: Path) -> dict:
    existing = tmp_path / 'notes.txt'
    existing.write_text('before edit\n', encoding='utf-8')

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"after edit\\n"},"call_id":"w1"}',
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"new.txt","content":"created file\\n"},"call_id":"w2"}',
            '{"type":"final","content":"done"}',
        ]
    )

    run_out = io.StringIO()
    with redirect_stdout(run_out):
        run_code = main(
            [
                'run',
                'gpt',
                'Write two files',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'workspace-write',
                '--skip-plan-check',
                '--max-iterations',
                '6',
                '--max-tool-calls',
                '6',
            ],
            _adapter_factory=lambda _provider, model=None: adapter,
        )
    payload = json.loads(run_out.getvalue())
    assert run_code == 0
    return payload


class TestJournalUndoOutput:
    def test_journal_undo_output_contains_journal(self, tmp_path: Path) -> None:
        _run_agent_that_writes_files(tmp_path)

        undo_out = io.StringIO()
        with redirect_stdout(undo_out):
            undo_code = main(['undo', '--last', '--root', str(tmp_path)])
        undo_payload = json.loads(undo_out.getvalue())

        assert undo_code == 0
        assert undo_payload['status'] == 'restored'
        assert undo_payload['method'] == 'journal', (
            f"Expected method='journal', got method='{undo_payload.get('method')}'"
        )
        assert 'mechanism' in undo_payload
        assert undo_payload['mechanism'] == 'journal undo', (
            f"Expected mechanism='journal undo', got '{undo_payload.get('mechanism')}'"
        )

    def test_journal_undo_partial_names_mechanism(self, tmp_path: Path) -> None:
        _run_agent_that_writes_files(tmp_path)

        from teaagent.run_store import RunStore

        store = RunStore(tmp_path)
        run_id = store.latest_run_with_undo()
        assert run_id is not None
        undo_path = store.undo_path(run_id)

        lines = undo_path.read_text().strip().split('\n')
        corrupted = []
        for line in lines:
            obj = json.loads(line)
            if obj.get('content_b64'):
                obj['content_b64'] = base64.b64encode(b'corrupted').decode('ascii')
            corrupted.append(json.dumps(obj))
        undo_path.write_text('\n'.join(corrupted))

        undo_out = io.StringIO()
        with redirect_stdout(undo_out):
            _ = main(['undo', run_id, '--root', str(tmp_path)])
        undo_payload = json.loads(undo_out.getvalue())

        assert undo_payload['method'] == 'journal'
        assert undo_payload['mechanism'] == 'journal undo'


class TestCheckpointFallbackOutput:
    def test_checkpoint_fallback_output(self, tmp_path: Path, monkeypatch) -> None:
        _run_agent_that_writes_files(tmp_path)

        from teaagent.run_store import RunStore

        store = RunStore(tmp_path)
        run_id = store.latest_run_with_undo()
        assert run_id is not None

        store.undo_path(run_id).unlink()

        mock_sandbox = MagicMock()
        mock_sandbox.is_available.return_value = True
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.branch_name = 'teaagent-sandbox-test'
        mock_sandbox.rollback.return_value = mock_result

        with patch(
            'teaagent.cli.execution.GitBranchSandbox',
            return_value=mock_sandbox,
        ):
            undo_out = io.StringIO()
            with redirect_stdout(undo_out):
                undo_code = main(['undo', run_id, '--root', str(tmp_path)])
            undo_payload = json.loads(undo_out.getvalue())

        assert undo_code == 0
        assert undo_payload['method'] == 'checkpoint', (
            f"Expected method='checkpoint', got method='{undo_payload.get('method')}'"
        )
        assert undo_payload['mechanism'] == 'checkpoint restore', (
            f"Expected mechanism='checkpoint restore', got '{undo_payload.get('mechanism')}'"
        )
        assert undo_payload['status'] == 'restored'

    def test_old_method_git_never_appears(self, tmp_path: Path, monkeypatch) -> None:
        _run_agent_that_writes_files(tmp_path)

        from teaagent.run_store import RunStore

        store = RunStore(tmp_path)
        run_id = store.latest_run_with_undo()
        assert run_id is not None

        store.undo_path(run_id).unlink()

        mock_sandbox = MagicMock()
        mock_sandbox.is_available.return_value = True
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.branch_name = 'teaagent-sandbox-test'
        mock_sandbox.rollback.return_value = mock_result

        with patch(
            'teaagent.cli.execution.GitBranchSandbox',
            return_value=mock_sandbox,
        ):
            undo_out = io.StringIO()
            with redirect_stdout(undo_out):
                undo_code = main(['undo', run_id, '--root', str(tmp_path)])
            undo_payload = json.loads(undo_out.getvalue())

        assert undo_code == 0
        assert undo_payload.get('method') != 'git', (
            "method='git' is deprecated; must be 'checkpoint'"
        )


class TestUndoPreview:
    def test_undo_preview_shows_files(self, tmp_path: Path) -> None:
        _run_agent_that_writes_files(tmp_path)

        existing = tmp_path / 'notes.txt'
        new_file = tmp_path / 'new.txt'
        assert existing.read_text(encoding='utf-8') == 'after edit\n'
        assert new_file.is_file()

        preview_out = io.StringIO()
        with redirect_stdout(preview_out):
            preview_code = main(
                ['undo', '--last', '--preview', '--root', str(tmp_path)]
            )
        preview_text = preview_out.getvalue()

        assert preview_code == 0
        assert 'notes.txt' in preview_text
        assert 'new.txt' in preview_text
        assert existing.read_text(encoding='utf-8') == 'after edit\n'
        assert new_file.is_file()

    def test_undo_preview_with_explicit_run_id(self, tmp_path: Path) -> None:
        payload = _run_agent_that_writes_files(tmp_path)
        run_id = payload['run_id']

        preview_out = io.StringIO()
        with redirect_stdout(preview_out):
            preview_code = main(['undo', run_id, '--preview', '--root', str(tmp_path)])
        preview_text = preview_out.getvalue()

        assert preview_code == 0
        assert 'notes.txt' in preview_text
        assert 'new.txt' in preview_text
