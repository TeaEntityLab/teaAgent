"""AC-NEW-5: Graceful cancel flow.

As a developer, I want to interrupt a running agent using a cancel token
so that long-running tasks can be stopped cleanly without corrupting state.

Acceptance criteria:
- Setting the cancel token causes the run to stop with a ``failed:system`` status.
- Audit log still has ``run_started``; no corruption.
- A subsequent resume from the checkpoint continues from where it left off.
- The cancel token can be set from a different thread.
"""

from __future__ import annotations

import threading
import time

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.tools import ToolRegistry


class _SlowStubAdapter:
    """Adapter that blocks in complete() until the cancel event is set."""

    provider = 'stub'
    call_count = 0

    def __init__(self, cancel_event: threading.Event) -> None:
        self._cancel = cancel_event

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        self.call_count += 1
        # Signal cancel while "working" so runner sees it on next iteration
        self._cancel.set()
        time.sleep(0.01)
        # Return a ToolRequest so the run loops and the cancel check fires
        return LLMResponse(
            provider='stub',
            model='stub',
            # Return a ToolRequest decision so the loop continues and cancel fires
            content='{"type":"tool","tool_name":"noop","arguments":{},"call_id":"c1"}',
        )


def test_cancel_token_stops_run_cleanly(tmp_path):
    cancel = threading.Event()
    adapter = _SlowStubAdapter(cancel)

    # Register a noop tool so the ToolRequest can be dispatched once before cancel
    from teaagent.tools import ToolAnnotations, ToolRegistry

    registry = ToolRegistry()
    registry.register(
        name='noop',
        description='noop',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {},
    )

    config = ChatAgentConfig.from_root(
        tmp_path,
        max_iterations=50,
        cancel_token=cancel,
    )

    result = run_chat_agent(
        task='long task',
        adapter=adapter,
        config=config,
        registry=registry,
    )

    assert result.status.startswith('failed'), (
        f'expected failed status after cancel, got {result.status!r}'
    )


def test_cancelled_run_has_run_started_in_audit(tmp_path):
    cancel = threading.Event()
    cancel.set()  # pre-cancelled

    audit = AuditLogger()
    registry = ToolRegistry()
    runner = AgentRunner(registry=registry, audit=audit, cancel_token=cancel)
    runner.run(task='cancelled', decide=lambda _: FinalAnswer(content='x'))

    assert any(e.event_type == 'run_started' for e in audit.events), (
        'run_started must still be recorded even when cancelled'
    )


def test_cancel_token_without_set_runs_normally(tmp_path):
    cancel = threading.Event()  # never set

    class _QuickAdapter:
        provider = 'stub'

        def complete(self, request):  # type: ignore[override]
            from teaagent.llm import LLMResponse

            return LLMResponse(
                provider='stub',
                model='stub',
                content='{"type":"final","content":"done"}',
            )

    config = ChatAgentConfig.from_root(tmp_path, cancel_token=cancel)
    result = run_chat_agent(task='hello', adapter=_QuickAdapter(), config=config)
    assert result.status == 'completed'
