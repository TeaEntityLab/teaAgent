#!/usr/bin/env python3
"""Performance benchmark for file-based approval queue.

This script benchmarks the current file-based approval queue implementation
to establish baseline metrics for throughput and latency under various load conditions.

Usage:
    python scripts/benchmark_approval_queue.py --concurrency 10 --requests 100
    python scripts/benchmark_approval_queue.py --all
"""

import argparse
import json

# Add project root to path
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from teaagent.subagents._approval_queue import (
    CentralizedApprovalQueue,
    SubagentApprovalRequest,
)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    operation: str
    concurrency: int
    total_requests: int
    duration_seconds: float
    throughput_ops_per_sec: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_min_ms: float
    latency_max_ms: float
    errors: int = 0


@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    results: list[BenchmarkResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalQueueBenchmark:
    """Benchmark harness for approval queue performance."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.parent_run_id = f'benchmark-{uuid4().hex}'
        self.queue = CentralizedApprovalQueue(
            self.parent_run_id,
            workspace_root=workspace_root,
        )

    def benchmark_submit_sync(
        self, concurrency: int, total_requests: int
    ) -> BenchmarkResult:
        """Benchmark submit_request_sync with immediate approval."""
        latencies = []
        errors = 0

        def submit_and_approve(request_id: int) -> float:
            try:
                start = time.perf_counter()

                # Submit request (will block until approved)
                def submit():
                    return self.queue.submit_request_sync(
                        subagent_id=f'subagent-{request_id % concurrency}',
                        subagent_name=f'benchmark-subagent-{request_id % concurrency}',
                        tool_name='write_file',
                        tool_arguments={
                            'path': f'/tmp/test_{request_id}.txt',
                            'content': 'test',
                        },
                        permission_mode='workspace-write',
                        isolation='shared',
                    )

                # Submit in thread
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    future = executor.submit(submit)

                    # Approve after small delay to simulate real workflow
                    time.sleep(0.001)  # 1ms delay
                    self.queue.approve_all_pending_sync(approved_by='benchmark')

                    future.result(timeout=10)

                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
                return latency_ms
            except Exception as e:
                print(f'Error in request {request_id}: {e}')
                nonlocal errors
                errors += 1
                return 0.0

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(submit_and_approve, i) for i in range(total_requests)
            ]
            for future in as_completed(futures):
                future.result()

        end_time = time.perf_counter()
        duration = end_time - start_time

        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
        else:
            p50 = p95 = p99 = 0.0

        return BenchmarkResult(
            operation='submit_request_sync',
            concurrency=concurrency,
            total_requests=total_requests,
            duration_seconds=duration,
            throughput_ops_per_sec=total_requests / duration if duration > 0 else 0,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            latency_min_ms=min(latencies) if latencies else 0.0,
            latency_max_ms=max(latencies) if latencies else 0.0,
            errors=errors,
        )

    def benchmark_batch_approve(
        self, concurrency: int, total_requests: int
    ) -> BenchmarkResult:
        """Benchmark batch approval operations."""
        latencies = []
        errors = 0

        # First, submit all requests without approval
        for i in range(total_requests):
            try:
                # Create request directly in queue (bypass submit to avoid blocking)
                request = SubagentApprovalRequest(
                    request_id=f'req-{i}',
                    subagent_id=f'subagent-{i % concurrency}',
                    parent_run_id=self.parent_run_id,
                    subagent_name=f'benchmark-subagent-{i % concurrency}',
                    tool_name='write_file',
                    tool_arguments={'path': f'/tmp/test_{i}.txt', 'content': 'test'},
                    permission_mode='workspace-write',
                    isolation='shared',
                )
                with self.queue._sync_lock:
                    self.queue._requests[request.request_id] = request
            except Exception as e:
                print(f'Error creating request {i}: {e}')
                errors += 1

        # Now benchmark batch approval
        def approve_batch(batch_id: int) -> float:
            try:
                start = time.perf_counter()

                # Create batch from subset of requests
                start_idx = batch_id * (total_requests // concurrency)
                end_idx = start_idx + (total_requests // concurrency)
                request_ids = [
                    f'req-{i}' for i in range(start_idx, min(end_idx, total_requests))
                ]

                if request_ids:
                    self.queue.create_batch(request_ids)
                    self.queue.approve_all_pending_sync(approved_by='benchmark')

                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
                return latency_ms
            except Exception as e:
                print(f'Error in batch {batch_id}: {e}')
                nonlocal errors
                errors += 1
                return 0.0

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(approve_batch, i) for i in range(concurrency)]
            for future in as_completed(futures):
                future.result()

        end_time = time.perf_counter()
        duration = end_time - start_time

        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
        else:
            p50 = p95 = p99 = 0.0

        return BenchmarkResult(
            operation='batch_approve',
            concurrency=concurrency,
            total_requests=total_requests,
            duration_seconds=duration,
            throughput_ops_per_sec=total_requests / duration if duration > 0 else 0,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            latency_min_ms=min(latencies) if latencies else 0.0,
            latency_max_ms=max(latencies) if latencies else 0.0,
            errors=errors,
        )

    def benchmark_get_pending(
        self, concurrency: int, total_requests: int
    ) -> BenchmarkResult:
        """Benchmark get_pending_requests operation."""
        latencies = []
        errors = 0

        # Create pending requests
        for i in range(total_requests):
            request = SubagentApprovalRequest(
                request_id=f'req-{i}',
                subagent_id=f'subagent-{i % concurrency}',
                parent_run_id=self.parent_run_id,
                subagent_name=f'benchmark-subagent-{i % concurrency}',
                tool_name='write_file',
                tool_arguments={'path': f'/tmp/test_{i}.txt', 'content': 'test'},
                permission_mode='workspace-write',
                isolation='shared',
            )
            with self.queue._sync_lock:
                self.queue._requests[request.request_id] = request

        def get_pending(iteration: int) -> float:
            try:
                start = time.perf_counter()
                self.queue.get_pending_requests()
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
                return latency_ms
            except Exception as e:
                print(f'Error in get_pending iteration {iteration}: {e}')
                nonlocal errors
                errors += 1
                return 0.0

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(get_pending, i) for i in range(total_requests)]
            for future in as_completed(futures):
                future.result()

        end_time = time.perf_counter()
        duration = end_time - start_time

        if latencies:
            latencies_sorted = sorted(latencies)
            p50 = latencies_sorted[len(latencies_sorted) // 2]
            p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
            p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
        else:
            p50 = p95 = p99 = 0.0

        return BenchmarkResult(
            operation='get_pending_requests',
            concurrency=concurrency,
            total_requests=total_requests,
            duration_seconds=duration,
            throughput_ops_per_sec=total_requests / duration if duration > 0 else 0,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            latency_min_ms=min(latencies) if latencies else 0.0,
            latency_max_ms=max(latencies) if latencies else 0.0,
            errors=errors,
        )


def run_benchmark_suite(
    concurrency_levels: list[int],
    request_counts: list[int],
    output_file: Path,
) -> BenchmarkSuite:
    """Run complete benchmark suite."""
    suite = BenchmarkSuite()
    suite.metadata = {
        'concurrency_levels': concurrency_levels,
        'request_counts': request_counts,
        'workspace_root': str(tempfile.gettempdir()),
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_root = Path(tmpdir)

        for concurrency in concurrency_levels:
            for total_requests in request_counts:
                print(
                    f'\nBenchmarking: concurrency={concurrency}, requests={total_requests}'
                )

                benchmark = ApprovalQueueBenchmark(workspace_root)

                # Benchmark submit_request_sync
                print('  - submit_request_sync...')
                result = benchmark.benchmark_submit_sync(concurrency, total_requests)
                suite.results.append(result)
                print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
                print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
                print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
                print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

                # Reset queue for next benchmark
                benchmark = ApprovalQueueBenchmark(workspace_root)

                # Benchmark batch_approve
                print('  - batch_approve...')
                result = benchmark.benchmark_batch_approve(concurrency, total_requests)
                suite.results.append(result)
                print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
                print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
                print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
                print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

                # Reset queue for next benchmark
                benchmark = ApprovalQueueBenchmark(workspace_root)

                # Benchmark get_pending_requests
                print('  - get_pending_requests...')
                result = benchmark.benchmark_get_pending(concurrency, total_requests)
                suite.results.append(result)
                print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
                print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
                print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
                print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

    # Save results
    output_file.write_text(json.dumps(suite, default=lambda o: o.__dict__, indent=2))
    print(f'\nResults saved to {output_file}')

    return suite


def main():
    parser = argparse.ArgumentParser(description='Benchmark approval queue performance')
    parser.add_argument(
        '--concurrency',
        type=int,
        nargs='+',
        default=[1, 10, 50, 100],
        help='Concurrency levels to test (default: 1 10 50 100)',
    )
    parser.add_argument(
        '--requests',
        type=int,
        nargs='+',
        default=[100, 500, 1000],
        help='Request counts to test (default: 100 500 1000)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('approval_queue_benchmark_results.json'),
        help='Output file for benchmark results (default: approval_queue_benchmark_results.json)',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run comprehensive benchmark with all combinations',
    )

    args = parser.parse_args()

    if args.all:
        args.concurrency = [1, 5, 10, 25, 50, 100]
        args.requests = [50, 100, 250, 500, 1000, 2500]

    print('Starting approval queue benchmark...')
    print(f'Concurrency levels: {args.concurrency}')
    print(f'Request counts: {args.requests}')
    print(f'Output file: {args.output}')

    suite = run_benchmark_suite(args.concurrency, args.requests, args.output)

    print('\n' + '=' * 60)
    print('Benchmark Summary')
    print('=' * 60)

    # Group results by operation
    by_operation = {}
    for result in suite.results:
        if result.operation not in by_operation:
            by_operation[result.operation] = []
        by_operation[result.operation].append(result)

    for operation, results in by_operation.items():
        print(f'\n{operation}:')
        for result in results:
            print(
                f'  {result.concurrency} concurrent, {result.total_requests} requests:'
            )
            print(
                f'    {result.throughput_ops_per_sec:.2f} ops/sec, '
                f'p50={result.latency_p50_ms:.2f}ms, '
                f'p95={result.latency_p95_ms:.2f}ms, '
                f'p99={result.latency_p99_ms:.2f}ms'
            )


if __name__ == '__main__':
    main()
