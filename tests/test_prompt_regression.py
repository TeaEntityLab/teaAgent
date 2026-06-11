"""Tests for prompt regression suite (TASK-H5-001-02)."""

import pytest

from teaagent.prompt_regression import (
    PromptRegressionEvaluator,
    PromptRegressionTest,
    RegressionResult,
    RegressionSeverity,
)


def test_prompt_regression_test_to_dict_and_from_dict():
    """Test test serialization."""
    test = PromptRegressionTest(
        test_id='regression-001',
        name='Test 1',
        prompt='Test prompt',
        expected_output='Expected output',
        tolerance_threshold=0.8,
    )

    data = test.to_dict()
    restored = PromptRegressionTest.from_dict(data)

    assert restored.test_id == test.test_id
    assert restored.name == test.name
    assert restored.prompt == test.prompt


def test_regression_result_to_dict_and_from_dict():
    """Test result serialization."""
    result = RegressionResult(
        test_id='regression-001',
        actual_output='Actual output',
        similarity_score=0.85,
        severity=RegressionSeverity.LOW,
        passed=True,
    )

    data = result.to_dict()
    restored = RegressionResult.from_dict(data)

    assert restored.test_id == result.test_id
    assert restored.similarity_score == result.similarity_score
    assert restored.severity == result.severity


@pytest.fixture
def regression_evaluator():
    """Fixture for PromptRegressionEvaluator."""
    return PromptRegressionEvaluator()


def test_calculate_similarity_identical(regression_evaluator):
    """Test similarity calculation for identical texts."""
    text = 'This is a test string'
    similarity = regression_evaluator.calculate_similarity(text, text)
    assert similarity == 1.0


def test_calculate_similarity_different(regression_evaluator):
    """Test similarity calculation for different texts."""
    text1 = 'This is a test string'
    text2 = 'Completely different text here'
    similarity = regression_evaluator.calculate_similarity(text1, text2)
    assert similarity < 1.0
    assert similarity >= 0.0


def test_calculate_similarity_empty(regression_evaluator):
    """Test similarity calculation for empty texts."""
    similarity = regression_evaluator.calculate_similarity('', '')
    assert similarity == 1.0


def test_evaluate_behavior_match_keywords(regression_evaluator):
    """Test behavior match evaluation for keywords."""
    actual_output = 'The function calculates factorial using recursion'
    expected_behavior = {
        'keywords': ['function', 'factorial', 'recursion'],
    }

    matches = regression_evaluator.evaluate_behavior_match(
        actual_output, expected_behavior
    )
    assert matches['keywords'] is True


def test_evaluate_behavior_match_forbidden_keywords(regression_evaluator):
    """Test behavior match evaluation for forbidden keywords."""
    actual_output = 'The function works correctly'
    expected_behavior = {
        'forbidden_keywords': ['error', 'bug', 'wrong'],
    }

    matches = regression_evaluator.evaluate_behavior_match(
        actual_output, expected_behavior
    )
    assert matches['forbidden_keywords'] is True


def test_evaluate_behavior_match_length(regression_evaluator):
    """Test behavior match evaluation for length constraints."""
    actual_output = 'This is a test output'
    expected_behavior = {
        'min_length': 10,
        'max_length': 100,
    }

    matches = regression_evaluator.evaluate_behavior_match(
        actual_output, expected_behavior
    )
    assert matches['min_length'] is True
    assert matches['max_length'] is True


def test_determine_severity_none(regression_evaluator):
    """Test severity determination for no regression."""
    behavior_match = {'keywords': True, 'length': True}
    severity = regression_evaluator.determine_severity(0.95, behavior_match, 0.9)
    assert severity == RegressionSeverity.NONE


def test_determine_severity_low(regression_evaluator):
    """Test severity determination for low regression."""
    behavior_match = {'keywords': True, 'length': True}
    severity = regression_evaluator.determine_severity(0.78, behavior_match, 0.9)
    assert severity == RegressionSeverity.LOW


def test_determine_severity_critical(regression_evaluator):
    """Test severity determination for critical regression."""
    behavior_match = {'keywords': False, 'length': False}
    severity = regression_evaluator.determine_severity(0.1, behavior_match, 0.9)
    assert severity == RegressionSeverity.CRITICAL


def test_evaluate_regression_passed(regression_evaluator):
    """Test regression evaluation when passed."""
    test = PromptRegressionTest(
        test_id='regression-001',
        name='Test 1',
        prompt='Test prompt',
        expected_output='Expected output with some keywords',
        expected_behavior={'keywords': ['keywords']},
        tolerance_threshold=0.8,
    )

    actual_output = 'Expected output with some keywords'
    result = regression_evaluator.evaluate_regression(test, actual_output)

    assert result.passed is True
    assert result.severity == RegressionSeverity.NONE


def test_evaluate_regression_failed(regression_evaluator):
    """Test regression evaluation when failed."""
    test = PromptRegressionTest(
        test_id='regression-001',
        name='Test 1',
        prompt='Test prompt',
        expected_output='Expected output with keywords',
        expected_behavior={'keywords': ['keywords']},
        tolerance_threshold=0.9,
    )

    actual_output = 'Completely different output without expected terms'
    result = regression_evaluator.evaluate_regression(test, actual_output)

    assert result.passed is False
    assert result.severity != RegressionSeverity.NONE


def test_create_default_regression_tests(regression_evaluator):
    """Test creating default regression tests."""
    tests = regression_evaluator.create_default_regression_tests()

    assert len(tests) >= 3
    assert all(isinstance(t, PromptRegressionTest) for t in tests)


def test_convert_to_eval_test(regression_evaluator):
    """Test converting regression test to eval test."""
    regression_test = PromptRegressionTest(
        test_id='regression-001',
        name='Test 1',
        prompt='Test prompt',
        expected_output='Expected output',
    )

    eval_test = regression_evaluator.convert_to_eval_test(regression_test)

    assert eval_test.test_id == regression_test.test_id
    assert eval_test.name == regression_test.name
    assert 'prompt' in eval_test.metadata
    assert 'expected_output' in eval_test.metadata
