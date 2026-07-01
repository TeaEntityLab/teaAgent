"""Repo-map benchmark execution helper for the eval suite.

Extracted from ``eval_suite.py`` to keep the runner under the 800-line
god-module threshold. Encapsulates deterministic repo-map benchmark
execution and status determination.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from teaagent.eval_suite import EvalCategory, EvalStatus, EvalTest


class RepoMapBenchmarkExecutor:
    """Execute deterministic repo-map benchmark eval tests."""

    @staticmethod
    def execution_metadata(test: EvalTest) -> dict[str, Any]:
        """Metadata for deterministic repo-map benchmark execution."""
        return {
            'execution_mode': 'fixture',
            'executor': 'repo_map_benchmark',
            'advisory_only': False,
            'category': test.category.value,
        }

    @staticmethod
    def execute(test: EvalTest, fixture_data: Optional[dict[str, Any]]) -> str:
        """Execute a deterministic repo-map benchmark test.

        Returns serialized JSON payload describing the benchmark result.
        """
        metadata = dict(test.metadata)
        expected_files = set(metadata.get('expected_files', []))
        expected_functions = set(metadata.get('expected_functions', []))
        expected_classes = set(metadata.get('expected_classes', []))
        seeded_failure = os.environ.get('TEAAGENT_EVAL_SEED_REPO_MAP_FAILURE') == '1'
        if seeded_failure:
            expected_files = {'__seeded_missing_repo_map_target__.py'}
            expected_functions = set()
            expected_classes = set()

        from teaagent.governance.repo_map_benchmark import (
            RepoMapBenchmark,
            RepoMapBenchmarkRunner,
        )

        benchmark = RepoMapBenchmark(
            benchmark_id=test.test_id,
            name=test.name,
            codebase_path=str(metadata.get('codebase_path', '.')),
            query=str(metadata.get('query', '')),
            expected_files=expected_files,
            expected_functions=expected_functions,
            expected_classes=expected_classes,
            max_duration_seconds=float(metadata.get('max_duration_seconds', 30.0)),
            metadata={
                key: value
                for key, value in metadata.items()
                if key
                not in {
                    'codebase_path',
                    'query',
                    'expected_files',
                    'expected_functions',
                    'expected_classes',
                    'max_duration_seconds',
                }
            },
        )
        result = RepoMapBenchmarkRunner().run_benchmark(
            benchmark,
            Path(benchmark.codebase_path),
        )
        payload = result.to_dict()
        payload['seeded_failure'] = seeded_failure
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def determine_status(output: str) -> EvalStatus:
        """Determine repo-map benchmark status from serialized benchmark output."""
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return EvalStatus.ERROR
        return EvalStatus.PASSED if payload.get('passed') is True else EvalStatus.FAILED


def is_repo_map_benchmark(test: EvalTest) -> bool:
    """Whether ``test`` is a repo-map benchmark category."""
    return test.category == EvalCategory.REPO_MAP_BENCHMARK
