"""Tests for eval suite framework (TASK-H5-001-01)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.eval_suite import (
    EvalCategory,
    EvalResult,
    EvalRunner,
    EvalStatus,
    EvalStore,
    EvalSuite,
    EvalTest,
)


class TestEvalTest(unittest.TestCase):
    """Test eval test management."""

    def test_to_dict_and_from_dict(self):
        """Test test serialization."""
        test = EvalTest(
            test_id='test-001',
            name='Test 1',
            category=EvalCategory.PROMPT_REGRESSION,
            description='Test description',
            timeout_seconds=120,
        )

        data = test.to_dict()
        restored = EvalTest.from_dict(data)

        self.assertEqual(restored.test_id, test.test_id)
        self.assertEqual(restored.name, test.name)
        self.assertEqual(restored.category, test.category)


class TestEvalResult(unittest.TestCase):
    """Test eval result management."""

    def test_to_dict_and_from_dict(self):
        """Test result serialization."""
        result = EvalResult(
            test_id='test-001',
            status=EvalStatus.PASSED,
            duration_seconds=10.5,
            output='Test output',
            metrics={'metric1': 100},
        )

        data = result.to_dict()
        restored = EvalResult.from_dict(data)

        self.assertEqual(restored.test_id, result.test_id)
        self.assertEqual(restored.status, result.status)
        self.assertEqual(restored.duration_seconds, result.duration_seconds)


class TestEvalSuite(unittest.TestCase):
    """Test eval suite management."""

    def test_add_test(self):
        """Test adding a test to a suite."""
        suite = EvalSuite(
            suite_id='suite-001',
            name='Test Suite 1',
        )

        test = EvalTest(
            test_id='test-001',
            name='Test 1',
            category=EvalCategory.PROMPT_REGRESSION,
        )

        suite.add_test(test)
        self.assertEqual(len(suite.tests), 1)
        self.assertEqual(suite.tests[0].test_id, 'test-001')

    def test_get_tests_by_category(self):
        """Test getting tests by category."""
        suite = EvalSuite(
            suite_id='suite-001',
            name='Test Suite 1',
        )

        test1 = EvalTest(
            test_id='test-001',
            name='Test 1',
            category=EvalCategory.PROMPT_REGRESSION,
        )
        test2 = EvalTest(
            test_id='test-002',
            name='Test 2',
            category=EvalCategory.REPO_MAP_BENCHMARK,
        )

        suite.add_test(test1)
        suite.add_test(test2)

        regression_tests = suite.get_tests_by_category(EvalCategory.PROMPT_REGRESSION)
        self.assertEqual(len(regression_tests), 1)
        self.assertEqual(regression_tests[0].test_id, 'test-001')

    def test_get_enabled_tests(self):
        """Test getting enabled tests."""
        suite = EvalSuite(
            suite_id='suite-001',
            name='Test Suite 1',
        )

        test1 = EvalTest(
            test_id='test-001',
            name='Test 1',
            category=EvalCategory.PROMPT_REGRESSION,
            enabled=True,
        )
        test2 = EvalTest(
            test_id='test-002',
            name='Test 2',
            category=EvalCategory.REPO_MAP_BENCHMARK,
            enabled=False,
        )

        suite.add_test(test1)
        suite.add_test(test2)

        enabled_tests = suite.get_enabled_tests()
        self.assertEqual(len(enabled_tests), 1)
        self.assertEqual(enabled_tests[0].test_id, 'test-001')

    def test_to_dict_and_from_dict(self):
        """Test suite serialization."""
        suite = EvalSuite(
            suite_id='suite-001',
            name='Test Suite 1',
            description='Test suite description',
        )

        test = EvalTest(
            test_id='test-001',
            name='Test 1',
            category=EvalCategory.PROMPT_REGRESSION,
        )
        suite.add_test(test)

        data = suite.to_dict()
        restored = EvalSuite.from_dict(data)

        self.assertEqual(restored.suite_id, suite.suite_id)
        self.assertEqual(restored.name, suite.name)
        self.assertEqual(len(restored.tests), 1)


class TestEvalStore(unittest.TestCase):
    """Test eval storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = EvalStore(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_save_and_load_suite(self):
        """Test saving and loading a suite."""
        suite = EvalSuite(
            suite_id='suite-001',
            name='Test Suite 1',
        )

        self.store.save_suite(suite)
        loaded = self.store.load_suite('suite-001')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.suite_id, suite.suite_id)
        self.assertEqual(loaded.name, suite.name)

    def test_list_suites(self):
        """Test listing all suites."""
        suite1 = EvalSuite(
            suite_id='suite-001',
            name='Suite 1',
        )
        suite2 = EvalSuite(
            suite_id='suite-002',
            name='Suite 2',
        )

        self.store.save_suite(suite1)
        self.store.save_suite(suite2)

        suites = self.store.list_suites()
        self.assertEqual(len(suites), 2)

    def test_save_and_load_result(self):
        """Test saving and loading a result."""
        result = EvalResult(
            test_id='test-001',
            status=EvalStatus.PASSED,
            duration_seconds=10.5,
        )

        self.store.save_result(result)
        loaded = self.store.load_result('test-001')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.test_id, result.test_id)
        self.assertEqual(loaded.status, result.status)

    def test_save_and_load_baseline(self):
        """Test saving and loading a baseline."""
        baseline_data = {'output': 'expected output', 'metrics': {'score': 95}}

        self.store.save_baseline('baseline-001', baseline_data)
        loaded = self.store.load_baseline('baseline-001')

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['output'], 'expected output')


