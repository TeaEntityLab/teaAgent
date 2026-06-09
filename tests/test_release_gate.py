"""Tests for release pipeline integration (TASK-H5-001-06)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.eval_suite import EvalCategory, EvalResult, EvalStatus, EvalStore
from teaagent.release_gate import (
    ReleaseDecision,
    ReleaseGate,
    ReleaseGateConfig,
    ReleaseGateResult,
)


class TestReleaseGateConfig(unittest.TestCase):
    """Test release gate configuration."""

    def test_to_dict_and_from_dict(self):
        """Test config serialization."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.95,
            critical_test_categories={'prompt_regression'},
        )

        data = config.to_dict()
        restored = ReleaseGateConfig.from_dict(data)

        self.assertEqual(restored.gate_id, config.gate_id)
        self.assertEqual(restored.required_success_rate, config.required_success_rate)


class TestReleaseGateResult(unittest.TestCase):
    """Test release gate result."""

    def test_to_dict_and_from_dict(self):
        """Test result serialization."""
        result = ReleaseGateResult(
            gate_id='gate-001',
            decision=ReleaseDecision.APPROVE,
            success_rate=0.95,
            passed_tests=19,
            failed_tests=1,
        )

        data = result.to_dict()
        restored = ReleaseGateResult.from_dict(data)

        self.assertEqual(restored.gate_id, result.gate_id)
        self.assertEqual(restored.decision, result.decision)
        self.assertEqual(restored.success_rate, result.success_rate)


class TestReleaseGate(unittest.TestCase):
    """Test release gate integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.store = EvalStore(self.temp_dir.name)
        self.gate = ReleaseGate(self.store)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_evaluate_gate_approve(self):
        """Test gate evaluation with approval."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.9,
        )

        # Create suite with passing results
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Create passing results
        suite = self.store.load_suite(suite.suite_id)
        for test in suite.tests:
            result = EvalResult(
                test_id=test.test_id,
                status=EvalStatus.PASSED,
            )
            self.store.save_result(result)

        gate_result = self.gate.evaluate_gate(config, suite.suite_id)

        self.assertEqual(gate_result.decision, ReleaseDecision.APPROVE)
        self.assertEqual(gate_result.passed_tests, 2)

    def test_evaluate_gate_block_low_success_rate(self):
        """Test gate evaluation blocked by low success rate."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.9,
        )

        # Create suite with mixed results
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Create mixed results
        suite = self.store.load_suite(suite.suite_id)
        result1 = EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.PASSED,
        )
        result2 = EvalResult(
            test_id=suite.tests[1].test_id,
            status=EvalStatus.FAILED,
        )
        self.store.save_result(result1)
        self.store.save_result(result2)

        result = self.gate.evaluate_gate(config, suite.suite_id)

        self.assertEqual(result.decision, ReleaseDecision.BLOCK)
        self.assertIn('success rate', result.summary)

    def test_evaluate_gate_block_critical_failure(self):
        """Test gate evaluation blocked by critical failure."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.5,
            critical_test_categories={'prompt_regression'},
            block_on_critical_failure=True,
        )

        # Create suite with critical failure
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Create results with critical failure
        suite = self.store.load_suite(suite.suite_id)
        result1 = EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.FAILED,
        )
        result2 = EvalResult(
            test_id=suite.tests[1].test_id,
            status=EvalStatus.PASSED,
        )
        self.store.save_result(result1)
        self.store.save_result(result2)

        result = self.gate.evaluate_gate(config, suite.suite_id)

        self.assertEqual(result.decision, ReleaseDecision.BLOCK)
        self.assertEqual(len(result.critical_failures), 1)

    def test_evaluate_gate_warn(self):
        """Test gate evaluation with warnings."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.5,  # Lower threshold to allow warnings
            allow_warnings=True,
        )

        # Create suite with error results
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 2',
            EvalCategory.REPO_MAP_BENCHMARK,
        )

        # Create mixed results (one passed, one error)
        suite = self.store.load_suite(suite.suite_id)
        result1 = EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.PASSED,
        )
        result2 = EvalResult(
            test_id=suite.tests[1].test_id,
            status=EvalStatus.ERROR,
            error_message='Test error',
        )
        self.store.save_result(result1)
        self.store.save_result(result2)

        result = self.gate.evaluate_gate(config, suite.suite_id)

        self.assertEqual(result.decision, ReleaseDecision.WARN)
        self.assertGreater(len(result.warnings), 0)

    def test_run_and_evaluate(self):
        """Test running suite and evaluating gate."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
            required_success_rate=0.9,
        )

        # Create suite
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )

        # Run and evaluate
        result = self.gate.run_and_evaluate(config, suite.suite_id)

        self.assertIn(result.decision, [ReleaseDecision.APPROVE, ReleaseDecision.WARN])

    def test_create_default_gate_config(self):
        """Test creating default gate configuration."""
        config = self.gate.create_default_gate_config()

        self.assertEqual(config.gate_id, 'default-gate')
        self.assertEqual(config.required_success_rate, 0.9)
        self.assertIn('prompt_regression', config.critical_test_categories)

    def test_export_gate_report(self):
        """Test exporting gate report."""
        config = ReleaseGateConfig(
            gate_id='gate-001',
            name='Test Gate',
        )

        # Create suite and results
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )

        suite = self.store.load_suite(suite.suite_id)
        result = EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.PASSED,
        )
        self.store.save_result(result)

        gate_result = self.gate.evaluate_gate(config, suite.suite_id)

        # Export report
        report_path = Path(self.temp_dir.name) / 'gate_report.json'
        self.gate.export_gate_report(gate_result, report_path)

        self.assertTrue(report_path.exists())

    def test_create_release_bundle(self):
        """Test creating release bundle."""
        # Create suite and results
        suite = self.gate.runner.create_suite('Test Suite')
        self.gate.runner.add_test_to_suite(
            suite.suite_id,
            'Test 1',
            EvalCategory.PROMPT_REGRESSION,
        )

        suite = self.store.load_suite(suite.suite_id)
        result = EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.PASSED,
        )
        self.store.save_result(result)

        # Create bundle
        bundle_path = Path(self.temp_dir.name) / 'release_bundle.json'
        metadata = self.gate.create_release_bundle(suite.suite_id, bundle_path)

        self.assertTrue(bundle_path.exists())
        self.assertEqual(metadata['test_count'], 1)
        self.assertEqual(metadata['result_count'], 1)


if __name__ == '__main__':
    unittest.main()
