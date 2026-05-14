"""AC-NEW-2: Error remediation hints flow.

As a user with a misconfigured environment, I want error messages to include
actionable remediation hints so I know exactly what to try next without
reading documentation.

Acceptance criteria:
- ``BudgetExceededError`` includes a hint about increasing limits.
- ``ToolPermissionError`` includes a hint about changing permission-mode.
- ``ToolExecutionError`` includes a hint about workspace/command validity.
- ``RunCancelledError`` includes a hint about resuming.
- Hints are surfaced in ``str()`` output so CLI formatters get them for free.
- Custom hints override defaults.
"""

from __future__ import annotations

from teaagent.errors import (
    BudgetExceededError,
    RunCancelledError,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)


def test_budget_exceeded_hint_mentions_iterations():
    exc = BudgetExceededError('over budget')
    assert exc.hint is not None
    hint_lower = exc.hint.lower()
    assert any(
        kw in hint_lower for kw in ['max_iterations', 'budget', 'limit', 'subtask']
    )


def test_tool_permission_hint_mentions_permission_mode():
    exc = ToolPermissionError('blocked')
    assert exc.hint is not None
    hint_lower = exc.hint.lower()
    assert 'permission' in hint_lower or 'allow' in hint_lower


def test_tool_execution_hint_mentions_workspace():
    exc = ToolExecutionError('failed')
    assert exc.hint is not None
    hint_lower = exc.hint.lower()
    assert any(kw in hint_lower for kw in ['workspace', 'writable', 'command', 'valid'])


def test_run_cancelled_hint_mentions_resume():
    exc = RunCancelledError()
    assert exc.hint is not None
    assert 'resume' in exc.hint.lower()


def test_hints_appear_in_str_representation():
    exc = BudgetExceededError('over budget')
    rendered = str(exc)
    assert '→' in rendered
    assert exc.hint in rendered  # type: ignore[operator]


def test_custom_hint_replaces_default():
    exc = ToolPermissionError('denied', hint='Ask your admin to change the policy.')
    assert 'Ask your admin' in str(exc)
    assert 'Ask your admin' in exc.hint  # type: ignore[operator]


def test_all_concrete_errors_have_hints():
    for cls in (
        BudgetExceededError,
        ToolValidationError,
        ToolPermissionError,
        ToolExecutionError,
        RunCancelledError,
    ):
        exc = cls('test message')
        assert exc.hint is not None, f'{cls.__name__} must provide a default hint'
        assert len(exc.hint.strip()) > 0