class TestEvalRunner(unittest.TestCase):
    """Test eval runner execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = EvalStore(self.temp_dir.name)
        self.runner = EvalRunner(self.store)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_suite(self):
        """Test creating a new suite."""
        suite = self.runner.create_suite('Test Suite', 'Test suite description')

        self.assertIsNotNone(suite)
        self.assertEqual(suite.name, 'Test Suite')
        self.assertEqual(suite.description, 'Test suite description')

    def test_add_test_to_suite(self):
        """Test adding a test to a suite."""
        suite = self.runner.create_suite('Test Suite')

        test, updated_suite = self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
            description='Test description',
        )

        self.assertIsNotNone(test)
        self.assertEqual(test.name, 'Test 1')
        self.assertEqual(test.category, EvalCategory.PROMPT_REGRESSION)

    def test_run_suite(self):
        """Test running a suite."""
        suite = self.runner.create_suite('Test Suite')

        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Reload suite to get the updated tests
        suite = self.store.load_suite(suite.suite_id)
        results = self.runner.run_suite(suite)

        self.assertEqual(len(results), 2)
        self.assertTrue(
            all(r.status in [EvalStatus.PASSED, EvalStatus.ERROR] for r in results)
        )

    def test_run_suite_with_category_filter(self):
        """Test running a suite with category filter."""
        suite = self.runner.create_suite('Test Suite')

        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Reload suite to get the updated tests
        suite = self.store.load_suite(suite.suite_id)
        results = self.runner.run_suite(
            suite, category_filter=EvalCategory.PROMPT_REGRESSION
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].test_id, suite.tests[0].test_id)

    def test_get_suite_summary(self):
        """Test getting suite summary."""
        suite = self.runner.create_suite('Test Suite')

        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Reload suite to get the updated tests
        suite = self.store.load_suite(suite.suite_id)

        # Run the suite
        self.runner.run_suite(suite)

        summary = self.runner.get_suite_summary(suite.suite_id)

        self.assertEqual(summary['total_tests'], 2)
        self.assertEqual(summary['total_executed'], 2)
        self.assertIn('success_rate', summary)
        self.assertIn('total_duration_seconds', summary)

    def test_disabled_test_not_executed(self):
        """Test that disabled tests are not executed."""
        suite = self.runner.create_suite('Test Suite')

        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Reload suite and disable the second test
        suite = self.store.load_suite(suite.suite_id)
        suite.tests[1].enabled = False
        self.store.save_suite(suite)

        results = self.runner.run_suite(suite)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].test_id, suite.tests[0].test_id)

    def test_baseline_comparison(self):
        """Test baseline comparison in test execution."""
        suite = self.runner.create_suite('Test Suite')

        # Create a baseline
        baseline_data = {'output': 'expected output', 'metrics': {'score': 95}}
        self.store.save_baseline('baseline-001', baseline_data)

        self.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
            baseline_path='baseline-001',
        )

        # Reload suite to get the updated tests
        suite = self.store.load_suite(suite.suite_id)
        results = self.runner.run_suite(suite)

        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].baseline_comparison)


if __name__ == '__main__':
    unittest.main()
