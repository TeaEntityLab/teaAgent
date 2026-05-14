"""IT-9: Error classes include actionable hint messages.

Verifies that the ``hint`` attribute is set on concrete error instances and
that ``str()`` rendering includes the hint text so CLI formatters get it for free.
"""

from __future__ import annotations

import pytest

from teaagent.errors import (
    BudgetExceededError,
    RunCancelledError,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)


@pytest.mark.parametrize(
    'exc_cls',
    [
        BudgetExceededError,
        ToolExecutionError,
        ToolPermissionError,
        ToolValidationError,
        RunCancelledError,
    ],
)
def test_error_has_default_hint(exc_cls):
    exc = exc_cls('something went wrong')
    assert exc.hint is not None, f'{exc_cls.__name__} must have a default hint'
    assert len(exc.hint) > 0


@pytest.mark.parametrize(
    'exc_cls',
    [
        BudgetExceededError,
        ToolExecutionError,
        ToolPermissionError,
        ToolValidationError,
        RunCancelledError,
    ],
)
def test_str_includes_hint(exc_cls):
    exc = exc_cls('something went wrong')
    rendered = str(exc)
    assert '→' in rendered, f'{exc_cls.__name__} str() must include hint arrow'


def test_custom_hint_overrides_default():
    exc = BudgetExceededError('over budget', hint='Try using a smaller model.')
    assert 'Try using a smaller model.' in exc.hint  # type: ignore[operator]
    assert 'Try using a smaller model.' in str(exc)


def test_no_hint_renders_cleanly():
    exc = BudgetExceededError.__new__(BudgetExceededError)
    Exception.__init__(exc, 'bare error')
    exc.hint = None  # type: ignore[assignment]
    assert str(exc) == 'bare error'
