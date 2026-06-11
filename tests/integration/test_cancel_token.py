"""IT-2: AgentRunner respects a cancel token set from another thread.

Verifies that setting the ``threading.Event`` cancel token causes the runner
to stop cleanly and return a ``failed:system`` status without corrupting the
audit log.
"""

from __future__ import annotations

import threading
import time

from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.types import AuditLogger

# Import shared helper from conftest
from tests.conftest import make_minimal_registry, make_noop_registry

# Cancel token test constants
_CANCEL_SLOW_DECIDE_SLEEP = 0.05  # Sleep time (seconds) for slow decision function
_CANCEL_ITERATION_SLEEP = (
    0.01  # Sleep time (seconds) in iteration to allow cancel check
)


def _slow_decide(context: dict) -> ToolRequest | FinalAnswer:
    """Simulate a decision function that takes a while."""
    time.sleep(_CANCEL_SLOW_DECIDE_SLEEP)
    return FinalAnswer(content='done')


def test_cancel_before_first_iteration(tmp_path):
    cancel = threading.Event()
    cancel.set()  # already cancelled

    registry = make_minimal_registry()
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit, cancel_token=cancel)

    result = runner.run(task='work', decide=_slow_decide)
    # Must not complete — cancelled before first useful iteration
    # Cancel token set before run starts should cause immediate system failure
    assert result.status == 'failed:system', (
        f'expected failed:system (cancel token pre-set), got {result.status!r}'
    )


def test_cancel_during_run(tmp_path):
    """Cancel is set on the first decide call; the second iteration must honour it."""
    cancel = threading.Event()

    def decide(context: dict) -> ToolRequest | FinalAnswer:
        # Set cancel immediately so the next iteration check fires before any FinalAnswer.
        cancel.set()
        time.sleep(_CANCEL_ITERATION_SLEEP)
        # Return a ToolRequest (not FinalAnswer) so the loop iterates again.
        return ToolRequest(tool_name='noop', arguments={}, call_id='c1')

    registry = make_noop_registry()
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit, cancel_token=cancel)

    result = runner.run(task='work', decide=decide)
    # Must be cancelled during run
    # Cancel token set during iteration should cause system failure on next iteration check
    assert result.status == 'failed:system', (
        f'expected failed:system (cancel token set during run), got {result.status!r}'
    )
    # Audit log must still have run_started
    assert any(e.event_type == 'run_started' for e in audit.events)


def test_cancel_token_is_optional():
    """Runner works normally when no cancel_token is provided."""
    registry = make_minimal_registry()
    audit = AuditLogger()
    runner = AgentRunner(registry=registry, audit=audit)

    result = runner.run(task='hi', decide=lambda _: FinalAnswer(content='hello'))
    assert result.status == 'completed'
