"""Test module for SwarmManager execution flow acceptance.

Covers swarm creation, execution, tournament scoring, and heartbeat monitoring.

Acceptance Criteria:
- AC1: SwarmManager creates with correct config and registers subagents
- AC2: execute_swarm returns SwarmReport with accurate success/failure counts
- AC3: _select_tournament_winner picks the highest fitness score correctly
- AC4: tick_heartbeat advances Subagent.last_heartbeat
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from teaagent.swarm import (
    PromptFitnessMetrics,
    Subagent,
    SubagentResult,
    SubagentTask,
    SwarmManager,
    SwarmReport,
    compute_prompt_fitness_score,
    fitness_metrics_from_result,
    rank_prompt_tournament,
)

# ---------------------------------------------------------------------------
# AC1: SwarmManager creation and task registration
# ---------------------------------------------------------------------------


def test_swarm_manager_creation() -> None:
    """Create SwarmManager, add tasks, verify internal structure."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SwarmManager(root, max_parallel=2)

        assert manager._max_parallel == 2
        assert len(manager._subagents) == 0

        manager.add_subagent(
            SubagentTask(
                task_id='task-a',
                description='Analyze code quality',
                priority=3,
            )
        )
        manager.add_subagent(
            SubagentTask(
                task_id='task-b',
                description='Fix type errors',
                context={'file': 'src/main.py'},
                priority=5,
            )
        )
        manager.add_subagent(
            SubagentTask(
                task_id='task-c',
                description='Run integration tests',
                priority=1,
            )
        )

        assert len(manager._subagents) == 3
        task_ids = {s._task.task_id for s in manager._subagents}
        assert task_ids == {'task-a', 'task-b', 'task-c'}
        descriptions = {s._task.description for s in manager._subagents}
        assert 'Analyze code quality' in descriptions
        assert 'Fix type errors' in descriptions
        assert 'Run integration tests' in descriptions

        priorities = [s._task.priority for s in manager._subagents]
        assert priorities == [3, 5, 1]

        task_b = next(s for s in manager._subagents if s._task.task_id == 'task-b')
        assert task_b._task.context == {'file': 'src/main.py'}


# ---------------------------------------------------------------------------
# AC2: Swarm execution with mocked subagents
# ---------------------------------------------------------------------------


def test_swarm_execute_mocked() -> None:
    """Execute swarm with mock subagents, verify SwarmReport integrity."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SwarmManager(root, max_parallel=2)

        manager.add_subagent(SubagentTask(task_id='ok-1', description='Passing task'))
        manager.add_subagent(
            SubagentTask(task_id='ok-2', description='Another passing task')
        )

        call_count = {'n': 0}

        def fake_execute(self: Subagent) -> SubagentResult:
            idx = call_count['n']
            call_count['n'] += 1
            return SubagentResult(
                task_id=self._task.task_id,
                success=True,
                branch_name=f'branch-{idx}',
                output={'status': 'completed'},
                execution_time_ms=50.0 + idx * 10,
                cost_cents=1.5,
                test_results={'tokens': 100, 'errors': 0},
            )

        with patch.object(Subagent, 'execute', fake_execute):
            report = manager.execute_swarm()

        assert isinstance(report, SwarmReport)
        assert report.total_subagents == 2
        assert report.successful_subagents == 2
        assert report.failed_subagents == 0
        assert len(report.results) == 2
        assert report.total_execution_time_ms > 0
        assert report.total_cost_cents > 0

        result_ids = {r.task_id for r in report.results}
        assert result_ids == {'ok-1', 'ok-2'}
        for result in report.results:
            assert result.success
            assert result.branch_name is not None


def test_swarm_execute_mocked_mixed_results() -> None:
    """Swarm execution with mix of success and failure returns accurate counts."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SwarmManager(root, max_parallel=2)

        manager.add_subagent(
            SubagentTask(task_id='succeed', description='Task that succeeds')
        )
        manager.add_subagent(
            SubagentTask(task_id='fail', description='Task that fails')
        )

        def fake_execute(self: Subagent) -> SubagentResult:
            if self._task.task_id == 'fail':
                return SubagentResult(
                    task_id=self._task.task_id,
                    success=False,
                    error='Simulated failure',
                )
            return SubagentResult(
                task_id=self._task.task_id,
                success=True,
                branch_name='branch-ok',
                output={'status': 'completed'},
                execution_time_ms=42.0,
            )

        with patch.object(Subagent, 'execute', fake_execute):
            report = manager.execute_swarm()

        assert report.total_subagents == 2
        assert report.successful_subagents == 1
        assert report.failed_subagents == 1
        assert len(report.results) == 2

        succeed = next(r for r in report.results if r.task_id == 'succeed')
        assert succeed.success
        fail = next(r for r in report.results if r.task_id == 'fail')
        assert not fail.success
        assert fail.error == 'Simulated failure'


