"""Acceptance test for guided recovery flow.

This test verifies that:
1. Failed runs trigger recovery guidance display
2. Recovery advice is appropriate for the failure type
3. Commands are correctly formatted
"""

import tempfile
from pathlib import Path

import pytest

from teaagent.guided_recovery import (
    FailureAnalyzer,
    FailureCategory,
    FailureSeverity,
    FailureType,
    RecoveryAdviceFormatter,
    RecoverySelector,
)
from teaagent.runner._types import FinalAnswer, RunResult


def test_guided_recovery_end_to_end():
    """Test end-to-end guided recovery flow."""
    # Simulate a failed run
    result = RunResult(
        run_id="test-run-guided-recovery",
        final_answer=None,
        iterations=5,
        tool_calls=3,
        status="failed",
        error_message="Tool call was denied by approval handler",
        metadata={"approval_denied": True},
    )

    # Analyze failure
    analyzer = FailureAnalyzer(audit_logger=None)
    failure = analyzer.classify(result)

    # Verify classification
    assert failure.category == FailureCategory.APPROVAL_DENIED
    assert failure.severity == FailureSeverity.LOW
    assert failure.recoverable is True

    # Select recovery strategy
    selector = RecoverySelector(undo_journal=None)
    advice = selector.select(failure)

    # Verify strategy selection
    assert advice.strategy.name == "inspect"
    assert advice.confidence >= 0.8
    assert len(advice.alternatives) >= 1

    # Format advice
    formatter = RecoveryAdviceFormatter()
    formatted = formatter.format(advice, run_id=result.run_id)

    # Verify formatting
    assert "RECOVERY RECOMMENDATION" in formatted
    assert "Recommended Action: INSPECT" in formatted
    assert "teaagent audit view --run test-run-guided-recovery" in formatted
    assert "Alternative actions:" in formatted

    # Verify JSON formatting
    json_output = formatter.format_json(advice, run_id=result.run_id)
    assert json_output["recommended_strategy"]["name"] == "inspect"
    assert json_output["confidence"] >= 0.8
    assert len(json_output["alternatives"]) >= 1


def test_guided_recovery_tool_failure():
    """Test guided recovery for tool failure."""
    result = RunResult(
        run_id="test-run-tool-failure",
        final_answer=None,
        iterations=4,
        tool_calls=3,
        status="failed",
        error_message="Tool execution failed",
        metadata={"failed_tool": "workspace_write_file"},
    )

    analyzer = FailureAnalyzer(audit_logger=None)
    failure = analyzer.classify(result)

    selector = RecoverySelector(undo_journal=None)
    advice = selector.select(failure)

    assert advice.strategy.name == "inspect"
    assert "tool_failure" in advice.reasoning


def test_guided_recovery_partial_success():
    """Test guided recovery for partial success."""
    result = RunResult(
        run_id="test-run-partial-success",
        final_answer=FinalAnswer(content="Partial completion"),
        iterations=8,
        tool_calls=6,
        status="completed",
        error_message=None,
        metadata={"partial_success": True},
    )

    analyzer = FailureAnalyzer(audit_logger=None)
    failure = analyzer.classify(result)

    selector = RecoverySelector(undo_journal=None)
    advice = selector.select(failure)

    assert advice.strategy.name == "undo"
    assert advice.strategy.destructive is True
    assert advice.strategy.requires_confirmation is True


def test_guided_recovery_with_undo_journal():
    """Test guided recovery with undo journal available."""
    # Create a temporary undo journal
    with tempfile.TemporaryDirectory() as tmpdir:
        from teaagent.run_undo import UndoJournal

        undo_path = Path(tmpdir) / "undo.jsonl"
        journal = UndoJournal(root=tmpdir, path=undo_path)

        # Simulate a failed run with undo journal
        result = RunResult(
            run_id="test-run-with-undo",
            final_answer=None,
            iterations=3,
            tool_calls=2,
            status="failed",
            error_message="Tool execution failed",
            metadata={"failed_tool": "workspace_write_file"},
        )

        analyzer = FailureAnalyzer(audit_logger=None)
        failure = analyzer.classify(result)

        selector = RecoverySelector(undo_journal=journal)
        advice = selector.select(failure)

        # With undo journal, confidence should be adjusted
        # (though in this case journal is empty, so confidence might be lower)
        assert advice.strategy.name == "inspect"


def test_guided_recovery_all_failure_categories():
    """Test that all failure categories produce valid advice."""
    test_cases = [
        (
            FailureCategory.TOOL_FAILURE,
            "Tool execution failed",
            {"failed_tool": "workspace_write_file"},
        ),
        (
            FailureCategory.APPROVAL_DENIED,
            "Tool call was denied",
            {"approval_denied": True},
        ),
        (
            FailureCategory.BUDGET_EXCEEDED,
            "Budget limit exceeded",
            {"budget_exceeded": True},
        ),
        (
            FailureCategory.TIMEOUT,
            "Operation timed out",
            {"timeout": True},
        ),
        (
            FailureCategory.PERMISSION_ERROR,
            "Access denied",
            {"permission_error": True},
        ),
        (
            FailureCategory.PARTIAL_SUCCESS,
            "Partial completion",
            {"partial_success": True},
        ),
    ]

    for category, error_msg, metadata in test_cases:
        result = RunResult(
            run_id=f"test-run-{category.value}",
            final_answer=None,
            iterations=5,
            tool_calls=3,
            status="failed" if category != FailureCategory.PARTIAL_SUCCESS else "completed",
            error_message=error_msg,
            metadata=metadata,
        )

        analyzer = FailureAnalyzer(audit_logger=None)
        failure = analyzer.classify(result)

        selector = RecoverySelector(undo_journal=None)
        advice = selector.select(failure)

        formatter = RecoveryAdviceFormatter()
        formatted = formatter.format(advice, run_id=result.run_id)

        # Verify all categories produce valid output
        assert "RECOVERY RECOMMENDATION" in formatted
        assert "Recommended Action:" in formatted
        assert "Command to execute:" in formatted
