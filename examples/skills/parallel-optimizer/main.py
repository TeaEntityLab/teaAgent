"""Parallel Experiment Optimizer - Reference Implementation.

This skill demonstrates TeaAgent's parallel experiment capabilities
for algorithm optimization using isolated Git branches.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List


class QualityMatrix:
    """Evaluates experiment results using multiple metrics."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def evaluate(self, branch_name: str) -> Dict[str, Any]:
        """Evaluate an experiment branch using quality metrics.

        Args:
            branch_name: Name of the Git branch to evaluate.

        Returns:
            Dictionary containing quality metrics.
        """
        results = {
            'branch': branch_name,
            'compilation_success': False,
            'test_pass_rate': 0.0,
            'performance_ms': 0.0,
            'lint_errors': 0,
        }

        # Check compilation
        try:
            result = subprocess.run(
                ['python', '-m', 'compileall', '-q', str(self.project_root)],
                cwd=self.project_root,
                capture_output=True,
                timeout=30,
            )
            results['compilation_success'] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            results['compilation_success'] = False

        # Run tests if compilation succeeded
        if results['compilation_success']:
            try:
                result = subprocess.run(
                    ['python', '-m', 'pytest', '--tb=no', '-q'],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                # Parse pytest output for pass rate
                if result.stdout:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'passed' in line:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part.isdigit() and i > 0:
                                    passed = int(part)
                                    total = (
                                        int(parts[i - 2])
                                        if i >= 2 and parts[i - 2].isdigit()
                                        else passed
                                    )
                                    results['test_pass_rate'] = (
                                        (passed / total * 100) if total > 0 else 0.0
                                    )
                                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                results['test_pass_rate'] = 0.0

        # Measure performance (example: run a benchmark if it exists)
        benchmark_file = self.project_root / 'benchmark.py'
        if benchmark_file.exists():
            try:
                start = time.time()
                result = subprocess.run(
                    ['python', str(benchmark_file)],
                    cwd=self.project_root,
                    capture_output=True,
                    timeout=30,
                )
                results['performance_ms'] = (time.time() - start) * 1000
            except (subprocess.TimeoutExpired, FileNotFoundError):
                results['performance_ms'] = float('inf')

        return results

    def compare(self, results: List[Dict[str, Any]]) -> str:
        """Select the best experiment based on quality metrics.

        Args:
            results: List of quality matrix results for each experiment.

        Returns:
            Name of the best branch.
        """
        # Score each result (higher is better)
        scored = []
        for result in results:
            score = 0
            if result['compilation_success']:
                score += 100
            score += result['test_pass_rate']
            # Lower performance is better, so invert
            if result['performance_ms'] > 0 and result['performance_ms'] != float(
                'inf'
            ):
                score += 10000 / result['performance_ms']
            score -= result['lint_errors'] * 5
            scored.append((score, result['branch']))

        # Return highest scoring branch
        scored.sort(reverse=True)
        return scored[0][1] if scored else results[0]['branch']


def run_parallel_optimization(
    project_root: Path,
    strategies: List[str],
    task_description: str,
) -> Dict[str, Any]:
    """Run parallel optimization experiments.

    Args:
        project_root: Path to the project repository.
        strategies: List of strategy names to test.
        task_description: Description of the optimization task.

    Returns:
        Dictionary containing optimization results.
    """
    from teaagent.git_sandbox import ParallelExperimentStack

    print(f'[Parallel Optimizer] Starting optimization for: {task_description}')
    print(
        f'[Parallel Optimizer] Testing {len(strategies)} strategies: {", ".join(strategies)}'
    )

    # Create parallel experiment stack
    run_id = f'opt-{int(time.time())}'
    stack = ParallelExperimentStack(
        root=project_root,
        run_id=run_id,
        options=strategies,
    )

    # Start all experiments
    print('[Parallel Optimizer] Creating experiment branches...')
    results = stack.start_all()

    if not results:
        return {'success': False, 'error': 'Failed to create experiment branches'}

    print(f'[Parallel Optimizer] Created {len(results)} experiment branches')

    # Evaluate each experiment
    quality = QualityMatrix(project_root)
    quality_results = []

    for branch_name in results:
        print(f'[Parallel Optimizer] Evaluating {branch_name}...')
        # Checkout the branch
        subprocess.run(
            ['git', 'checkout', branch_name], cwd=project_root, capture_output=True
        )

        # Evaluate
        result = quality.evaluate(branch_name)
        quality_results.append(result)

        print(
            f'[Parallel Optimizer] {branch_name}: '
            f'compile={result["compilation_success"]}, '
            f'tests={result["test_pass_rate"]:.1f}%, '
            f'perf={result["performance_ms"]:.1f}ms'
        )

    # Select best result
    best_branch = quality.compare(quality_results)
    print(f'[Parallel Optimizer] Best strategy: {best_branch}')

    # Select the best branch
    selection_result = stack.select(best_branch)

    # Cleanup failed branches
    print('[Parallel Optimizer] Cleaning up failed branches...')
    stack.cleanup_all()

    return {
        'success': True,
        'best_branch': best_branch,
        'quality_results': quality_results,
        'selection_result': selection_result,
    }


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print(
            'Usage: python main.py <project_root> <strategy1,strategy2,...> <task_description>'
        )
        sys.exit(1)

    project_root = Path(sys.argv[1])
    strategies = sys.argv[2].split(',')
    task_description = ' '.join(sys.argv[3:])

    result = run_parallel_optimization(project_root, strategies, task_description)
    print(json.dumps(result, indent=2))
