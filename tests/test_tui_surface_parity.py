"""Tests for TUI surface parity features: approve --selector, progress <run_id>, receipt <run_id>."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from teaagent.run_store import RunStore
from teaagent.tui import TeaAgentTUI
from teaagent.tui._commands import _COMMAND_DISPATCH


def _seed_run_events(runs_dir: Path, run_id: str, events: list[dict]) -> None:
    """Write a JSONL run file into the runs directory."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event) for event in events]
    (runs_dir / f'{run_id}.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _rewrite_index(store_dir: Path, runs_dir: Path) -> None:
    """Force a fresh runs-index.jsonl from globbed run files.

    RunStore._read_index reads from the index file; when no index exists,
    list_runs() falls back to globbing.  Seeding one avoids the summarize()
    path for zero-event or partial files.
    """
    index_path = store_dir / 'runs-index.jsonl'
    entries: list[dict] = []
    for path in sorted(runs_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime):
        store = RunStore(runs_dir.parent.parent)
        summary = store.summarize(path)
        if summary is not None:
            entries.append(summary.to_dict())
    index_path.write_text(
        '\n'.join(json.dumps(e) for e in entries) + '\n', encoding='utf-8'
    )


class ApproveSelectorTests(unittest.TestCase):
    def test_approve_selector_selects_pending_approval(self) -> None:
        """approve --selector 1 approves the first pending call_id."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            _seed_run_events(
                runs_dir,
                'run-1',
                [
                    {
                        'event_type': 'run_started',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:00:00Z',
                        'payload': {'task': 'write file'},
                    },
                    {
                        'event_type': 'tool_call_pending_approval',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:01:00Z',
                        'payload': {
                            'call_id': 'call-abc123',
                            'tool_name': 'workspace_write_file',
                            'reason': 'destructive write',
                            'arguments': {'path': 'foo.txt'},
                        },
                    },
                ],
            )
            _rewrite_index(root / '.teaagent', runs_dir)

            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('approve --selector 1')
            self.assertTrue(result)
            self.assertIn('call-abc123', output[0])
            self.assertIn('via selector 1', output[0])

    def test_approve_selector_out_of_range(self) -> None:
        """approve --selector with out-of-range number returns error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            _seed_run_events(
                runs_dir,
                'run-1',
                [
                    {
                        'event_type': 'run_started',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:00:00Z',
                        'payload': {'task': 'write file'},
                    },
                    {
                        'event_type': 'tool_call_pending_approval',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:01:00Z',
                        'payload': {
                            'call_id': 'call-abc123',
                            'tool_name': 'workspace_write_file',
                            'reason': 'destructive write',
                            'arguments': {'path': 'foo.txt'},
                        },
                    },
                ],
            )
            _rewrite_index(root / '.teaagent', runs_dir)

            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('approve --selector 99')
            self.assertTrue(result)
            self.assertIn('out of range', output[0])

    def test_approve_selector_no_pending_approvals(self) -> None:
        """approve --selector when no pending approvals returns error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            _seed_run_events(
                runs_dir,
                'run-1',
                [
                    {
                        'event_type': 'run_started',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:00:00Z',
                        'payload': {'task': 'write file'},
                    },
                    {
                        'event_type': 'tool_call_approved',
                        'run_id': 'run-1',
                        'created_at': '2026-06-07T00:02:00Z',
                        'payload': {
                            'call_id': 'call-abc123',
                            'tool_name': 'workspace_write_file',
                        },
                    },
                ],
            )
            _rewrite_index(root / '.teaagent', runs_dir)

            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('approve --selector 1')
            self.assertTrue(result)
            self.assertIn('no pending approvals', output[0])

    def test_approve_selector_non_integer(self) -> None:
        """approve --selector with non-integer returns error."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        result = tui.handle_command('approve --selector abc')
        self.assertTrue(result)
        self.assertIn('selector must be an integer', output[0])

    def test_approve_call_id_still_works(self) -> None:
        """approve <call_id> backward compat works."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        result = tui.handle_command('approve write-1')
        self.assertTrue(result)
        self.assertEqual(output[0], 'approved: write-1')
        self.assertIn('write-1', tui.approved_call_ids)


class ProgressRunIdTests(unittest.TestCase):
    def _seed_run(self, runs_dir: Path, run_id: str) -> None:
        _seed_run_events(
            runs_dir,
            run_id,
            [
                {
                    'event_type': 'run_started',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:00Z',
                    'payload': {
                        'task': 'analyze code',
                        'max_estimated_cost_cents': 1000,
                    },
                },
                {
                    'event_type': 'iteration_started',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:10Z',
                    'payload': {'iteration': 1},
                },
                {
                    'event_type': 'tool_call_started',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:11Z',
                    'payload': {'tool_name': 'workspace_read_file'},
                },
                {
                    'event_type': 'tool_call_completed',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:12Z',
                    'payload': {'tool_name': 'workspace_read_file'},
                },
                {
                    'event_type': 'run_completed',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:01:00Z',
                    'payload': {'cost_cents': 42},
                },
            ],
        )

    def test_progress_run_id_shows_formatted_output(self) -> None:
        """progress <run_id> shows Phase and Budget fields."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            self._seed_run(runs_dir, 'run-1')
            _rewrite_index(root / '.teaagent', runs_dir)

            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('progress run-1')
            self.assertTrue(result)
            progress_output = output[0]
            self.assertIn('Phase:', progress_output)
            self.assertIn('Budget:', progress_output)
            self.assertIn('run-1', progress_output)

    def test_progress_run_id_not_found(self) -> None:
        """progress <run_id> with non-existent run returns error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('progress run-does-not-exist')
            self.assertTrue(result)
            self.assertIn('not found', output[0])

    def test_progress_on_off_toggle_still_works(self) -> None:
        """progress on/off toggle backward compat works."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        self.assertTrue(tui.handle_command('progress on'))
        self.assertTrue(tui.progress)
        self.assertIn('progress: on', output[0])

        self.assertTrue(tui.handle_command('progress off'))
        self.assertFalse(tui.progress)


class ReceiptTests(unittest.TestCase):
    def _seed_run(self, runs_dir: Path, run_id: str) -> None:
        _seed_run_events(
            runs_dir,
            run_id,
            [
                {
                    'event_type': 'run_started',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:00Z',
                    'payload': {
                        'task': 'analyze code',
                        'provider': 'gpt',
                        'model': 'gpt-4',
                    },
                },
                {
                    'event_type': 'tool_call_started',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:10Z',
                    'payload': {'tool_name': 'workspace_read_file'},
                },
                {
                    'event_type': 'tool_call_completed',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:00:11Z',
                    'payload': {'tool_name': 'workspace_read_file'},
                },
                {
                    'event_type': 'run_completed',
                    'run_id': run_id,
                    'created_at': '2026-06-07T00:01:00Z',
                    'payload': {'cost_cents': 42},
                },
            ],
        )

    def test_receipt_run_id_shows_formatted_receipt(self) -> None:
        """receipt <run_id> shows goal, cost, and audit path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_dir = root / '.teaagent' / 'runs'
            self._seed_run(runs_dir, 'run-1')
            _rewrite_index(root / '.teaagent', runs_dir)

            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('receipt run-1')
            self.assertTrue(result)
            receipt_output = output[0]
            self.assertIn('Run receipt:', receipt_output)
            self.assertIn('Goal:', receipt_output)
            self.assertIn('Cost:', receipt_output)
            self.assertIn('Audit log:', receipt_output)

    def test_receipt_run_id_not_found(self) -> None:
        """receipt <run_id> with non-existent run returns not-found."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            tui = TeaAgentTUI(
                root=root, input_fn=lambda _prompt: 'exit', output_fn=output.append
            )
            result = tui.handle_command('receipt run-does-not-exist')
            self.assertTrue(result)
            self.assertIn('not found', output[0])

    def test_receipt_without_args(self) -> None:
        """receipt without args returns error."""
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)
        result = tui.handle_command('receipt')
        self.assertTrue(result)
        self.assertIn('requires a run id', output[0])


class DispatchRegistrationTests(unittest.TestCase):
    def test_receipt_in_command_dispatch(self) -> None:
        """receipt is registered in _COMMAND_DISPATCH."""
        self.assertIn('receipt', _COMMAND_DISPATCH)
        self.assertTrue(callable(_COMMAND_DISPATCH['receipt']))

    def test_approve_in_command_dispatch(self) -> None:
        """approve remains registered in _COMMAND_DISPATCH."""
        self.assertIn('approve', _COMMAND_DISPATCH)
        self.assertTrue(callable(_COMMAND_DISPATCH['approve']))

    def test_progress_in_command_dispatch(self) -> None:
        """progress remains registered in _COMMAND_DISPATCH."""
        self.assertIn('progress', _COMMAND_DISPATCH)
        self.assertTrue(callable(_COMMAND_DISPATCH['progress']))


if __name__ == '__main__':
    unittest.main()
