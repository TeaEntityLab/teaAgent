from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.checkpoint import (
    InMemoryCheckpointStore,
    SQLiteCheckpointStore,
    _extract_checkpoint,
)


class ExtractCheckpointTests(unittest.TestCase):
    def test_extracts_known_keys_only(self) -> None:
        context = {
            'task': 'do thing',
            'observations': [{'call_id': 'a', 'tool_name': 'read', 'result': {}}],
            'compacted_summary': 'summary text',
            'memory_keys': ['task'],
            '_cost_cents': 0.5,
            'memories': [{'content': 'mem'}],
        }
        snap = _extract_checkpoint(context)
        self.assertEqual(
            set(snap.keys()),
            {'task', 'observations', 'compacted_summary', 'memory_keys'},
        )
        self.assertNotIn('_cost_cents', snap)
        self.assertNotIn('memories', snap)

    def test_skips_missing_optional_keys(self) -> None:
        context = {'task': 'minimal', 'observations': []}
        snap = _extract_checkpoint(context)
        self.assertEqual(snap, {'task': 'minimal', 'observations': []})


class InMemoryCheckpointStoreTests(unittest.TestCase):
    def test_save_and_load(self) -> None:
        store = InMemoryCheckpointStore()
        context = {'task': 'test', 'observations': [{'call_id': 'x'}]}
        store.save('run-1', context)
        loaded = store.load('run-1')
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded['task'], 'test')
        self.assertEqual(len(loaded['observations']), 1)

    def test_load_missing_returns_none(self) -> None:
        store = InMemoryCheckpointStore()
        self.assertIsNone(store.load('no-such-run'))

    def test_delete_removes_entry(self) -> None:
        store = InMemoryCheckpointStore()
        store.save('run-1', {'task': 't', 'observations': []})
        store.delete('run-1')
        self.assertIsNone(store.load('run-1'))

    def test_delete_missing_is_noop(self) -> None:
        store = InMemoryCheckpointStore()
        store.delete('ghost')  # must not raise

    def test_overwrite_updates_snapshot(self) -> None:
        store = InMemoryCheckpointStore()
        store.save('r', {'task': 't', 'observations': []})
        store.save('r', {'task': 't', 'observations': [{'call_id': 'a'}]})
        loaded = store.load('r')
        assert loaded is not None
        self.assertEqual(len(loaded['observations']), 1)


class SQLiteCheckpointStoreTests(unittest.TestCase):
    def test_persist_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'checkpoints.sqlite3'
            store1 = SQLiteCheckpointStore(path)
            store1.save('run-1', {'task': 'hello', 'observations': [{'call_id': 'z'}]})

            store2 = SQLiteCheckpointStore(path)
            loaded = store2.load('run-1')
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded['task'], 'hello')
            self.assertEqual(loaded['observations'][0]['call_id'], 'z')

    def test_load_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteCheckpointStore(Path(tmp) / 'cp.sqlite3')
            self.assertIsNone(store.load('nope'))

    def test_delete_removes_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteCheckpointStore(Path(tmp) / 'cp.sqlite3')
            store.save('r', {'task': 't', 'observations': []})
            store.delete('r')
            self.assertIsNone(store.load('r'))

    def test_overwrite_upserts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteCheckpointStore(Path(tmp) / 'cp.sqlite3')
            store.save('r', {'task': 't', 'observations': []})
            store.save(
                'r',
                {
                    'task': 't',
                    'observations': [{'call_id': 'b'}],
                    'compacted_summary': 'cs',
                },
            )
            loaded = store.load('r')
            assert loaded is not None
            self.assertEqual(loaded['compacted_summary'], 'cs')
            self.assertEqual(len(loaded['observations']), 1)

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'deep' / 'nested' / 'cp.sqlite3'
            store = SQLiteCheckpointStore(path)
            store.save('r', {'task': 't', 'observations': []})
            self.assertTrue(path.exists())


class AgentRunnerCheckpointTests(unittest.TestCase):
    def _make_runner(self, checkpoint_store=None):
        from teaagent.audit import AuditLogger
        from teaagent.budget import RunBudget
        from teaagent.runner import AgentRunner
        from teaagent.tools import ToolAnnotations, ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name='echo',
            description='echo',
            input_schema={
                'type': 'object',
                'properties': {'msg': {'type': 'string'}},
                'required': ['msg'],
            },
            output_schema={
                'type': 'object',
                'properties': {'out': {'type': 'string'}},
                'required': ['out'],
            },
            annotations=ToolAnnotations(
                read_only=True, destructive=False, idempotent=True
            ),
            handler=lambda args: {'out': args['msg']},
        )
        return AgentRunner(
            registry=registry,
            audit=AuditLogger(),
            budget=RunBudget(max_iterations=5, max_tool_calls=5),
            checkpoint_store=checkpoint_store,
        )

    def test_checkpoint_saved_after_tool_call(self) -> None:
        from teaagent.runner import FinalAnswer, ToolRequest

        store = InMemoryCheckpointStore()
        runner = self._make_runner(checkpoint_store=store)

        calls = iter(
            [
                ToolRequest(tool_name='echo', arguments={'msg': 'hi'}, call_id='c1'),
                FinalAnswer(content='done'),
            ]
        )

        runner.run(task='test task', decide=lambda _: next(calls), run_id='run-42')

        checkpoint = store.load('run-42')
        self.assertIsNotNone(checkpoint)
        assert checkpoint is not None
        self.assertEqual(len(checkpoint['observations']), 1)
        self.assertEqual(checkpoint['observations'][0]['call_id'], 'c1')

    def test_initial_context_extra_merged(self) -> None:
        from teaagent.runner import FinalAnswer

        runner = self._make_runner()
        seen_context: list[dict] = []

        def decide(ctx):
            seen_context.append(dict(ctx))
            return FinalAnswer(content='ok')

        runner.run(
            task='t',
            decide=decide,
            initial_context_extra={'compacted_summary': 'prior summary'},
        )
        self.assertEqual(seen_context[0].get('compacted_summary'), 'prior summary')

    def test_task_in_extra_is_not_overwritten(self) -> None:
        from teaagent.runner import FinalAnswer

        runner = self._make_runner()
        seen_context: list[dict] = []

        def decide(ctx):
            seen_context.append(dict(ctx))
            return FinalAnswer(content='ok')

        runner.run(
            task='real task',
            decide=decide,
            initial_context_extra={
                'task': 'should be ignored',
                'compacted_summary': 'cs',
            },
        )
        self.assertEqual(seen_context[0]['task'], 'real task')


if __name__ == '__main__':
    unittest.main()
