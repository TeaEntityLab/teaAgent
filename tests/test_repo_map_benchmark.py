"""Tests for repo-map benchmark automation (TASK-H5-001-03)."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from teaagent.repo_map_benchmark import (
    BenchmarkResult,
    RepoMapBenchmark,
    RepoMapBenchmarkRunner,
)


def test_repo_map_benchmark_to_dict_and_from_dict():
    """Test benchmark serialization."""
    benchmark = RepoMapBenchmark(
        benchmark_id='benchmark-001',
        name='Test Benchmark',
        codebase_path='.',
        query='test query',
        expected_files={'file1.py', 'file2.py'},
    )

    data = benchmark.to_dict()
    restored = RepoMapBenchmark.from_dict(data)

    assert restored.benchmark_id == benchmark.benchmark_id
    assert restored.name == benchmark.name
    assert restored.expected_files == benchmark.expected_files


def test_benchmark_result_to_dict_and_from_dict():
    """Test result serialization."""
    result = BenchmarkResult(
        benchmark_id='benchmark-001',
        actual_files={'file1.py', 'file2.py'},
        overall_accuracy=0.85,
        passed=True,
    )

    data = result.to_dict()
    restored = BenchmarkResult.from_dict(data)

    assert restored.benchmark_id == result.benchmark_id
    assert restored.overall_accuracy == result.overall_accuracy
    assert restored.passed == result.passed


@pytest.fixture
def benchmark_runner():
    """Fixture for RepoMapBenchmarkRunner with test codebase."""
    temp_dir = TemporaryDirectory()
    runner = RepoMapBenchmarkRunner()

    # Create a simple test codebase
    codebase_root = Path(temp_dir.name)
    (codebase_root / 'test1.py').write_text('def test_func(): pass\n')
    (codebase_root / 'test2.py').write_text('class TestClass: pass\n')
    (codebase_root / 'config.py').write_text('CONFIG = "value"\n')

    yield runner, codebase_root, temp_dir

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


def test_calculate_accuracy_perfect(benchmark_runner):
    """Test accuracy calculation for perfect match."""
    runner, codebase_root, _ = benchmark_runner
    expected = {'file1.py', 'file2.py'}
    actual = {'file1.py', 'file2.py'}
    accuracy = runner.calculate_accuracy(expected, actual)
    assert accuracy == 1.0


def test_calculate_accuracy_partial(benchmark_runner):
    """Test accuracy calculation for partial match."""
    runner, codebase_root, _ = benchmark_runner
    expected = {'file1.py', 'file2.py', 'file3.py'}
    actual = {'file1.py', 'file2.py'}
    accuracy = runner.calculate_accuracy(expected, actual)
    assert accuracy < 1.0
    assert accuracy > 0.0


def test_calculate_accuracy_no_match(benchmark_runner):
    """Test accuracy calculation for no match."""
    runner, codebase_root, _ = benchmark_runner
    expected = {'file1.py', 'file2.py'}
    actual = {'file3.py', 'file4.py'}
    accuracy = runner.calculate_accuracy(expected, actual)
    assert accuracy == 0.0


def test_calculate_accuracy_empty(benchmark_runner):
    """Test accuracy calculation for empty sets."""
    runner, codebase_root, _ = benchmark_runner
    accuracy = runner.calculate_accuracy(set(), set())
    assert accuracy == 1.0


def test_run_benchmark(benchmark_runner):
    """Test running a benchmark."""
    runner, codebase_root, _ = benchmark_runner
    benchmark = RepoMapBenchmark(
        benchmark_id='benchmark-001',
        name='Test Benchmark',
        codebase_path='.',
        query='test',
        expected_files={'test1.py'},
    )

    result = runner.run_benchmark(benchmark, codebase_root)

    assert result.benchmark_id == benchmark.benchmark_id
    assert result.duration_seconds > 0
    assert 'file_count' in result.performance_metrics


def test_run_benchmark_with_time_limit(benchmark_runner):
    """Test running a benchmark with time limit."""
    runner, codebase_root, _ = benchmark_runner
    benchmark = RepoMapBenchmark(
        benchmark_id='benchmark-001',
        name='Test Benchmark',
        codebase_path='.',
        query='test',
        max_duration_seconds=1.0,
    )

    result = runner.run_benchmark(benchmark, codebase_root)

    assert 'within_time_limit' in result.performance_metrics


def test_extract_functions(benchmark_runner):
    """Test extracting functions from files."""
    runner, codebase_root, _ = benchmark_runner
    file_paths = {'test1.py'}
    functions = runner._extract_functions(codebase_root, file_paths)

    assert 'test_func' in functions


def test_extract_classes(benchmark_runner):
    """Test extracting classes from files."""
    runner, codebase_root, _ = benchmark_runner
    file_paths = {'test2.py'}
    classes = runner._extract_classes(codebase_root, file_paths)

    assert 'TestClass' in classes


def test_create_default_benchmarks(benchmark_runner):
    """Test creating default benchmarks."""
    runner, codebase_root, _ = benchmark_runner
    benchmarks = runner.create_default_benchmarks()

    assert len(benchmarks) >= 3
    assert all(isinstance(b, RepoMapBenchmark) for b in benchmarks)


def test_convert_to_eval_test(benchmark_runner):
    """Test converting benchmark to eval test."""
    runner, codebase_root, _ = benchmark_runner
    benchmark = RepoMapBenchmark(
        benchmark_id='benchmark-001',
        name='Test Benchmark',
        codebase_path='.',
        query='test query',
    )

    eval_test = runner.convert_to_eval_test(benchmark)

    assert eval_test.test_id == benchmark.benchmark_id
    assert eval_test.name == benchmark.name
    assert 'query' in eval_test.metadata
    assert 'codebase_path' in eval_test.metadata
