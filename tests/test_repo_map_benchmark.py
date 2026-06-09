"""Tests for repo-map benchmark automation (TASK-H5-001-03)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.repo_map_benchmark import (
    BenchmarkResult,
    RepoMapBenchmark,
    RepoMapBenchmarkRunner,
)


class TestRepoMapBenchmark(unittest.TestCase):
    """Test repo-map benchmark management."""

    def test_to_dict_and_from_dict(self):
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

        self.assertEqual(restored.benchmark_id, benchmark.benchmark_id)
        self.assertEqual(restored.name, benchmark.name)
        self.assertEqual(restored.expected_files, benchmark.expected_files)


class TestBenchmarkResult(unittest.TestCase):
    """Test benchmark result management."""

    def test_to_dict_and_from_dict(self):
        """Test result serialization."""
        result = BenchmarkResult(
            benchmark_id='benchmark-001',
            actual_files={'file1.py', 'file2.py'},
            overall_accuracy=0.85,
            passed=True,
        )

        data = result.to_dict()
        restored = BenchmarkResult.from_dict(data)

        self.assertEqual(restored.benchmark_id, result.benchmark_id)
        self.assertEqual(restored.overall_accuracy, result.overall_accuracy)
        self.assertEqual(restored.passed, result.passed)


class TestRepoMapBenchmarkRunner(unittest.TestCase):
    """Test repo-map benchmark runner."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = RepoMapBenchmarkRunner()
        self.temp_dir = TemporaryDirectory()

        # Create a simple test codebase
        self.codebase_root = Path(self.temp_dir.name)
        (self.codebase_root / 'test1.py').write_text('def test_func(): pass\n')
        (self.codebase_root / 'test2.py').write_text('class TestClass: pass\n')
        (self.codebase_root / 'config.py').write_text('CONFIG = "value"\n')

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_calculate_accuracy_perfect(self):
        """Test accuracy calculation for perfect match."""
        expected = {'file1.py', 'file2.py'}
        actual = {'file1.py', 'file2.py'}
        accuracy = self.runner.calculate_accuracy(expected, actual)
        self.assertEqual(accuracy, 1.0)

    def test_calculate_accuracy_partial(self):
        """Test accuracy calculation for partial match."""
        expected = {'file1.py', 'file2.py', 'file3.py'}
        actual = {'file1.py', 'file2.py'}
        accuracy = self.runner.calculate_accuracy(expected, actual)
        self.assertLess(accuracy, 1.0)
        self.assertGreater(accuracy, 0.0)

    def test_calculate_accuracy_no_match(self):
        """Test accuracy calculation for no match."""
        expected = {'file1.py', 'file2.py'}
        actual = {'file3.py', 'file4.py'}
        accuracy = self.runner.calculate_accuracy(expected, actual)
        self.assertEqual(accuracy, 0.0)

    def test_calculate_accuracy_empty(self):
        """Test accuracy calculation for empty sets."""
        accuracy = self.runner.calculate_accuracy(set(), set())
        self.assertEqual(accuracy, 1.0)

    def test_run_benchmark(self):
        """Test running a benchmark."""
        benchmark = RepoMapBenchmark(
            benchmark_id='benchmark-001',
            name='Test Benchmark',
            codebase_path='.',
            query='test',
            expected_files={'test1.py'},
        )

        result = self.runner.run_benchmark(benchmark, self.codebase_root)

        self.assertEqual(result.benchmark_id, benchmark.benchmark_id)
        self.assertGreater(result.duration_seconds, 0)
        self.assertIn('file_count', result.performance_metrics)

    def test_run_benchmark_with_time_limit(self):
        """Test running a benchmark with time limit."""
        benchmark = RepoMapBenchmark(
            benchmark_id='benchmark-001',
            name='Test Benchmark',
            codebase_path='.',
            query='test',
            max_duration_seconds=1.0,
        )

        result = self.runner.run_benchmark(benchmark, self.codebase_root)

        self.assertIn('within_time_limit', result.performance_metrics)

    def test_extract_functions(self):
        """Test extracting functions from files."""
        file_paths = {'test1.py'}
        functions = self.runner._extract_functions(self.codebase_root, file_paths)

        self.assertIn('test_func', functions)

    def test_extract_classes(self):
        """Test extracting classes from files."""
        file_paths = {'test2.py'}
        classes = self.runner._extract_classes(self.codebase_root, file_paths)

        self.assertIn('TestClass', classes)

    def test_create_default_benchmarks(self):
        """Test creating default benchmarks."""
        benchmarks = self.runner.create_default_benchmarks()

        self.assertGreaterEqual(len(benchmarks), 3)
        self.assertTrue(all(isinstance(b, RepoMapBenchmark) for b in benchmarks))

    def test_convert_to_eval_test(self):
        """Test converting benchmark to eval test."""
        benchmark = RepoMapBenchmark(
            benchmark_id='benchmark-001',
            name='Test Benchmark',
            codebase_path='.',
            query='test query',
        )

        eval_test = self.runner.convert_to_eval_test(benchmark)

        self.assertEqual(eval_test.test_id, benchmark.benchmark_id)
        self.assertEqual(eval_test.name, benchmark.name)
        self.assertIn('query', eval_test.metadata)
        self.assertIn('codebase_path', eval_test.metadata)


if __name__ == '__main__':
    unittest.main()