# ---------------------------------------------------------------------------
# AC3: Tournament winner selection
# ---------------------------------------------------------------------------


def test_tournament_winner_selection_prompt_fitness() -> None:
    """_select_tournament_winner with prompt_by_task_id picks highest score."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        manager = SwarmManager(
            root,
            prompt_by_task_id={
                'sub-1': 'prompt variant alpha',
                'sub-2': 'prompt variant beta',
                'sub-3': 'prompt variant gamma',
            },
        )

        results = [
            SubagentResult(
                task_id='sub-1',
                success=True,
                execution_time_ms=100.0,
                test_results={'tokens': 50, 'errors': 0},
            ),
            SubagentResult(
                task_id='sub-2',
                success=True,
                execution_time_ms=500.0,
                test_results={'tokens': 200, 'errors': 2},
            ),
            SubagentResult(
                task_id='sub-3',
                success=False,
                execution_time_ms=200.0,
                test_results={'tokens': 80, 'errors': 3},
            ),
        ]

        winner_id, winner_score, best_result = manager._select_tournament_winner(
            results
        )

        assert winner_id == 'sub-1'
        assert winner_score > 0
        assert best_result is not None
        assert best_result.task_id == 'sub-1'

        failed_metrics = fitness_metrics_from_result(results[2], peer_results=results)
        assert compute_prompt_fitness_score(failed_metrics) == 0.0


def test_tournament_winner_single_result() -> None:
    """_select_tournament_winner with single result (no prompts) returns it directly."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SwarmManager(root)

        results = [
            SubagentResult(
                task_id='only',
                success=True,
                execution_time_ms=75.0,
                output={'status': 'completed'},
            )
        ]

        winner_id, winner_score, best_result = manager._select_tournament_winner(
            results
        )

        assert best_result is not None
        assert best_result.task_id == 'only'
        assert best_result.success


def test_rank_prompt_tournament_ordering() -> None:
    """rank_prompt_tournament returns candidates ordered by descending fitness."""
    candidates = [
        (
            'low',
            'prompt-low',
            PromptFitnessMetrics(
                success=1,
                tokens=100.0,
                min_tokens=50.0,
                time_seconds=2.0,
                min_time_seconds=0.5,
                errors=5,
            ),
        ),
        (
            'high',
            'prompt-high',
            PromptFitnessMetrics(
                success=1,
                tokens=50.0,
                min_tokens=50.0,
                time_seconds=0.5,
                min_time_seconds=0.5,
                errors=0,
            ),
        ),
        (
            'mid',
            'prompt-mid',
            PromptFitnessMetrics(
                success=1,
                tokens=80.0,
                min_tokens=50.0,
                time_seconds=1.0,
                min_time_seconds=0.5,
                errors=1,
            ),
        ),
    ]

    ranked = rank_prompt_tournament(candidates)
    assert len(ranked) == 3
    assert ranked[0][0] == 'high'
    assert ranked[0][2] == 'prompt-high'
    assert ranked[1][0] == 'mid'
    assert ranked[2][0] == 'low'
    assert ranked[0][1] >= ranked[1][1] >= ranked[2][1]


# ---------------------------------------------------------------------------
# AC4: Subagent heartbeat monitoring
# ---------------------------------------------------------------------------


def test_subagent_heartbeat_monitoring() -> None:
    """tick_heartbeat advances Subagent.last_heartbeat."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = SubagentTask(task_id='heartbeat-1', description='Heartbeat test')
        subagent = Subagent(task, root)

        initial_heartbeat = subagent.last_heartbeat
        assert initial_heartbeat > 0

        time.sleep(0.01)
        subagent.tick_heartbeat()
        updated_heartbeat = subagent.last_heartbeat
        assert updated_heartbeat > initial_heartbeat

        time.sleep(0.01)
        subagent.tick_heartbeat()
        assert subagent.last_heartbeat > updated_heartbeat


def test_subagent_heartbeat_initial_state() -> None:
    """New Subagent starts with is_running=False and last_heartbeat set."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = SubagentTask(task_id='init-1', description='Initial state test')
        subagent = Subagent(task, root)

        assert subagent.is_running is False
        assert subagent.last_heartbeat > 0
        assert abs(subagent.last_heartbeat - time.time()) < 5.0
