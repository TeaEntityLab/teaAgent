# test-type: behavior
"""A batch deadline must stop running children via the cooperative cancel token.

Covers G-P1-5: children that outlive the batch deadline keep executing tool
calls unless the batch sets a cancel token they check. These tests drive a real
child AgentRunner (no mocked run_subagent) with a stub LLM that always requests
a slow read-only tool, and count how many tool calls actually execute.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.chat_agent import ChatAgentConfig
from teaagent.llm import LLMResponse
from teaagent.run_store import RunStore
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.types import ToolAnnotations, ToolRegistry

_TOOL_SLEEP_SECONDS = 0.4
_BATCH_TIMEOUT_SECONDS = 1
_POST_RETURN_WAIT_SECONDS = 1.5


class _CountingProbe:
    """Thread-safe counter for executed tool calls, with a slow handler."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._count = 0

    def __call__(self, _args: dict) -> dict:
        with self._lock:
            self._count += 1
        time.sleep(_TOOL_SLEEP_SECONDS)
        return {'ok': True}

    def value(self) -> int:
        with self._lock:
            return self._count


class _AlwaysToolAdapter:
    """Stub LLM that requests the slow probe tool on every iteration."""

    provider = 'stub'

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = 0

    def complete(self, request: object) -> LLMResponse:
        with self._lock:
            self._calls += 1
            call_id = f'c{self._calls}'
        return LLMResponse(
            provider='stub',
            model='stub',
            content=(
                '{"type":"tool","tool_name":"slow_probe",'
                f'"arguments":{{}},"call_id":"{call_id}"}}'
            ),
        )


def _setup(
    root: Path, parent_cancel: threading.Event | None
) -> tuple[ToolRegistry, SubagentManager, ChatAgentConfig, _CountingProbe]:
    (root / '.teaagent').mkdir(exist_ok=True)
    probe = _CountingProbe()
    registry = ToolRegistry()
    registry.register(
        name='slow_probe',
        description='slow read-only probe',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'additionalProperties': True},
        annotations=ToolAnnotations(read_only=True),
        handler=probe,
    )
    config = ChatAgentConfig(root=root, max_iterations=200, cancel_token=parent_cancel)
    manager = SubagentManager(
        root=root, parent_config=config, parent_adapter=_AlwaysToolAdapter()
    )
    return registry, manager, config, probe


def _run_batch(
    registry: ToolRegistry,
    manager: SubagentManager,
    config: ChatAgentConfig,
    tasks: list[dict],
    timeout_seconds: int,
) -> dict:
    # register_subagent_tools binds ``registry`` as the children's source registry,
    # so the batch tool must be registered on the same registry the probe lives in.
    register_subagent_tools(
        registry,
        adapter=manager._parent_adapter,
        config=config,
        depth=0,
        manager=manager,
    )
    return registry.execute(
        'subagent_batch',
        {
            'tasks': tasks,
            'max_workers': len(tasks),
            'timeout_seconds': timeout_seconds,
        },
    )


def _loop_task() -> dict:
    return {
        'task': 'loop forever',
        'isolation': 'shared',
        'max_iterations': 200,
        'max_tool_calls': 200,
    }


def test_batch_deadline_stops_running_child_tool_loop() -> None:
    """After the batch returns at its deadline, a running child may finish at most
    the one tool call it had already dispatched; it must not start another.

    Bound: tool executions after batch return <= 1 (the single in-flight call
    that passed the pre-dispatch cancel check before the batch token was set).
    """
    with TemporaryDirectory() as td:
        root = Path(td)
        registry, manager, config, probe = _setup(root, parent_cancel=None)
        result = _run_batch(
            registry, manager, config, [_loop_task()], _BATCH_TIMEOUT_SECONDS
        )
        count_at_return = probe.value()
        time.sleep(_POST_RETURN_WAIT_SECONDS)
        count_after_wait = probe.value()

        assert result['timed_out'] == 1, result
        assert count_at_return >= 1, 'child never executed a tool before the deadline'
        delta = count_after_wait - count_at_return
        assert delta <= 1, (
            f'child executed {delta} tool calls after the batch deadline '
            f'(bound: <= 1 in-flight call); at return={count_at_return}, '
            f'after wait={count_after_wait}'
        )

        store = RunStore(root)
        cancelled_runs = []
        for summary in store.list_runs(limit=None):
            events = store.show_run(summary.run_id)
            if any(
                e.get('event_type') == 'run_failed' and 'cancel' in str(e).lower()
                for e in events
            ):
                cancelled_runs.append(summary.run_id)
        assert cancelled_runs, 'child cancellation was not recorded in the audit log'


def test_parent_cancel_mid_batch_stops_children() -> None:
    parent_cancel = threading.Event()
    with TemporaryDirectory() as td:
        root = Path(td)
        registry, manager, config, probe = _setup(root, parent_cancel=parent_cancel)
        timer = threading.Timer(0.6, parent_cancel.set)
        timer.start()
        started = time.monotonic()
        result = _run_batch(registry, manager, config, [_loop_task(), _loop_task()], 10)
        elapsed = time.monotonic() - started
        timer.cancel()
        count_at_return = probe.value()
        time.sleep(0.8)

        assert elapsed < 5, (
            f'batch waited {elapsed:.2f}s; parent cancel did not propagate'
        )
        assert all(r.get('status') != 'completed' for r in result['results']), result
        assert probe.value() - count_at_return <= 1
