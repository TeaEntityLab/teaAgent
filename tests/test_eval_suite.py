"""Tests for eval suite framework (TASK-H5-001-01)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.eval_suite import (
    EvalCategory,
    EvalResult,
    EvalRunner,
    EvalStatus,
    EvalStore,
    EvalSuite,
    EvalTest,
)


def test_eval_test_to_dict_and_from_dict():
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

    assert restored.test_id == test.test_id
    assert restored.name == test.name
    assert restored.category == test.category


def test_eval_result_to_dict_and_from_dict():
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

    assert restored.test_id == result.test_id
    assert restored.status == result.status
    assert restored.duration_seconds == result.duration_seconds


def test_eval_suite_add_test():
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
    assert len(suite.tests) == 1
    assert suite.tests[0].test_id == 'test-001'


def test_eval_suite_get_tests_by_category():
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
    assert len(regression_tests) == 1
    assert regression_tests[0].test_id == 'test-001'


def test_eval_suite_get_enabled_tests():
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
    assert len(enabled_tests) == 1
    assert enabled_tests[0].test_id == 'test-001'


def test_eval_suite_to_dict_and_from_dict():
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

    assert restored.suite_id == suite.suite_id
    assert restored.name == suite.name
    assert len(restored.tests) == 1


@pytest.fixture
def eval_store():
    """Fixture for EvalStore with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = EvalStore(temp_dir.name)
    yield store
    # Verify cleanup
    import os

    temp_path = temp_dir.name
    assert os.path.exists(temp_path), (
        f'Temporary directory {temp_path} should still exist before cleanup'
    )
    temp_dir.cleanup()
    assert not os.path.exists(temp_path), (
        f'Temporary directory {temp_path} was not cleaned up'
    )


def test_eval_store_save_and_load_suite(eval_store):
    """Test saving and loading a suite."""
    suite = EvalSuite(
        suite_id='suite-001',
        name='Test Suite 1',
    )

    eval_store.save_suite(suite)
    loaded = eval_store.load_suite('suite-001')

    assert loaded is not None
    assert loaded.suite_id == suite.suite_id
    assert loaded.name == suite.name


def test_eval_store_list_suites(eval_store):
    """Test listing all suites."""
    suite1 = EvalSuite(
        suite_id='suite-001',
        name='Suite 1',
    )
    suite2 = EvalSuite(
        suite_id='suite-002',
        name='Suite 2',
    )

    eval_store.save_suite(suite1)
    eval_store.save_suite(suite2)

    suites = eval_store.list_suites()
    assert len(suites) == 2


def test_eval_store_save_and_load_result(eval_store):
    """Test saving and loading a result."""
    result = EvalResult(
        test_id='test-001',
        status=EvalStatus.PASSED,
        duration_seconds=10.5,
    )

    eval_store.save_result(result)
    loaded = eval_store.load_result('test-001')

    assert loaded is not None
    assert loaded.test_id == result.test_id
    assert loaded.status == result.status


def test_eval_store_save_and_load_baseline(eval_store):
    """Test saving and loading a baseline."""
    baseline_data = {'output': 'expected output', 'metrics': {'score': 95}}

    eval_store.save_baseline('baseline-001', baseline_data)
    loaded = eval_store.load_baseline('baseline-001')

    assert loaded is not None
    assert loaded['output'] == 'expected output'


@pytest.fixture
def eval_runner():
    """Fixture for EvalRunner with temporary directory."""
    temp_dir = TemporaryDirectory()
    store = EvalStore(temp_dir.name)
    runner = EvalRunner(store)
    yield runner, store
    temp_dir.cleanup()


def test_eval_runner_create_suite(eval_runner):
    """Test creating a new suite."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite', 'Test suite description')

    assert suite is not None
    assert suite.name == 'Test Suite'
    assert suite.description == 'Test suite description'


def test_eval_runner_add_test_to_suite(eval_runner):
    """Test adding a test to a suite."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    test, updated_suite = runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
        description='Test description',
    )

    assert test is not None
    assert test.name == 'Test 1'
    assert test.category == EvalCategory.PROMPT_REGRESSION


