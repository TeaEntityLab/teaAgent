"""Tests for long-session context health tests (TASK-H5-001-04)."""

import unittest

from teaagent.context_health import (
    ContextHealthEvaluator,
    ContextHealthResult,
    ContextHealthTest,
)


class TestContextHealthTest(unittest.TestCase):
    """Test context health test management."""

    def test_to_dict_and_from_dict(self):
        """Test test serialization."""
        test = ContextHealthTest(
            test_id='health-001',
            name='Test 1',
            session_length=10,
            context_window_size=1000,
        )

        data = test.to_dict()
        restored = ContextHealthTest.from_dict(data)

        self.assertEqual(restored.test_id, test.test_id)
        self.assertEqual(restored.name, test.name)
        self.assertEqual(restored.session_length, test.session_length)


class TestContextHealthResult(unittest.TestCase):
    """Test context health result management."""

    def test_to_dict_and_from_dict(self):
        """Test result serialization."""
        result = ContextHealthResult(
            test_id='health-001',
            actual_retention_rate=0.85,
            overall_health_score=0.9,
            passed=True,
        )

        data = result.to_dict()
        restored = ContextHealthResult.from_dict(data)

        self.assertEqual(restored.test_id, result.test_id)
        self.assertEqual(restored.actual_retention_rate, result.actual_retention_rate)
        self.assertEqual(restored.passed, result.passed)


class TestContextHealthEvaluator(unittest.TestCase):
    """Test context health evaluator."""

    def setUp(self):
        """Set up test fixtures."""
        self.evaluator = ContextHealthEvaluator()

    def test_calculate_retention_rate_perfect(self):
        """Test retention rate calculation for perfect retention."""
        initial = ['item1', 'item2', 'item3']
        final = ['item1', 'item2', 'item3']
        retention = self.evaluator.calculate_retention_rate(initial, final)
        self.assertEqual(retention, 1.0)

    def test_calculate_retention_rate_partial(self):
        """Test retention rate calculation for partial retention."""
        initial = ['item1', 'item2', 'item3']
        final = ['item1', 'item2']
        retention = self.evaluator.calculate_retention_rate(initial, final)
        self.assertAlmostEqual(retention, 2 / 3, places=2)

    def test_calculate_retention_rate_empty(self):
        """Test retention rate calculation for empty context."""
        retention = self.evaluator.calculate_retention_rate([], [])
        self.assertEqual(retention, 1.0)

    def test_calculate_consistency_score_perfect(self):
        """Test consistency score calculation for perfect consistency."""
        history = [
            ['item1', 'item2'],
            ['item1', 'item2'],
            ['item1', 'item2'],
        ]
        consistency = self.evaluator.calculate_consistency_score(history)
        self.assertEqual(consistency, 1.0)

    def test_calculate_consistency_score_partial(self):
        """Test consistency score calculation for partial consistency."""
        history = [
            ['item1', 'item2'],
            ['item1', 'item3'],
            ['item1', 'item4'],
        ]
        consistency = self.evaluator.calculate_consistency_score(history)
        self.assertLess(consistency, 1.0)
        self.assertGreater(consistency, 0.0)

    def test_calculate_memory_growth(self):
        """Test memory growth calculation."""
        growth = self.evaluator.calculate_memory_growth(1000, 1500)
        self.assertEqual(growth, 1.5)

    def test_calculate_memory_growth_zero_initial(self):
        """Test memory growth calculation with zero initial."""
        growth = self.evaluator.calculate_memory_growth(0, 1000)
        self.assertEqual(growth, 1.0)

    def test_calculate_drift_score_no_drift(self):
        """Test drift score calculation for no drift."""
        initial = ['item1', 'item2']
        final = ['item1', 'item2']
        drift = self.evaluator.calculate_drift_score(initial, final)
        self.assertEqual(drift, 0.0)

    def test_calculate_drift_score_with_drift(self):
        """Test drift score calculation with drift."""
        initial = ['item1', 'item2']
        final = ['item1', 'item2', 'item3', 'item4']
        drift = self.evaluator.calculate_drift_score(initial, final)
        self.assertEqual(drift, 1.0)

    def test_calculate_relevance_score_perfect(self):
        """Test relevance score calculation for perfect relevance."""
        task = 'implement authentication'
        context = [
            'implement authentication',
            'implement authentication',
            'implement authentication',
        ]
        relevance = self.evaluator.calculate_relevance_score(task, context)
        self.assertEqual(relevance, 1.0)

    def test_calculate_relevance_score_partial(self):
        """Test relevance score calculation for partial relevance."""
        task = 'implement authentication'
        context = ['implement authentication', 'database setup', 'user interface']
        relevance = self.evaluator.calculate_relevance_score(task, context)
        self.assertLess(relevance, 1.0)
        self.assertGreater(relevance, 0.0)

    def test_evaluate_context_health_passed(self):
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

        result = self.evaluator.evaluate_context_health(test, session_data)

        self.assertTrue(result.passed)
        self.assertEqual(result.actual_retention_rate, 1.0)

    def test_evaluate_context_health_failed(self):
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

        result = self.evaluator.evaluate_context_health(test, session_data)

        self.assertFalse(result.passed)

    def test_create_default_context_health_tests(self):
        """Test creating default context health tests."""
        tests = self.evaluator.create_default_context_health_tests()

        self.assertGreaterEqual(len(tests), 3)
        self.assertTrue(all(isinstance(t, ContextHealthTest) for t in tests))

    def test_convert_to_eval_test(self):
        """Test converting context health test to eval test."""
        health_test = ContextHealthTest(
            test_id='health-001',
            name='Test 1',
            session_length=10,
            context_window_size=1000,
        )

        eval_test = self.evaluator.convert_to_eval_test(health_test)

        self.assertEqual(eval_test.test_id, health_test.test_id)
        self.assertEqual(eval_test.name, health_test.name)
        self.assertIn('session_length', eval_test.metadata)
        self.assertIn('context_window_size', eval_test.metadata)


if __name__ == '__main__':
    unittest.main()
