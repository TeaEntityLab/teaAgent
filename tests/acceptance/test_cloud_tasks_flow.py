"""Test module for cloud/managed runtime task lifecycle.

This module tests the cloud task system for managed runtime environments, which
enables task submission, polling, and cancellation in cloud environments. The
system provides a task store and manager for cloud-based agent execution.

Key concepts tested:
- Task Submission: CloudTaskManager submits tasks for execution
- Task Polling: CloudTaskManager polls task status
- Task Cancellation: CloudTaskManager cancels pending tasks
- Task Persistence: CloudTaskStore persists task metadata
- Task Listing: CloudTaskManager lists all tasks
- Capabilities: CloudTaskManager exposes available capabilities

Acceptance Criteria:
- AC1: CloudTaskManager.submit() creates and executes a task
- AC2: CloudTaskManager.poll() returns current task status
- AC3: CloudTaskManager.cancel() cancels a pending task
- AC4: CloudTaskStore persists tasks to .teaagent/cloud-tasks/tasks.jsonl
- AC5: CloudTaskManager.list_tasks() returns all tasks
- AC6: CloudTaskManager.capabilities() returns available providers

Technical Details:
- CloudTaskStore manages task persistence in JSONL format
- CloudTaskManager integrates with ManagedAgentRunner for execution
- Tasks include: task_id, name, prompt, status, result
- Task states: pending, completed, cancelled
- Manifest file tracks all tasks for observability
- Capabilities expose available LLM providers

References:
- Cloud runtime design: /docs/architecture/cloud_runtime.md
- Task lifecycle spec: /docs/specs/cloud_tasks.md
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

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
        manager = CloudTaskManager(
            store=store,
            runner_factory=lambda r, adapter=None: ManagedAgentRunner(_EchoAdapter()),
        )

        task = manager.submit('test-task', 'hello cloud', 'echo')
        assert task.status == 'completed', f'expected completed, got {task.status}'
        assert task.result == 'echo: hello cloud', f'unexpected result: {task.result}'

        polled = manager.poll(task.task_id)
        assert polled.status == 'completed'

        tasks = manager.list_tasks()
        assert any(t.name == 'test-task' for t in tasks)

        manifest = os.path.join(tmp, '.teaagent', 'cloud-tasks', 'tasks.jsonl')
        assert os.path.exists(manifest), 'manifest file should exist'
        assert task.name in Path(manifest).read_text(encoding='utf-8')


def test_cloud_task_cancel() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CloudTaskStore(tmp)
        manager = CloudTaskManager(
            store=store, runner_factory=lambda r, adapter=None: _EchoAdapter()
        )

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