def test_eval_runner_run_suite(eval_runner):
    """Test running a suite."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.LONG_SESSION,
    )

    # Reload suite to get the updated tests
    suite = store.load_suite(suite.suite_id)
    results = runner.run_suite(suite)

    assert len(results) == 2
    assert all(r.status in [EvalStatus.PASSED, EvalStatus.ERROR] for r in results)
    simulated = [r for r in results if r.metrics.get('execution_mode') == 'simulated']
    assert simulated, 'expected at least one simulated execution metadata stamp'
    assert simulated[0].metrics['executor'] == 'placeholder'
    assert simulated[0].metrics['advisory_only'] is True


def test_eval_runner_repo_map_benchmark_executes_real_fixture(eval_runner):
    """M5: a repo-map benchmark runs a real deterministic fixture, not a sim.

    Regression guard for the release-gate wiring: the repo_map_benchmark
    category must produce non-advisory ``fixture`` execution metadata and pass
    when its expected symbols are actually defined in the target corpus.
    """
    runner, store = eval_runner
    corpus = Path(store.root) / 'rmb-corpus'
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / 'anchor.py').write_text(
        'def eval_suite_repo_map_anchor() -> int:\n    return 1\n', encoding='utf-8'
    )
    suite = runner.create_suite('Repo Map Suite')
    runner.add_test_to_suite(
        suite.suite_id,
        'Repo Map',
        EvalCategory.REPO_MAP_BENCHMARK,
        metadata={
            'codebase_path': str(corpus),
            'query': 'eval_suite_repo_map_anchor',
            'expected_files': ['anchor.py'],
            'expected_functions': ['eval_suite_repo_map_anchor'],
        },
    )
    suite = store.load_suite(suite.suite_id)
    (result,) = runner.run_suite(suite)

    assert result.status == EvalStatus.PASSED
    assert result.metrics['execution_mode'] == 'fixture'
    assert result.metrics['executor'] == 'repo_map_benchmark'
    assert result.metrics['advisory_only'] is False


def test_eval_runner_run_suite_with_category_filter(eval_runner):
    """Test running a suite with category filter."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Reload suite to get the updated tests
    suite = store.load_suite(suite.suite_id)
    results = runner.run_suite(suite, category_filter=EvalCategory.PROMPT_REGRESSION)

    assert len(results) == 1
    assert results[0].test_id == suite.tests[0].test_id


def test_eval_runner_get_suite_summary(eval_runner):
    """Test getting suite summary."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Reload suite to get the updated tests
    suite = store.load_suite(suite.suite_id)

    # Run the suite
    runner.run_suite(suite)

    summary = runner.get_suite_summary(suite.suite_id)

    assert summary['total_tests'] == 2
    assert summary['total_executed'] == 2
    assert 'success_rate' in summary
    assert 'total_duration_seconds' in summary


def test_eval_runner_disabled_test_not_executed(eval_runner):
    """Test that disabled tests are not executed."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
    )
    runner.add_test_to_suite(
        suite.suite_id,
        'Test 2',
        EvalCategory.REPO_MAP_BENCHMARK,
    )

    # Reload suite and disable the second test
    suite = store.load_suite(suite.suite_id)
    suite.tests[1].enabled = False
    store.save_suite(suite)

    results = runner.run_suite(suite)

    assert len(results) == 1
    assert results[0].test_id == suite.tests[0].test_id


def test_eval_runner_baseline_comparison(eval_runner):
    """Test baseline comparison in test execution."""
    runner, store = eval_runner
    suite = runner.create_suite('Test Suite')

    # Create a baseline
    baseline_data = {'output': 'expected output', 'metrics': {'score': 95}}
    store.save_baseline('baseline-001', baseline_data)

    runner.add_test_to_suite(
        suite.suite_id,
        'Test 1',
        EvalCategory.PROMPT_REGRESSION,
        baseline_path='baseline-001',
        metadata={'expected_output': 'expected output'},
    )

    # Reload suite to get the updated tests
    suite = store.load_suite(suite.suite_id)
    results = runner.run_suite(suite)

    assert len(results) == 1
    assert results[0].baseline_comparison is not None
