"""IT-2: AgentRunner respects a cancel token set from another thread.

Verifies that setting the ``threading.Event`` cancel token causes the runner
to stop cleanly and return a ``failed:system`` status without corrupting the
audit log.
"""

from __future__ import annotations

import threading
import time

from teaagent.audit import AuditLogger
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def _slow_decide(context: dict) -> ToolRequest | FinalAnswer:
    """Simulate a decision function that takes a while."""
    time.sleep(0.05)
    return FinalAnswer(content='done')


def _make_minimal_registry() -> ToolRegistry:
    registry = ToolRegistry()
    return registry


def test_cancel_before_first_iteration(tmp_path):
    cancel = threading.Event()
    cancel.set()  # already cancelled

    registry = _make_minimal_registry()
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit, cancel_token=cancel)

    result = runner.run(task='work', decide=_slow_decide)
    # Must not complete — cancelled before first useful iteration
    assert result.status.startswith('failed'), f'expected failed, got {result.status!r}'


def test_cancel_during_run(tmp_path):
    """Cancel is set on the first decide call; the second iteration must honour it."""
    cancel = threading.Event()

    def decide(context: dict) -> ToolRequest | FinalAnswer:
        # Set cancel immediately so the next iteration check fires before any FinalAnswer.
        cancel.set()
        time.sleep(0.01)
        # Return a ToolRequest (not FinalAnswer) so the loop iterates again.
        return ToolRequest(tool_name='noop', arguments={}, call_id='c1')

    registry = _make_minimal_registry()
    # Register a noop tool so the ToolRequest can be dispatched

    registry.register(
        name='noop',
        description='noop',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {},
    )
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit, cancel_token=cancel)

    result = runner.run(task='work', decide=decide)
    assert result.status.startswith('failed'), f'expected failed, got {result.status!r}'
    # Audit log must still have run_started
    assert any(e.event_type == 'run_started' for e in audit.events)


def test_cancel_token_is_optional():
    """Runner works normally when no cancel_token is provided."""
    registry = _make_minimal_registry()
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit)

    result = runner.run(task='hi', decide=lambda _: FinalAnswer(content='hello'))
    assert result.status == 'completed'
