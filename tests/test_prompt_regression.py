"""Tests for prompt regression suite (TASK-H5-001-02)."""

import unittest

from teaagent.prompt_regression import (
    PromptRegressionEvaluator,
    PromptRegressionTest,
    RegressionResult,
    RegressionSeverity,
)


class TestPromptRegressionTest(unittest.TestCase):
    """Test prompt regression test management."""

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.test_id, test.test_id)
        self.assertEqual(restored.name, test.name)
        self.assertEqual(restored.prompt, test.prompt)


class TestRegressionResult(unittest.TestCase):
    """Test regression result management."""

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.test_id, result.test_id)
        self.assertEqual(restored.similarity_score, result.similarity_score)
        self.assertEqual(restored.severity, result.severity)


class TestPromptRegressionEvaluator(unittest.TestCase):
    """Test prompt regression evaluator."""

    def setUp(self):
        """Set up test fixtures."""
        self.evaluator = PromptRegressionEvaluator()

    def test_calculate_similarity_identical(self):
        """Test similarity calculation for identical texts."""
        text = 'This is a test string'
        similarity = self.evaluator.calculate_similarity(text, text)
        self.assertEqual(similarity, 1.0)

    def test_calculate_similarity_different(self):
        """Test similarity calculation for different texts."""
        text1 = 'This is a test string'
        text2 = 'Completely different text here'
        similarity = self.evaluator.calculate_similarity(text1, text2)
        self.assertLess(similarity, 1.0)
        self.assertGreaterEqual(similarity, 0.0)

    def test_calculate_similarity_empty(self):
        """Test similarity calculation for empty texts."""
        similarity = self.evaluator.calculate_similarity('', '')
        self.assertEqual(similarity, 1.0)

    def test_evaluate_behavior_match_keywords(self):
        """Test behavior match evaluation for keywords."""
        actual_output = 'The function calculates factorial using recursion'
        expected_behavior = {
            'keywords': ['function', 'factorial', 'recursion'],
        }

        matches = self.evaluator.evaluate_behavior_match(
            actual_output, expected_behavior
        )
        self.assertTrue(matches['keywords'])

    def test_evaluate_behavior_match_forbidden_keywords(self):
        """Test behavior match evaluation for forbidden keywords."""
        actual_output = 'The function works correctly'
        expected_behavior = {
            'forbidden_keywords': ['error', 'bug', 'wrong'],
        }

        matches = self.evaluator.evaluate_behavior_match(
            actual_output, expected_behavior
        )
        self.assertTrue(matches['forbidden_keywords'])

    def test_evaluate_behavior_match_length(self):
        """Test behavior match evaluation for length constraints."""
        actual_output = 'This is a test output'
        expected_behavior = {
            'min_length': 10,
            'max_length': 100,
        }

        matches = self.evaluator.evaluate_behavior_match(
            actual_output, expected_behavior
        )
        self.assertTrue(matches['min_length'])
        self.assertTrue(matches['max_length'])

    def test_determine_severity_none(self):
        """Test severity determination for no regression."""
        behavior_match = {'keywords': True, 'length': True}
        severity = self.evaluator.determine_severity(0.95, behavior_match, 0.9)
        self.assertEqual(severity, RegressionSeverity.NONE)

    def test_determine_severity_low(self):
        """Test severity determination for low regression."""
        behavior_match = {'keywords': True, 'length': True}
        severity = self.evaluator.determine_severity(0.78, behavior_match, 0.9)
        self.assertEqual(severity, RegressionSeverity.LOW)

    def test_determine_severity_critical(self):
        """Test severity determination for critical regression."""
        behavior_match = {'keywords': False, 'length': False}
        severity = self.evaluator.determine_severity(0.1, behavior_match, 0.9)
        self.assertEqual(severity, RegressionSeverity.CRITICAL)

    def test_evaluate_regression_passed(self):
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
        result = self.evaluator.evaluate_regression(test, actual_output)

        self.assertTrue(result.passed)
        self.assertEqual(result.severity, RegressionSeverity.NONE)

    def test_evaluate_regression_failed(self):
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
        result = self.evaluator.evaluate_regression(test, actual_output)

        self.assertFalse(result.passed)
        self.assertNotEqual(result.severity, RegressionSeverity.NONE)

    def test_create_default_regression_tests(self):
        """Test creating default regression tests."""
        tests = self.evaluator.create_default_regression_tests()

        self.assertGreaterEqual(len(tests), 3)
        self.assertTrue(all(isinstance(t, PromptRegressionTest) for t in tests))

    def test_convert_to_eval_test(self):
        """Test converting regression test to eval test."""
        regression_test = PromptRegressionTest(
            test_id='regression-001',
            name='Test 1',
            prompt='Test prompt',
            expected_output='Expected output',
        )

        eval_test = self.evaluator.convert_to_eval_test(regression_test)

        self.assertEqual(eval_test.test_id, regression_test.test_id)
        self.assertEqual(eval_test.name, regression_test.name)
        self.assertIn('prompt', eval_test.metadata)
        self.assertIn('expected_output', eval_test.metadata)


if __name__ == '__main__':
    unittest.main()
