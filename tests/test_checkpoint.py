from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.checkpoint import (
    InMemoryCheckpointStore,
    SQLiteCheckpointStore,
    _extract_checkpoint,
)


def test_extracts_known_keys_only() -> None:
    context = {
        'task': 'do thing',
        'observations': [{'call_id': 'a', 'tool_name': 'read', 'result': {}}],
        'compacted_summary': 'summary text',
        'memory_keys': ['task'],
        '_cost_cents': 0.5,
        'memories': [{'content': 'mem'}],
    }
    snap = _extract_checkpoint(context)
    assert set(snap.keys()) == {
        'task',
        'observations',
        'compacted_summary',
        'memory_keys',
    }
    assert '_cost_cents' not in snap
    assert 'memories' not in snap


def test_skips_missing_optional_keys() -> None:
    context = {'task': 'minimal', 'observations': []}
    snap = _extract_checkpoint(context)
    assert snap == {'task': 'minimal', 'observations': []}


def test_save_and_load() -> None:
    store = InMemoryCheckpointStore()
    context = {'task': 'test', 'observations': [{'call_id': 'x'}]}
    store.save('run-1', context)
    loaded = store.load('run-1')
    assert loaded is not None
    assert loaded['task'] == 'test'
    assert len(loaded['observations']) == 1


def test_load_missing_returns_none() -> None:
    store = InMemoryCheckpointStore()
    assert store.load('no-such-run') is None


def test_delete_removes_entry() -> None:
    store = InMemoryCheckpointStore()
    store.save('run-1', {'task': 't', 'observations': []})
    store.delete('run-1')
    assert store.load('run-1') is None


def test_delete_missing_is_noop() -> None:
    store = InMemoryCheckpointStore()
    store.delete('ghost')  # must not raise


def test_overwrite_updates_snapshot() -> None:
    store = InMemoryCheckpointStore()
    store.save('r', {'task': 't', 'observations': []})
    store.save('r', {'task': 't', 'observations': [{'call_id': 'a'}]})
    loaded = store.load('r')
    assert loaded is not None
    assert len(loaded['observations']) == 1


def test_persist_across_instances() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        path = tmp_path / 'checkpoints.sqlite3'
        store1 = SQLiteCheckpointStore(path)
        store1.save('run-1', {'task': 'hello', 'observations': [{'call_id': 'z'}]})

        store2 = SQLiteCheckpointStore(path)
        loaded = store2.load('run-1')
        assert loaded is not None
        assert loaded['task'] == 'hello'
        assert loaded['observations'][0]['call_id'] == 'z'
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_load_missing_returns_none_sqlite() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store = SQLiteCheckpointStore(tmp_path / 'cp.sqlite3')
        assert store.load('nope') is None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_delete_removes_entry_sqlite() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store = SQLiteCheckpointStore(tmp_path / 'cp.sqlite3')
        store.save('r', {'task': 't', 'observations': []})
        store.delete('r')
        assert store.load('r') is None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_overwrite_upserts() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store = SQLiteCheckpointStore(tmp_path / 'cp.sqlite3')
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
        assert loaded['compacted_summary'] == 'cs'
        assert len(loaded['observations']) == 1
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_creates_parent_dirs() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        path = tmp_path / 'deep' / 'nested' / 'cp.sqlite3'
        store = SQLiteCheckpointStore(path)
        store.save('r', {'task': 't', 'observations': []})
        assert path.exists()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def _make_runner(checkpoint_store=None):
    from teaagent.runner import AgentRunner
    from teaagent.types import AuditLogger, RunBudget, ToolAnnotations, ToolRegistry

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
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {'out': args['msg']},
    )
    return AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        budget=RunBudget(max_iterations=5, max_tool_calls=5),
        checkpoint_store=checkpoint_store,
    )


def test_checkpoint_saved_after_tool_call() -> None:
    from teaagent.runner import FinalAnswer, ToolRequest

    store = InMemoryCheckpointStore()
    runner = _make_runner(checkpoint_store=store)

    calls = iter(
        [
            ToolRequest(tool_name='echo', arguments={'msg': 'hi'}, call_id='c1'),
            FinalAnswer(content='done'),
        ]
    )

    runner.run(task='test task', decide=lambda _: next(calls), run_id='run-42')

    checkpoint = store.load('run-42')
    assert checkpoint is not None
    assert len(checkpoint['observations']) == 1
    assert checkpoint['observations'][0]['call_id'] == 'c1'


def test_initial_context_extra_merged() -> None:
    from teaagent.runner import FinalAnswer

    runner = _make_runner()
    seen_context: list[dict] = []

    def decide(ctx):
        seen_context.append(dict(ctx))
        return FinalAnswer(content='ok')

    runner.run(
        task='t',
        decide=decide,
        initial_context_extra={'compacted_summary': 'prior summary'},
    )
    assert seen_context[0].get('compacted_summary') == 'prior summary'


def test_task_in_extra_is_not_overwritten() -> None:
    from teaagent.runner import FinalAnswer

    runner = _make_runner()
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
    assert seen_context[0]['task'] == 'real task'
