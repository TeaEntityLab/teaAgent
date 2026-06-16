"""Tests for TeamOrchestrator concurrent dispatch."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from teaagent.subagents._team_orchestrator import (
    TeamDef,
    TeamOrchestrator,
)
from teaagent.subagents._types import SubagentDef


def _make_spec(name: str) -> SubagentDef:
    return SubagentDef(name=name, description=f'Specialist {name}')


def _make_team(
    name: str = 'test-team',
    specialists: tuple[SubagentDef, ...] = (),
    max_concurrent: int = 3,
) -> TeamDef:
    return TeamDef(
        name=name,
        specialists=specialists,
        max_concurrent=max_concurrent,
    )


class TestTeamOrchestratorConcurrency:
    def _slow_run_subagent(self, **kwargs: object) -> dict[str, object]:
        time.sleep(0.1)
        idx = kwargs.get('batch_index', -1)
        return {'status': 'ok', 'batch_index': idx, 'output': f'result-{idx}'}

    def test_specialists_run_concurrently(self, tmp_path: Path):
        manager = MagicMock()
        manager.run_subagent = self._slow_run_subagent

        team = _make_team(
            specialists=(
                _make_spec('a'),
                _make_spec('b'),
                _make_spec('c'),
            ),
            max_concurrent=3,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        start = time.monotonic()
        result = orchestrator.run_team('do the thing', 'test-team')
        elapsed = time.monotonic() - start

        assert result['status'] == 'ok'
        assert result['specialist_count'] == 3
        assert elapsed < 0.25, (
            f'Expected concurrent execution (~0.1s), got {elapsed:.2f}s (sequential would be ~0.3s)'
        )

    def test_max_concurrent_respected(self, tmp_path: Path):
        manager = MagicMock()
        manager.run_subagent = self._slow_run_subagent

        team = _make_team(
            specialists=(
                _make_spec('a'),
                _make_spec('b'),
                _make_spec('c'),
            ),
            max_concurrent=1,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        start = time.monotonic()
        result = orchestrator.run_team('do the thing', 'test-team')
        elapsed = time.monotonic() - start

        assert result['status'] == 'ok'
        assert result['specialist_count'] == 3
        assert elapsed >= 0.25, (
            f'Expected sequential execution (>=0.3s), got {elapsed:.2f}s'
        )


class TestTeamOrchestratorOrdering:
    def test_results_preserve_batch_index_order(self, tmp_path: Path):
        delays = [0.15, 0.05, 0.10]

        def _staggered_run_subagent(**kwargs: object) -> dict[str, object]:
            idx = kwargs.get('batch_index', -1)
            time.sleep(delays[idx])
            return {'status': 'ok', 'batch_index': idx, 'output': f'result-{idx}'}

        manager = MagicMock()
        manager.run_subagent = _staggered_run_subagent

        team = _make_team(
            specialists=(
                _make_spec('slow'),
                _make_spec('fast'),
                _make_spec('mid'),
            ),
            max_concurrent=3,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        result = orchestrator.run_team('task', 'test-team')

        assert result['status'] == 'ok'
        assert result['specialist_count'] == 3
        output_parts = result['output'].split('\n\n---\n\n')
        batch_indices = [int(p.removeprefix('result-')) for p in output_parts]
        assert batch_indices == [0, 1, 2], (
            f'Expected ordered [0,1,2], got {batch_indices}'
        )


class TestTeamOrchestratorErrorHandling:
    def test_single_failure_does_not_block_others(self, tmp_path: Path):
        call_counts = {'count': 0}

        def _succeed_or_fail(**kwargs: object) -> dict[str, object]:
            idx = kwargs.get('batch_index', -1)
            call_counts['count'] += 1
            if idx == 0:
                raise RuntimeError('specialist-0 exploded')
            return {'status': 'ok', 'batch_index': idx, 'output': f'result-{idx}'}

        manager = MagicMock()
        manager.run_subagent = _succeed_or_fail

        team = _make_team(
            specialists=(
                _make_spec('a'),
                _make_spec('b'),
                _make_spec('c'),
            ),
            max_concurrent=3,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        result = orchestrator.run_team('task', 'test-team')

        assert result['status'] == 'ok'
        assert result['specialist_count'] == 3
        assert call_counts['count'] == 3, 'All 3 specialists should have been called'

    def test_all_failures_still_return_ordered(self, tmp_path: Path):
        def _always_fail(**kwargs: object) -> dict[str, object]:
            idx = kwargs.get('batch_index', -1)
            raise RuntimeError(f'specialist-{idx} exploded')

        manager = MagicMock()
        manager.run_subagent = _always_fail

        team = _make_team(
            specialists=(
                _make_spec('a'),
                _make_spec('b'),
            ),
            max_concurrent=2,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        result = orchestrator.run_team('task', 'test-team')

        assert result['status'] == 'ok'
        assert result['specialist_count'] == 2
        output_parts = result['output'].split('\n\n---\n\n')
        assert len(output_parts) == 2

    def test_timeout_returns_without_waiting_for_slow_specialist(self, tmp_path: Path):
        def _slow_run_subagent(**kwargs: object) -> dict[str, object]:
            time.sleep(0.5)
            return {'status': 'ok', 'output': 'late'}

        manager = MagicMock()
        manager.run_subagent = _slow_run_subagent

        team = _make_team(
            specialists=(_make_spec('slow'),),
            max_concurrent=1,
        )

        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}

        start = time.monotonic()
        result = orchestrator.run_team('task', 'test-team', timeout=0.05)
        elapsed = time.monotonic() - start

        assert elapsed < 0.25
        assert result['status'] == 'ok'
        assert result['specialist_count'] == 1
        assert 'timeout' in result['output']


class TestTeamOrchestratorEdgeCases:
    def test_unknown_team(self, tmp_path: Path):
        manager = MagicMock()
        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        result = orchestrator.run_team('task', 'nonexistent')
        assert result['status'] == 'error'
        assert 'unknown team' in result['message']

    def test_empty_specialists(self, tmp_path: Path):
        manager = MagicMock()
        team = _make_team(specialists=(), max_concurrent=3)
        orchestrator = TeamOrchestrator(
            root=tmp_path,
            subagent_manager=manager,
        )
        orchestrator._defs = {'test-team': team}
        result = orchestrator.run_team('task', 'test-team')
        assert result['status'] == 'ok'
        assert result['specialist_count'] == 0
        assert result['output'] == ''
