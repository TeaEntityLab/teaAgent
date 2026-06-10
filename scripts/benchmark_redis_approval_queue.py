#!/usr/bin/env python3
"""Performance benchmark for Redis-based approval queue.

This script benchmarks a Redis-based approval queue implementation
to compare performance with the file-based baseline.

Usage:
    python scripts/benchmark_redis_approval_queue.py --concurrency 10 --requests 100
    python scripts/benchmark_redis_approval_queue.py --all
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import redis
except ImportError:
    print('Redis library not installed. Install with: pip install redis')
    exit(1)


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


class RedisApprovalQueueBenchmark:
    """Benchmark harness for Redis-based approval queue performance."""

    def __init__(self, redis_client: redis.Redis, queue_key: str = 'approval_queue'):
        self.redis = redis_client
        self.queue_key = queue_key
        self.request_key_prefix = f'{queue_key}:request:'
        self.pending_set_key = f'{queue_key}:pending'

    def cleanup(self):
        """Clean up Redis keys."""
        self.redis.delete(self.queue_key)
        self.redis.delete(self.pending_set_key)
        # Delete all request keys
        for key in self.redis.scan_iter(f'{self.request_key_prefix}*'):
            self.redis.delete(key)

    def submit_request(self, request_data: dict) -> str:
        """Submit an approval request to Redis."""
        request_id = request_data['request_id']
        request_key = f'{self.request_key_prefix}{request_id}'

        # Store request data as hash
        self.redis.hset(request_key, mapping=request_data)

        # Add to pending set
        self.redis.sadd(self.pending_set_key, request_id)

        # Add to queue for processing
        self.redis.rpush(self.queue_key, request_id)

        return request_id

    def approve_request(self, request_id: str) -> bool:
        """Approve a pending request."""
        request_key = f'{self.request_key_prefix}{request_id}'

        # Check if request exists and is pending
        if not self.redis.sismember(self.pending_set_key, request_id):
            return False

        # Update request status
        self.redis.hset(request_key, 'status', 'approved')
        self.redis.hset(
            request_key, 'approved_at', datetime.now(timezone.utc).isoformat()
        )

        # Remove from pending set
        self.redis.srem(self.pending_set_key, request_id)

        return True

    def approve_all_pending(self) -> int:
        """Approve all pending requests."""
        approved = 0
        for request_id in self.redis.smembers(self.pending_set_key):
            if self.approve_request(request_id):
                approved += 1
        return approved

    def get_pending_requests(self) -> list[dict]:
        """Get all pending requests."""
        pending = []
        for request_id in self.redis.smembers(self.pending_set_key):
            request_key = f'{self.request_key_prefix}{request_id}'
            request_data = self.redis.hgetall(request_key)
            if request_data:
                # Convert bytes to strings
                request_data = {
                    k.decode() if isinstance(k, bytes) else k: v.decode()
                    if isinstance(v, bytes)
                    else v
                    for k, v in request_data.items()
                }
                pending.append(request_data)
        return pending

    def benchmark_submit_approve(
        self, concurrency: int, total_requests: int
    ) -> BenchmarkResult:
        """Benchmark submit and approve operations."""
        latencies = []
        errors = 0

        def submit_and_approve(request_id: int) -> float:
            try:
                start = time.perf_counter()

                # Submit request
                request_data = {
                    'request_id': f'req-{request_id}',
                    'subagent_id': f'subagent-{request_id % concurrency}',
                    'parent_run_id': 'benchmark-parent',
                    'subagent_name': f'benchmark-subagent-{request_id % concurrency}',
                    'tool_name': 'write_file',
                    'tool_arguments': json.dumps(
                        {'path': f'/tmp/test_{request_id}.txt', 'content': 'test'}
                    ),
                    'permission_mode': 'workspace-write',
                    'isolation': 'shared',
                    'status': 'pending',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }

                self.submit_request(request_data)

                # Approve after small delay
                time.sleep(0.001)  # 1ms delay
                self.approve_request(f'req-{request_id}')

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
            operation='submit_approve',
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

        # First, submit all requests
        for i in range(total_requests):
            request_data = {
                'request_id': f'req-{i}',
                'subagent_id': f'subagent-{i % concurrency}',
                'parent_run_id': 'benchmark-parent',
                'subagent_name': f'benchmark-subagent-{i % concurrency}',
                'tool_name': 'write_file',
                'tool_arguments': json.dumps(
                    {'path': f'/tmp/test_{i}.txt', 'content': 'test'}
                ),
                'permission_mode': 'workspace-write',
                'isolation': 'shared',
                'status': 'pending',
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            self.submit_request(request_data)

        # Benchmark batch approval
        def approve_batch(batch_id: int) -> float:
            try:
                start = time.perf_counter()

                # Approve subset of requests
                start_idx = batch_id * (total_requests // concurrency)
                end_idx = start_idx + (total_requests // concurrency)
                for i in range(start_idx, min(end_idx, total_requests)):
                    self.approve_request(f'req-{i}')

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
            request_data = {
                'request_id': f'req-{i}',
                'subagent_id': f'subagent-{i % concurrency}',
                'parent_run_id': 'benchmark-parent',
                'subagent_name': f'benchmark-subagent-{i % concurrency}',
                'tool_name': 'write_file',
                'tool_arguments': json.dumps(
                    {'path': f'/tmp/test_{i}.txt', 'content': 'test'}
                ),
                'permission_mode': 'workspace-write',
                'isolation': 'shared',
                'status': 'pending',
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            self.submit_request(request_data)

        def get_pending(iteration: int) -> float:
            try:
                start = time.perf_counter()
                self.get_pending_requests()
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
    output_file: str,
    redis_host: str = 'localhost',
    redis_port: int = 6379,
) -> BenchmarkSuite:
    """Run complete benchmark suite."""
    suite = BenchmarkSuite()
    suite.metadata = {
        'concurrency_levels': concurrency_levels,
        'request_counts': request_counts,
        'redis_host': redis_host,
        'redis_port': redis_port,
    }

    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True
        )
        redis_client.ping()
        print(f'Connected to Redis at {redis_host}:{redis_port}')
    except Exception as e:
        print(f'Failed to connect to Redis: {e}')
        print('Make sure Redis is running: redis-server')
        return suite

    for concurrency in concurrency_levels:
        for total_requests in request_counts:
            print(
                f'\nBenchmarking: concurrency={concurrency}, requests={total_requests}'
            )

            benchmark = RedisApprovalQueueBenchmark(redis_client)

            # Benchmark submit_approve
            print('  - submit_approve...')
            benchmark.cleanup()
            result = benchmark.benchmark_submit_approve(concurrency, total_requests)
            suite.results.append(result)
            print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
            print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
            print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
            print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

            # Benchmark batch_approve
            print('  - batch_approve...')
            benchmark.cleanup()
            result = benchmark.benchmark_batch_approve(concurrency, total_requests)
            suite.results.append(result)
            print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
            print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
            print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
            print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

            # Benchmark get_pending_requests
            print('  - get_pending_requests...')
            benchmark.cleanup()
            result = benchmark.benchmark_get_pending(concurrency, total_requests)
            suite.results.append(result)
            print(f'    Throughput: {result.throughput_ops_per_sec:.2f} ops/sec')
            print(f'    Latency p50: {result.latency_p50_ms:.2f}ms')
            print(f'    Latency p95: {result.latency_p95_ms:.2f}ms')
            print(f'    Latency p99: {result.latency_p99_ms:.2f}ms')

    # Final cleanup
    benchmark.cleanup()

    # Save results
    suite_dict = suite.__dict__.copy()
    suite_dict['results'] = [r.__dict__ for r in suite.results]
    with open(output_file, 'w') as f:
        json.dump(suite_dict, f, indent=2)
    print(f'\nResults saved to {output_file}')

    return suite


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark Redis-based approval queue performance'
    )
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
        type=str,
        default='redis_approval_queue_benchmark_results.json',
        help='Output file for benchmark results (default: redis_approval_queue_benchmark_results.json)',
    )
    parser.add_argument(
        '--redis-host',
        type=str,
        default='localhost',
        help='Redis host (default: localhost)',
    )
    parser.add_argument(
        '--redis-port',
        type=int,
        default=6379,
        help='Redis port (default: 6379)',
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

    print('Starting Redis approval queue benchmark...')
    print(f'Concurrency levels: {args.concurrency}')
    print(f'Request counts: {args.requests}')
    print(f'Redis: {args.redis_host}:{args.redis_port}')
    print(f'Output file: {args.output}')

    suite = run_benchmark_suite(
        args.concurrency, args.requests, args.output, args.redis_host, args.redis_port
    )

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
