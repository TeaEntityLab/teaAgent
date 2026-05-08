from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent import FinalAnswer, RunStore
from teaagent.cli import main
from teaagent.runner import RunResult


class RunStoreTests(unittest.TestCase):
    def test_run_store_persists_and_summarizes_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-1', task='demo')
            audit.record('run_completed', 'run-1', answer='done', metadata={})
            result = RunResult(
                run_id='run-1',
                final_answer=FinalAnswer('done'),
                iterations=1,
                tool_calls=0,
                status='completed',
            )

            store.logger_for_result(result, audit)
            summaries = store.list_runs()
            events = store.show_run('run-1')

            self.assertEqual(summaries[0].run_id, 'run-1')
            self.assertEqual(summaries[0].status, 'completed')
            self.assertEqual(summaries[0].final_answer, 'done')
            self.assertEqual(events[0]['event_type'], 'run_started')
            self.assertTrue((Path(tmp) / '.teaagent' / 'runs' / 'run-1.jsonl').exists())

    def test_task_for_run_extracts_original_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-task', task='resume me')
            audit.record('run_completed', 'run-task', answer='ok', metadata={})
            store.logger_for_result(
                RunResult(
                    run_id='run-task',
                    final_answer=FinalAnswer('ok'),
                    iterations=1,
                    tool_calls=0,
                    status='completed',
                ),
                audit,
            )

            self.assertEqual(store.task_for_run('run-task'), 'resume me')

    def test_cli_lists_and_shows_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-2', task='demo')
            audit.record('run_failed', 'run-2', category='model_logic', message='x')
            store.logger_for_result(
                RunResult(
                    run_id='run-2',
                    final_answer=None,
                    iterations=1,
                    tool_calls=0,
                    status='failed:model_logic',
                ),
                audit,
            )

            list_output = io.StringIO()
            show_output = io.StringIO()
            with redirect_stdout(list_output):
                list_code = main(['agent', 'runs', '--root', tmp])
            with redirect_stdout(show_output):
                show_code = main(['agent', 'show', 'run-2', '--root', tmp])

            self.assertEqual(list_code, 0)
            self.assertEqual(show_code, 0)
            self.assertEqual(json.loads(list_output.getvalue())[0]['run_id'], 'run-2')
            self.assertEqual(
                json.loads(show_output.getvalue())[1]['event_type'], 'run_failed'
            )

    def test_list_runs_skips_corrupt_jsonl_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-ok', task='demo')
            audit.record('run_completed', 'run-ok', answer='ok', metadata={})
            store.logger_for_result(
                RunResult(
                    run_id='run-ok',
                    final_answer=FinalAnswer('ok'),
                    iterations=1,
                    tool_calls=0,
                    status='completed',
                ),
                audit,
            )
            (Path(tmp) / '.teaagent' / 'runs' / 'broken.jsonl').write_text(
                'not json\n', encoding='utf-8'
            )

            summaries = store.list_runs()

            self.assertEqual([summary.run_id for summary in summaries], ['run-ok'])

    def test_list_runs_skips_records_without_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            (Path(tmp) / '.teaagent' / 'runs' / 'missing-id.jsonl').write_text(
                json.dumps({'event_type': 'run_started', 'payload': {'task': 'x'}})
                + '\n',
                encoding='utf-8',
            )

            self.assertEqual(store.list_runs(), [])

    def test_run_paused_summarizes_as_pending_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-paused', task='write')
            audit.record(
                'run_paused',
                'run-paused',
                status='pending_approval',
                approval={'call_id': 'write-1'},
            )
            store.logger_for_result(
                RunResult(
                    run_id='run-paused',
                    final_answer=None,
                    iterations=1,
                    tool_calls=0,
                    status='pending_approval',
                ),
                audit,
            )

            self.assertEqual(store.list_runs()[0].status, 'pending_approval')
            self.assertEqual(
                store.heartbeat_for_run('run-paused')['status'], 'pending_approval'
            )

    def test_observations_for_run_returns_completed_tool_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-obs', task='read')
            audit.record(
                'tool_call_completed',
                'run-obs',
                call_id='r1',
                tool_name='workspace_read_file',
                result={'path': 'a.txt', 'content': 'hi', 'truncated': False},
            )
            audit.record(
                'tool_call_completed',
                'run-obs',
                call_id='r2',
                tool_name='workspace_read_file',
                result={'path': 'b.txt', 'content': 'yo', 'truncated': False},
            )
            store.logger_for_result(
                RunResult(
                    run_id='run-obs',
                    final_answer=None,
                    iterations=2,
                    tool_calls=2,
                    status='pending_approval',
                ),
                audit,
            )

            observations = store.observations_for_run('run-obs')

            self.assertEqual([obs['call_id'] for obs in observations], ['r1', 'r2'])
            self.assertEqual(observations[0]['result']['content'], 'hi')

    def test_pending_approval_for_run_returns_last_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-pend', task='write')
            audit.record(
                'tool_call_pending_approval',
                'run-pend',
                call_id='write-1',
                tool_name='workspace_write_file',
                arguments={'path': 'x.txt', 'content': 'x'},
            )
            store.logger_for_result(
                RunResult(
                    run_id='run-pend',
                    final_answer=None,
                    iterations=1,
                    tool_calls=0,
                    status='pending_approval',
                ),
                audit,
            )

            pending = store.pending_approval_for_run('run-pend')

            self.assertIsNotNone(pending)
            self.assertEqual(pending['call_id'], 'write-1')
            self.assertEqual(pending['tool_name'], 'workspace_write_file')
            self.assertEqual(pending['arguments']['path'], 'x.txt')

    def test_pending_approval_for_run_clears_after_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record('run_started', 'run-resolved', task='write')
            audit.record(
                'tool_call_pending_approval',
                'run-resolved',
                call_id='write-1',
                tool_name='workspace_write_file',
                arguments={'path': 'x.txt', 'content': 'x'},
            )
            audit.record('tool_call_approved', 'run-resolved', call_id='write-1')
            store.logger_for_result(
                RunResult(
                    run_id='run-resolved',
                    final_answer=None,
                    iterations=2,
                    tool_calls=1,
                    status='completed',
                ),
                audit,
            )

            self.assertIsNone(store.pending_approval_for_run('run-resolved'))


if __name__ == '__main__':
    unittest.main()
