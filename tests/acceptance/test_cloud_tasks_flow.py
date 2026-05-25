"""Acceptance test for cloud/managed runtime task lifecycle.

Verifies: CloudTaskStore CRUD, CloudTaskManager submit/poll/cancel.
"""

from __future__ import annotations

import json
import os
import tempfile

from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore


class _EchoAdapter:
    """A deterministic adapter that returns the task as output."""

    def run_task(self, task: str, *, context: dict) -> str:
        return f'echo: {task}'

    def health_check(self) -> bool:
        return True


def test_cloud_task_submit_poll_cancel() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        from teaagent.managed_runtime import ManagedAgentRunner

        store = CloudTaskStore(tmp)
        manager = CloudTaskManager(store=store, runner_factory=lambda r, adapter=None: ManagedAgentRunner(_EchoAdapter()))

        task = manager.submit('test-task', 'hello cloud', 'echo')
        assert task.status == 'completed', f'expected completed, got {task.status}'
        assert task.result == 'echo: hello cloud', f'unexpected result: {task.result}'

        polled = manager.poll(task.task_id)
        assert polled.status == 'completed'

        tasks = manager.list_tasks()
        assert any(t.name == 'test-task' for t in tasks)

        manifest = os.path.join(tmp, '.teaagent', 'cloud-tasks', 'tasks.jsonl')
        assert os.path.exists(manifest), 'manifest file should exist'
        assert task.name in open(manifest).read()


def test_cloud_task_cancel() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CloudTaskStore(tmp)
        manager = CloudTaskManager(store=store, runner_factory=lambda r, adapter=None: _EchoAdapter())

        store.create('cancel-me', 'prompt', 'echo')
        tasks = manager.list_tasks(status='pending')
        assert any(t.name == 'cancel-me' for t in tasks)
        pending = [t for t in tasks if t.name == 'cancel-me'][0]
        cancelled = manager.cancel(pending.task_id)
        assert cancelled.status == 'cancelled'


def test_cloud_task_store_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CloudTaskStore(tmp)
        task = store.create('persist', 'data', 'echo')
        re_read = CloudTaskStore(tmp).get(task.task_id)
        assert re_read is not None
        assert re_read.name == 'persist'


def test_cloud_task_capabilities() -> None:
    from teaagent.cloud_tasks import CloudTaskManager, CloudTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        store = CloudTaskStore(tmp)
        manager = CloudTaskManager(store=store)
        caps = manager.capabilities()
        assert isinstance(caps, list)
        assert any(c['name'] == 'anthropic' for c in caps)
