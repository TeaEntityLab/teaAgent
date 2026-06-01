"""Unit tests for guided recovery module."""

import pytest

from teaagent.guided_recovery import (
    FailureAnalyzer,
    FailureCategory,
    FailureSeverity,
    FailureType,
    RecoveryAdvice,
    RecoveryAdviceFormatter,
    RecoverySelector,
    RecoveryStrategy,
)
from teaagent.runner._types import FinalAnswer, RunResult


@pytest.fixture
def analyzer():
    """Create a FailureAnalyzer instance."""
    return FailureAnalyzer(audit_logger=None)


def test_classify_approval_denied(analyzer):
    """Test classification of approval denied failures."""
    result = RunResult(
        run_id='test-run-1',
        final_answer=None,
        iterations=5,
        tool_calls=3,
        status='failed',
        error_message='Tool call was denied by approval handler',
        metadata={'approval_denied': True},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.APPROVAL_DENIED
    assert failure.severity == FailureSeverity.LOW
    assert failure.recoverable is True
    assert failure.error_message == 'Tool call was denied by approval handler'


def test_classify_budget_exceeded(analyzer):
    """Test classification of budget exceeded failures."""
    result = RunResult(
        run_id='test-run-2',
        final_answer=None,
        iterations=10,
        tool_calls=8,
        status='failed',
        error_message='Budget limit exceeded',
        metadata={'budget_exceeded': True},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.BUDGET_EXCEEDED
    assert failure.severity == FailureSeverity.HIGH
    assert failure.recoverable is False


def test_classify_timeout(analyzer):
    """Test classification of timeout failures."""
    result = RunResult(
        run_id='test-run-3',
        final_answer=None,
        iterations=15,
        tool_calls=12,
        status='failed',
        error_message='Operation timed out after 30 seconds',
        metadata={'timeout': True},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.TIMEOUT
    assert failure.severity == FailureSeverity.MEDIUM
    assert failure.recoverable is True


def test_classify_permission_error(analyzer):
    """Test classification of permission errors."""
    result = RunResult(
        run_id='test-run-4',
        final_answer=None,
        iterations=3,
        tool_calls=2,
        status='failed',
        error_message='Access denied: insufficient permissions',
        metadata={'permission_error': True},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.PERMISSION_ERROR
    assert failure.severity == FailureSeverity.MEDIUM
    assert failure.recoverable is True


def test_classify_tool_failure(analyzer):
    """Test classification of tool failures."""
    result = RunResult(
        run_id='test-run-5',
        final_answer=None,
        iterations=4,
        tool_calls=3,
        status='failed',
        error_message='Tool execution failed',
        metadata={'failed_tool': 'workspace_write_file'},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.TOOL_FAILURE
    assert failure.severity == FailureSeverity.MEDIUM
    assert failure.recoverable is True
    assert failure.tool_name == 'workspace_write_file'


def test_classify_partial_success(analyzer):
    """Test classification of partial success."""
    result = RunResult(
        run_id='test-run-6',
        final_answer=FinalAnswer(content='Partial completion'),
        iterations=8,
        tool_calls=6,
        status='completed',
        error_message=None,
        metadata={'partial_success': True},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.PARTIAL_SUCCESS
    assert failure.severity == FailureSeverity.MEDIUM
    assert failure.recoverable is True


def test_classify_unknown_failure(analyzer):
    """Test classification of unknown failures."""
    result = RunResult(
        run_id='test-run-7',
        final_answer=None,
        iterations=2,
        tool_calls=1,
        status='failed',
        error_message='Unknown error occurred',
        metadata={},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.UNKNOWN
    assert failure.severity == FailureSeverity.HIGH
    assert failure.recoverable is False


def test_classify_successful_run(analyzer):
    """Test classification of successful runs."""
    result = RunResult(
        run_id='test-run-8',
        final_answer=FinalAnswer(content='Task completed successfully'),
        iterations=5,
        tool_calls=4,
        status='completed',
        error_message=None,
        metadata={},
    )

    failure = analyzer.classify(result)

    assert failure.category == FailureCategory.UNKNOWN
    assert failure.severity == FailureSeverity.LOW
    assert failure.recoverable is True


def test_analyze_detailed(analyzer):
    """Test detailed analysis output."""
    result = RunResult(
        run_id='test-run-9',
        final_answer=None,
        iterations=7,
        tool_calls=5,
        status='failed',
        error_message='Tool call was denied',
        metadata={'approval_denied': True},
    )

    analysis = analyzer.analyze(result)

    assert analysis['category'] == 'approval_denied'
    assert analysis['severity'] == 'low'
    assert analysis['recoverable'] is True
    assert analysis['run_id'] == 'test-run-9'
    assert analysis['status'] == 'failed'
    assert analysis['iterations'] == 7
    assert analysis['tool_calls'] == 5
    assert analysis['audit_events_available'] is False


def test_error_message_keyword_detection(analyzer):
    """Test failure detection via error message keywords."""
    # Test approval denied via keyword
    result = RunResult(
        run_id='test-run-10',
        final_answer=None,
        iterations=3,
        tool_calls=2,
        status='failed',
        error_message='Request was rejected by policy',
        metadata={},
    )
    failure = analyzer.classify(result)
    assert failure.category == FailureCategory.APPROVAL_DENIED

    # Test budget exceeded via keyword
    result = RunResult(
        run_id='test-run-11',
        final_answer=None,
        iterations=5,
        tool_calls=4,
        status='failed',
        error_message='Cost limit reached',
        metadata={},
    )
    failure = analyzer.classify(result)
    assert failure.category == FailureCategory.BUDGET_EXCEEDED

    # Test timeout via keyword
    result = RunResult(
        run_id='test-run-12',
        final_answer=None,
        iterations=8,
        tool_calls=6,
        status='failed',
        error_message='Operation timed out',
        metadata={},
    )
    failure = analyzer.classify(result)
    assert failure.category == FailureCategory.TIMEOUT

    # Test permission error via keyword
    result = RunResult(
        run_id='test-run-13',
        final_answer=None,
        iterations=2,
        tool_calls=1,
        status='failed',
        error_message='Unauthorized access',
        metadata={},
    )
    failure = analyzer.classify(result)
    assert failure.category == FailureCategory.PERMISSION_ERROR


@pytest.fixture
def selector():
    """Create a RecoverySelector instance."""
    return RecoverySelector(undo_journal=None)


def test_select_tool_failure(selector):
    """Test strategy selection for tool failures."""
    failure = FailureType(
        category=FailureCategory.TOOL_FAILURE,
        severity=FailureSeverity.MEDIUM,
        recoverable=True,
        tool_name='workspace_write_file',
        error_message='Tool execution failed',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'inspect'
    assert advice.confidence >= 0.8
    assert len(advice.alternatives) >= 1
    assert 'Failure type: tool_failure' in advice.reasoning


def test_select_approval_denied(selector):
    """Test strategy selection for approval denied."""
    failure = FailureType(
        category=FailureCategory.APPROVAL_DENIED,
        severity=FailureSeverity.LOW,
        recoverable=True,
        error_message='Tool call was denied',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'inspect'
    assert advice.strategy.destructive is False
    assert advice.confidence >= 0.8


def test_select_budget_exceeded(selector):
    """Test strategy selection for budget exceeded."""
    failure = FailureType(
        category=FailureCategory.BUDGET_EXCEEDED,
        severity=FailureSeverity.HIGH,
        recoverable=False,
        error_message='Budget limit exceeded',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'manual'
    assert advice.strategy.destructive is False


def test_select_timeout(selector):
    """Test strategy selection for timeout."""
    failure = FailureType(
        category=FailureCategory.TIMEOUT,
        severity=FailureSeverity.MEDIUM,
        recoverable=True,
        error_message='Operation timed out',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'resume'
    assert advice.strategy.destructive is False
    assert advice.confidence >= 0.8


def test_select_permission_error(selector):
    """Test strategy selection for permission error."""
    failure = FailureType(
        category=FailureCategory.PERMISSION_ERROR,
        severity=FailureSeverity.MEDIUM,
        recoverable=True,
        error_message='Access denied',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'retry'
    assert 'safer' in advice.strategy.command_template


def test_select_partial_success(selector):
    """Test strategy selection for partial success."""
    failure = FailureType(
        category=FailureCategory.PARTIAL_SUCCESS,
        severity=FailureSeverity.MEDIUM,
        recoverable=True,
        error_message='Partial completion',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'undo'
    assert advice.strategy.destructive is True
    assert advice.strategy.requires_confirmation is True


def test_select_unknown_failure(selector):
    """Test strategy selection for unknown failures."""
    failure = FailureType(
        category=FailureCategory.UNKNOWN,
        severity=FailureSeverity.HIGH,
        recoverable=False,
        error_message='Unknown error',
    )

    advice = selector.select(failure)

    assert advice.strategy.name == 'inspect'
    assert advice.confidence < 0.8  # Lower confidence for unknown


def test_rank_strategies(selector):
    """Test ranking of recovery strategies."""
    failure = FailureType(
        category=FailureCategory.TOOL_FAILURE,
        severity=FailureSeverity.MEDIUM,
        recoverable=True,
        tool_name='workspace_write_file',
    )

    strategies = selector.rank(failure)

    assert len(strategies) >= 2
    assert strategies[0].name == 'inspect'
    assert any(s.name == 'undo' for s in strategies)
    assert any(s.name == 'retry' for s in strategies)


def test_strategy_matrix_coverage(selector):
    """Test that all failure categories have strategies."""
    for category in FailureCategory:
        failure = FailureType(
            category=category,
            severity=FailureSeverity.MEDIUM,
            recoverable=True,
        )
        strategies = selector.rank(failure)
        assert len(strategies) > 0, f'No strategies for {category}'


@pytest.fixture
def formatter():
    """Create a RecoveryAdviceFormatter instance."""
    return RecoveryAdviceFormatter()


def test_format_advice_text(formatter):
    """Test formatting recovery advice as text."""
    strategy = RecoveryStrategy(
        name='undo',
        command_template='teaagent undo --run {run_id}',
        requires_confirmation=True,
        destructive=True,
    )

    advice = RecoveryAdvice(
        strategy=strategy,
        reasoning='Failure type: tool_failure. Severity: medium. Recommended action: undo',
        confidence=0.9,
        alternatives=[
            RecoveryStrategy(
                name='inspect',
                command_template='teaagent audit view --run {run_id}',
                requires_confirmation=False,
                destructive=False,
            )
        ],
    )

    formatted = formatter.format(advice, run_id='test-run-123')

    assert 'RECOVERY RECOMMENDATION' in formatted
    assert 'Recommended Action: UNDO' in formatted
    assert 'Confidence: 90%' in formatted
    assert 'teaagent undo --run test-run-123' in formatted
    assert 'WARNING: This action is destructive' in formatted
    assert 'Alternative actions:' in formatted
    assert '1. inspect:' in formatted


def test_format_advice_json(formatter):
    """Test formatting recovery advice as JSON."""
    strategy = RecoveryStrategy(
        name='inspect',
        command_template='teaagent audit view --run {run_id}',
        requires_confirmation=False,
        destructive=False,
    )

    advice = RecoveryAdvice(
        strategy=strategy,
        reasoning='Failure type: unknown. Severity: high. Recommended action: inspect',
        confidence=0.5,
        alternatives=[],
    )

    json_output = formatter.format_json(advice, run_id='test-run-456')

    assert json_output['recommended_strategy']['name'] == 'inspect'
    assert (
        json_output['recommended_strategy']['command']
        == 'teaagent audit view --run test-run-456'
    )
    assert json_output['recommended_strategy']['requires_confirmation'] is False
    assert json_output['recommended_strategy']['destructive'] is False
    assert json_output['reasoning'] == advice.reasoning
    assert json_output['confidence'] == 0.5
    assert json_output['alternatives'] == []


def test_format_command_substitution(formatter):
    """Test command template substitution."""
    strategy = RecoveryStrategy(
        name='resume',
        command_template='teaagent run --resume {run_id} --timeout-extended',
        requires_confirmation=False,
        destructive=False,
    )

    advice = RecoveryAdvice(
        strategy=strategy,
        reasoning='Test reasoning',
        confidence=0.8,
        alternatives=[],
    )

    formatted = formatter.format(advice, run_id='my-run-id')
    assert 'teaagent run --resume my-run-id --timeout-extended' in formatted

    json_output = formatter.format_json(advice, run_id='my-run-id')
    assert (
        json_output['recommended_strategy']['command']
        == 'teaagent run --resume my-run-id --timeout-extended'
    )
