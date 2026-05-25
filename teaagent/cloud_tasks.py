"""Cloud Task Manager — submit/poll/cancel tasks to managed runtimes.

Extends ``managed_runtime.py`` with an async task lifecycle:
submit → pending → running → completed/failed/cancelled.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.managed_runtime import (
    ManagedAgentRunner,
    ManagedRuntimeAdapter,
    managed_runtime_capabilities,
    managed_runtime_context,
)


@dataclass(frozen=True)
class CloudTask:
    task_id: str
    name: str
    prompt: str
    runtime: str
    status: str
    created_at: str
    updated_at: str
    result: Optional[str] = None
    error: Optional[str] = None
    run_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TASK_STORE_LOCK = threading.Lock()


class CloudTaskStore:
    """Persistent JSONL store for cloud task lifecycle."""

    def __init__(self, path: str | Path = '.') -> None:
        self._dir = Path(path).resolve() / '.teaagent' / 'cloud-tasks'
        self._dir.mkdir(parents=True, exist_ok=True)

    def _manifest(self) -> Path:
        return self._dir / 'tasks.jsonl'

    def _read_all(self) -> list[CloudTask]:
        manifest = self._manifest()
        if not manifest.exists():
            return []
        tasks: list[CloudTask] = []
        with _TASK_STORE_LOCK:
            for line in manifest.read_text(encoding='utf-8').strip().splitlines():
                if line:
                    tasks.append(CloudTask(**json.loads(line)))
        return tasks

    def _write_all(self, tasks: list[CloudTask]) -> None:
        with _TASK_STORE_LOCK:
            self._manifest().write_text(
                '\n'.join(json.dumps(t.to_dict()) for t in tasks) + '\n',
                encoding='utf-8',
            )

    def _append(self, task: CloudTask) -> None:
        with _TASK_STORE_LOCK, self._manifest().open('a', encoding='utf-8') as f:
            f.write(json.dumps(task.to_dict()) + '\n')

    def create(self, name: str, prompt: str, runtime: str) -> CloudTask:
        now = datetime.now(timezone.utc).isoformat()
        task = CloudTask(
            task_id=str(uuid4()),
            name=name,
            prompt=prompt,
            runtime=runtime,
            status='pending',
            created_at=now,
            updated_at=now,
        )
        self._append(task)
        return task

    def get(self, task_id: str) -> Optional[CloudTask]:
        for t in self._read_all():
            if t.task_id == task_id:
                return t
        return None

    def list(self, *, status: Optional[str] = None, limit: int = 50) -> list[CloudTask]:
        tasks = self._read_all()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    def update(self, task_id: str, **changes: Any) -> CloudTask:
        tasks = self._read_all()
        for i, t in enumerate(tasks):
            if t.task_id == task_id:
                updated = CloudTask(**{**t.to_dict(), **changes, 'updated_at': datetime.now(timezone.utc).isoformat()})
                tasks[i] = updated
                self._write_all(tasks)
                return updated
        raise ValueError(f'task {task_id!r} not found')

    def delete(self, task_id: str) -> None:
        tasks = [t for t in self._read_all() if t.task_id != task_id]
        self._write_all(tasks)

    def cancel(self, task_id: str) -> CloudTask:
        return self.update(task_id, status='cancelled')


class CloudTaskManager:
    """Orchestrates cloud task lifecycle with local or remote adapters."""

    def __init__(
        self,
        *,
        store: CloudTaskStore,
        runner_factory: Optional[Any] = None,
    ) -> None:
        self._store = store
        self._runner_factory = runner_factory or _default_runner

    def submit(
        self, name: str, prompt: str, runtime: str, *, adapter: Optional[ManagedRuntimeAdapter] = None
    ) -> CloudTask:
        from teaagent.tools import ToolRegistry

        task = self._store.create(name, prompt, runtime)
        task = self._store.update(task.task_id, status='running')
        try:
            runner = self._runner_factory(runtime, adapter=adapter)
            ctx = managed_runtime_context(ToolRegistry())
            result = runner.run(prompt, context=ctx)
            return self._store.update(
                task.task_id,
                status='completed',
                result=result.output,
                run_id=result.metadata.get('run_id', ''),
                metadata=result.metadata,
            )
        except Exception as exc:
            return self._store.update(task.task_id, status='failed', error=str(exc))

    def poll(self, task_id: str) -> CloudTask:
        task = self._store.get(task_id)
        if task is None:
            raise ValueError(f'task {task_id!r} not found')
        return task

    def cancel(self, task_id: str) -> CloudTask:
        return self._store.cancel(task_id)

    def list_tasks(self, *, status: Optional[str] = None, limit: int = 50) -> list[CloudTask]:
        return self._store.list(status=status, limit=limit)

    def capabilities(self) -> list[dict[str, Any]]:
        return managed_runtime_capabilities()


def _default_runner(runtime: str, *, adapter: Optional[ManagedRuntimeAdapter] = None) -> ManagedAgentRunner:
    if adapter is not None:
        return ManagedAgentRunner(adapter, runtime_name=runtime)
    runtime_map = {
        'anthropic': ('AnthropicManagedRuntime', {'agent_id': 'default', 'model': 'claude-opus-4-5'}),
        'openai': ('OpenAIManagedRuntime', {'assistant_id': 'default', 'model': 'gpt-4o'}),
    }
    if runtime in runtime_map:
        class_name, kwargs = runtime_map[runtime]
        module = __import__('teaagent.managed_runtime', fromlist=[class_name])
        cls = getattr(module, class_name)
        return ManagedAgentRunner(cls(**kwargs), runtime_name=runtime)
    raise ValueError(f'unknown runtime: {runtime}. '
                     f'Install the SDK or provide a custom adapter.')
