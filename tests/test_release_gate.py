"""Tests for release pipeline integration (TASK-H5-001-06)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from teaagent.release_gate import (
    ReleaseDecision,
    ReleaseGate,
    ReleaseGateConfig,
    ReleaseGateResult,
)

from teaagent.eval_suite import EvalCategory, EvalResult, EvalStatus, EvalStore


def test_release_gate_config_to_dict_and_from_dict():
    """Test config serialization."""
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.95,
        critical_test_categories={'prompt_regression'},
    )

    data = config.to_dict()
    restored = ReleaseGateConfig.from_dict(data)

    assert restored.gate_id == config.gate_id
    assert restored.required_success_rate == config.required_success_rate


def test_release_gate_result_to_dict_and_from_dict():
    """Test result serialization."""
    result = ReleaseGateResult(
        gate_id='gate-001',
        decision=ReleaseDecision.APPROVE,
        success_rate=0.95,
        passed_tests=19,
        failed_tests=1,
        simulated=True,
        advisory_only=True,
    )

    data = result.to_dict()
    restored = ReleaseGateResult.from_dict(data)

    assert restored.gate_id == result.gate_id
    assert restored.decision == result.decision
    assert restored.success_rate == result.success_rate
    assert restored.simulated is True
    assert restored.advisory_only is True


@pytest.fixture
def release_gate():
    """Fixture for ReleaseGate with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = EvalStore(temp_dir.name)
    gate = ReleaseGate(store)
    yield gate, store
    temp_dir.cleanup()


def test_release_gate_evaluate_gate_approve(release_gate):
    """Test gate evaluation with approval."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.9,
    )

    # Create suite with passing results
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Create passing results
    suite = store.load_suite(suite.suite_id)
    for test in suite.tests:
        result = EvalResult(
            test_id=test.test_id,
            status=EvalStatus.PASSED,
        )
        store.save_result(result)

    gate_result = gate.evaluate_gate(config, suite.suite_id)

    assert gate_result.decision == ReleaseDecision.APPROVE
    assert gate_result.passed_tests == 2


def test_release_gate_evaluate_gate_block_low_success_rate(release_gate):
    """Test gate evaluation blocked by low success rate."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.9,
    )

    # Create suite with mixed results
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Create mixed results
    suite = store.load_suite(suite.suite_id)
    result1 = EvalResult(
        test_id=suite.tests[0].test_id,
        status=EvalStatus.PASSED,
    )
    result2 = EvalResult(
        test_id=suite.tests[1].test_id,
        status=EvalStatus.FAILED,
    )
    store.save_result(result1)
    store.save_result(result2)

    result = gate.evaluate_gate(config, suite.suite_id)

    assert result.decision == ReleaseDecision.BLOCK
    assert 'success rate' in result.summary


def test_release_gate_evaluate_gate_block_critical_failure(release_gate):
    """Test gate evaluation blocked by critical failure."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.5,
        critical_test_categories={'prompt_regression'},
        block_on_critical_failure=True,
    )

    # Create suite with critical failure
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Create results with critical failure
    suite = store.load_suite(suite.suite_id)
    result1 = EvalResult(
        test_id=suite.tests[0].test_id,
        status=EvalStatus.FAILED,
    )
    result2 = EvalResult(
        test_id=suite.tests[1].test_id,
        status=EvalStatus.PASSED,
    )
    store.save_result(result1)
    store.save_result(result2)

    result = gate.evaluate_gate(config, suite.suite_id)

    assert result.decision == ReleaseDecision.BLOCK
    assert len(result.critical_failures) == 1


def test_release_gate_blocks_empty_critical_category(release_gate):
    """Test gate blocks when a critical category has no enabled tests."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.5,
        critical_test_categories={'repo_map_benchmark'},
        block_on_critical_failure=True,
    )

    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    suite = store.load_suite(suite.suite_id)
    assert suite is not None
    store.save_result(
        EvalResult(
            test_id=suite.tests[0].test_id,
            status=EvalStatus.PASSED,
        )
    )

    result = gate.evaluate_gate(config, suite.suite_id)

    assert result.decision == ReleaseDecision.BLOCK
    assert result.critical_failures == ['missing-category:repo_map_benchmark']
    assert 'missing critical categories' in result.summary


def test_release_gate_evaluate_gate_warn(release_gate):
    """Test gate evaluation with warnings."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.5,  # Lower threshold to allow warnings
        allow_warnings=True,
    )

    # Create suite with error results
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Create mixed results (one passed, one error)
    suite = store.load_suite(suite.suite_id)
    result1 = EvalResult(
        test_id=suite.tests[0].test_id,
        status=EvalStatus.PASSED,
    )
    result2 = EvalResult(
        test_id=suite.tests[1].test_id,
        status=EvalStatus.ERROR,
        error_message='Test error',
    )
    store.save_result(result1)
    store.save_result(result2)

    result = gate.evaluate_gate(config, suite.suite_id)

    assert result.decision == ReleaseDecision.WARN
    assert len(result.warnings) > 0


def test_release_gate_run_and_evaluate(release_gate):
    """Test running suite and evaluating gate."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
        required_success_rate=0.9,
    )

    # Create suite
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Run and evaluate
    result = gate.run_and_evaluate(config, suite.suite_id)

    assert result.decision == ReleaseDecision.APPROVE
    assert result.simulated is False
    assert result.advisory_only is False
    assert result.details['execution_mode'] == 'real'
    assert 'advisory_note' not in result.details


def test_release_gate_create_default_gate_config(release_gate):
    """Test creating default gate configuration."""
    gate, store = release_gate
    config = gate.create_default_gate_config()

    assert config.gate_id == 'default-gate'
    assert config.required_success_rate == 0.9
    assert 'prompt_regression' in config.critical_test_categories


def test_release_gate_export_gate_report(release_gate):
    """Test exporting gate report."""
    gate, store = release_gate
    config = ReleaseGateConfig(
        gate_id='gate-001',
        name='Test Gate',
    )

    # Create suite and results
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )

    suite = store.load_suite(suite.suite_id)
    result = EvalResult(
        test_id=suite.tests[0].test_id,
        status=EvalStatus.PASSED,
    )
    store.save_result(result)

    gate_result = gate.evaluate_gate(config, suite.suite_id)

    # Export report
    temp_dir = TemporaryDirectory()
    report_path = Path(temp_dir.name) / 'gate_report.json'
    gate.export_gate_report(gate_result, report_path)

    assert report_path.exists()
    temp_dir.cleanup()


def test_release_gate_create_release_bundle(release_gate):
    """Test creating release bundle."""
    gate, store = release_gate
    # Create suite and results
    suite = gate.runner.create_suite('Test Suite')
    gate.runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )

    suite = store.load_suite(suite.suite_id)
    result = EvalResult(
        test_id=suite.tests[0].test_id,
        status=EvalStatus.PASSED,
    )
    store.save_result(result)

    # Create bundle
    temp_dir = TemporaryDirectory()
    bundle_path = Path(temp_dir.name) / 'release_bundle.json'
    metadata = gate.create_release_bundle(suite.suite_id, bundle_path)

    assert bundle_path.exists()
    assert metadata['test_count'] == 1
    assert metadata['result_count'] == 1
    temp_dir.cleanup()
