"""Tests for long-session context health tests (TASK-H5-001-04)."""

import pytest

from teaagent.context_health import (
    ContextHealthEvaluator,
    ContextHealthResult,
    ContextHealthTest,
)


def test_to_dict_and_from_dict():
    """Test test serialization."""
    test = ContextHealthTest(
        test_id='health-001',
        name='Test 1',
        session_length=10,
        context_window_size=1000,
    )

    data = test.to_dict()
    restored = ContextHealthTest.from_dict(data)

    assert restored.test_id == test.test_id
    assert restored.name == test.name
    assert restored.session_length == test.session_length


def test_result_to_dict_and_from_dict():
    """Test result serialization."""
    result = ContextHealthResult(
        test_id='health-001',
        actual_retention_rate=0.85,
        overall_health_score=0.9,
        passed=True,
    )

    data = result.to_dict()
    restored = ContextHealthResult.from_dict(data)

    assert restored.test_id == result.test_id
    assert restored.actual_retention_rate == result.actual_retention_rate
    assert restored.passed == result.passed


@pytest.fixture
def evaluator():
    """Fixture for ContextHealthEvaluator."""
    return ContextHealthEvaluator()


def test_calculate_retention_rate_perfect(evaluator):
    """Test retention rate calculation for perfect retention."""
    initial = ['item1', 'item2', 'item3']
    final = ['item1', 'item2', 'item3']
    retention = evaluator.calculate_retention_rate(initial, final)
    assert retention == 1.0


def test_calculate_retention_rate_partial(evaluator):
    """Test retention rate calculation for partial retention."""
    initial = ['item1', 'item2', 'item3']
    final = ['item1', 'item2']
    retention = evaluator.calculate_retention_rate(initial, final)
    assert abs(retention - 2 / 3) < 0.01


def test_calculate_retention_rate_empty(evaluator):
    """Test retention rate calculation for empty context."""
    retention = evaluator.calculate_retention_rate([], [])
    assert retention == 1.0


def test_calculate_consistency_score_perfect(evaluator):
    """Test consistency score calculation for perfect consistency."""
    history = [
        ['item1', 'item2'],
        ['item1', 'item2'],
        ['item1', 'item2'],
    ]
    consistency = evaluator.calculate_consistency_score(history)
    assert consistency == 1.0


def test_calculate_consistency_score_partial(evaluator):
    """Test consistency score calculation for partial consistency."""
    history = [
        ['item1', 'item2'],
        ['item1', 'item3'],
        ['item1', 'item4'],
    ]
    consistency = evaluator.calculate_consistency_score(history)
    assert consistency < 1.0
    assert consistency > 0.0


def test_calculate_memory_growth(evaluator):
    """Test memory growth calculation."""
    growth = evaluator.calculate_memory_growth(1000, 1500)
    assert growth == 1.5


def test_calculate_memory_growth_zero_initial(evaluator):
    """Test memory growth calculation with zero initial."""
    growth = evaluator.calculate_memory_growth(0, 1000)
    assert growth == 1.0


def test_calculate_drift_score_no_drift(evaluator):
    """Test drift score calculation for no drift."""
    initial = ['item1', 'item2']
    final = ['item1', 'item2']
    drift = evaluator.calculate_drift_score(initial, final)
    assert drift == 0.0


def test_calculate_drift_score_with_drift(evaluator):
    """Test drift score calculation with drift."""
    initial = ['item1', 'item2']
    final = ['item1', 'item2', 'item3', 'item4']
    drift = evaluator.calculate_drift_score(initial, final)
    assert drift == 1.0


def test_calculate_relevance_score_perfect(evaluator):
    """Test relevance score calculation for perfect relevance."""
    task = 'implement authentication'
    context = [
        'implement authentication',
        'implement authentication',
        'implement authentication',
    ]
    relevance = evaluator.calculate_relevance_score(task, context)
    assert relevance == 1.0


def test_calculate_relevance_score_partial(evaluator):
    """Test relevance score calculation for partial relevance."""
    task = 'implement authentication'
    context = ['implement authentication', 'database setup', 'user interface']
    relevance = evaluator.calculate_relevance_score(task, context)
    assert relevance < 1.0
    assert relevance > 0.0


def test_evaluate_context_health_passed(evaluator):
    """Test context health evaluation when passed."""
    test = ContextHealthTest(
        test_id='health-001',
        name='Test 1',
        session_length=10,
        context_window_size=1000,
        expected_retention_rate=0.9,
        max_memory_growth=1.5,
    )

    session_data = {
        'initial_context': ['item1', 'item2', 'item3'],
        'final_context': ['item1', 'item2', 'item3'],
        'context_history': [['item1', 'item2'], ['item1', 'item2', 'item3']],
        'initial_memory_size': 1000,
        'final_memory_size': 1200,
        'current_task': 'item1 item2',  # Make task relevant to context
    }

    result = evaluator.evaluate_context_health(test, session_data)

    assert result.passed
    assert result.actual_retention_rate == 1.0


def test_evaluate_context_health_failed(evaluator):
    """Test context health evaluation when failed."""
    test = ContextHealthTest(
        test_id='health-001',
        name='Test 1',
        session_length=10,
        context_window_size=1000,
        expected_retention_rate=0.9,
        max_memory_growth=1.5,
    )

    session_data = {
        'initial_context': ['item1', 'item2', 'item3'],
        'final_context': ['item4'],  # Poor retention
        'context_history': [['item1'], ['item4']],
        'initial_memory_size': 1000,
        'final_memory_size': 3000,  # Excessive memory growth
        'current_task': 'item4',  # Make task relevant to final context
    }

    result = evaluator.evaluate_context_health(test, session_data)

    assert not result.passed


def test_create_default_context_health_tests(evaluator):
    """Test creating default context health tests."""
    tests = evaluator.create_default_context_health_tests()

    assert len(tests) >= 3
    assert all(isinstance(t, ContextHealthTest) for t in tests)


def test_convert_to_eval_test(evaluator):
    """Test converting context health test to eval test."""
    health_test = ContextHealthTest(
        test_id='health-001',
        name='Test 1',
        session_length=10,
        context_window_size=1000,
    )

    eval_test = evaluator.convert_to_eval_test(health_test)

    assert eval_test.test_id == health_test.test_id
    assert eval_test.name == health_test.name
    assert 'session_length' in eval_test.metadata
    assert 'context_window_size' in eval_test.metadata
