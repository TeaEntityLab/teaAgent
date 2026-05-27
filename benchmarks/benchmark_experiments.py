"""Benchmark parallel experiments performance."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from teaagent.git_sandbox import ParallelExperimentStack


def benchmark_parallel_experiment_creation(count: int = 10) -> dict[str, float]:
    """Benchmark creating multiple parallel experiments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a base git repository
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create initial commit
        (tmp_path / "test.txt").write_text("initial content", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)
        
        # Benchmark experiment creation
        options = [f"opt{i}" for i in range(count)]
        stack = ParallelExperimentStack(root=tmp_path, run_id="benchmark-exp", options=options)
        
        start = time.perf_counter()
        results = stack.start_all(auto_stash=False)
        creation_time = time.perf_counter() - start
        
        # Benchmark cleanup
        start = time.perf_counter()
        stack.cleanup_all()
        cleanup_time = time.perf_counter() - start
        
        return {
            "experiment_count": count,
            "creation_time": creation_time,
            "cleanup_time": cleanup_time,
            "avg_creation_time": creation_time / count,
            "avg_cleanup_time": cleanup_time / count,
        }


def benchmark_experiment_isolation(count: int = 5) -> dict[str, float]:
    """Benchmark isolation operations across experiments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create a base git repository
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create initial commit
        (tmp_path / "test.txt").write_text("initial content", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)
        
        # Create experiments
        options = [f"opt{i}" for i in range(count)]
        stack = ParallelExperimentStack(root=tmp_path, run_id="benchmark-exp", options=options)
        results = stack.start_all(auto_stash=False)
        
        # Benchmark checkout operations
        checkout_times = []
        for opt in options:
            start = time.perf_counter()
            subprocess.run(["git", "checkout", results[opt].branch_name], cwd=tmp_path, check=True, capture_output=True)
            checkout_time = time.perf_counter() - start
            checkout_times.append(checkout_time)
        
        # Cleanup
        stack.cleanup_all()
        
        return {
            "experiment_count": count,
            "avg_checkout_time": sum(checkout_times) / len(checkout_times),
            "min_checkout_time": min(checkout_times),
            "max_checkout_time": max(checkout_times),
        }


def print_benchmark_results() -> None:
    """Print benchmark results."""
    print("=" * 80)
    print("Parallel Experiments Performance Benchmark")
    print("=" * 80)
    
    counts = [5, 10, 20, 50]
    
    print("\nExperiment Creation & Cleanup:")
    print(f"{'Count':<10} {'Creation (s)':<15} {'Cleanup (s)':<15} {'Avg Create (s)':<15} {'Avg Cleanup (s)':<15}")
    print("-" * 80)
    
    for count in counts:
        results = benchmark_parallel_experiment_creation(count)
        print(
            f"{count:<10} "
            f"{results['creation_time']:<15.4f} "
            f"{results['cleanup_time']:<15.4f} "
            f"{results['avg_creation_time']:<15.4f} "
            f"{results['avg_cleanup_time']:<15.4f}"
        )
    
    print("\n" + "=" * 80)
    print("Experiment Isolation (Checkout Performance)")
    print("=" * 80)
    
    isolation_results = benchmark_experiment_isolation(10)
    print(f"\nExperiment count: {isolation_results['experiment_count']}")
    print(f"Average checkout time: {isolation_results['avg_checkout_time']:.4f}s")
    print(f"Min checkout time: {isolation_results['min_checkout_time']:.4f}s")
    print(f"Max checkout time: {isolation_results['max_checkout_time']:.4f}s")


if __name__ == "__main__":
    print_benchmark_results()
