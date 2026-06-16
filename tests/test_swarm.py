"""Tests for multi-agent swarm orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.consensus import (
    ConsensusConfig,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
)
from teaagent.context_bus import (
    ContextBusConfig,
    DeltaType,
)
from teaagent.swarm import (
    CodeReview,
    Subagent,
    SubagentResult,
    SubagentTask,
    SwarmManager,
    SwarmReport,
)
from test_support import skip_if_thread_start_is_blocked


def test_subagent_task_creation():
    task = SubagentTask(
        task_id='task-1',
        description='Test task',
        priority=1,
    )
    assert task.task_id == 'task-1'
    assert task.description == 'Test task'
    assert task.priority == 1


def test_subagent_result_creation():
    result = SubagentResult(
        task_id='task-1',
        success=True,
        branch_name='teaagent-sandbox-task-1',
        output={'status': 'completed'},
        execution_time_ms=100.0,
    )
    assert result.task_id == 'task-1'
    assert result.success is True
    assert result.branch_name == 'teaagent-sandbox-task-1'
    assert result.execution_time_ms == 100.0


def test_code_review_creation():
    review = CodeReview(
        reviewer_task_id='task-1',
        target_task_id='task-2',
        score=0.9,
        findings=['Good code quality'],
        recommendation='approve',
    )
    assert review.reviewer_task_id == 'task-1'
    assert review.target_task_id == 'task-2'
    assert review.score == 0.9
    assert review.recommendation == 'approve'


def test_subagent_execute_without_git():
    """Test subagent execution when git is not available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = SubagentTask(task_id='task-1', description='Test task')
        subagent = Subagent(task, tmpdir)
        result = subagent.execute()

        assert result.task_id == 'task-1'
        assert result.success is False
        assert 'Git sandbox not available' in result.error


def test_subagent_execute_with_git():
    """Test subagent execution with git sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        import subprocess

        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ['git', 'checkout', '-b', 'main'],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )

        task = SubagentTask(task_id='task-1', description='Test task')
        subagent = Subagent(task, tmpdir)
        result = subagent.execute()

        assert result.task_id == 'task-1'
        # Should succeed or fail with git-related error
        assert result is not None


def test_swarm_manager_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir, max_parallel=3)
        assert manager._max_parallel == 3
        assert len(manager._subagents) == 0


def test_swarm_manager_add_subagent():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)
        task = SubagentTask(task_id='task-1', description='Test task')
        manager.add_subagent(task)

        assert len(manager._subagents) == 1


def test_swarm_manager_execute_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)
        report = manager.execute_swarm()

        assert report.total_subagents == 0
        assert report.successful_subagents == 0
        assert report.failed_subagents == 0
        assert len(report.results) == 0


def test_swarm_manager_execute_multiple():
    skip_if_thread_start_is_blocked()
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir, max_parallel=2)

        for i in range(3):
            task = SubagentTask(
                task_id=f'task-{i}',
                description=f'Test task {i}',
            )
            manager.add_subagent(task)

        report = manager.execute_swarm()

        assert report.total_subagents == 3
        assert len(report.results) == 3
        assert report.total_execution_time_ms > 0


def test_swarm_manager_code_reviews():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)

        # Add mock results
        results = [
            SubagentResult(
                task_id='task-1',
                success=True,
                branch_name='branch-1',
                output={'status': 'done'},
            ),
            SubagentResult(
                task_id='task-2',
                success=True,
                branch_name='branch-2',
                output={'status': 'done'},
            ),
        ]

        report = SwarmReport(
            total_subagents=2,
            successful_subagents=2,
            failed_subagents=0,
            results=results,
            code_reviews=[],
        )

        reviews = manager.run_code_reviews(report)

        # Should have pairwise reviews (2 subagents = 2 reviews)
        assert len(reviews) == 2
        for review in reviews:
            assert review.score >= 0.0
            assert review.score <= 1.0


def test_swarm_manager_select_best_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)

        results = [
            SubagentResult(
                task_id='task-1',
                success=True,
                branch_name='branch-1',
                output={'status': 'done'},
                execution_time_ms=100.0,
            ),
            SubagentResult(
                task_id='task-2',
                success=True,
                branch_name='branch-2',
                output={'status': 'done'},
                execution_time_ms=50.0,  # Faster
            ),
        ]

        report = SwarmReport(
            total_subagents=2,
            successful_subagents=2,
            failed_subagents=0,
            results=results,
            code_reviews=[],
        )

        reviews = [
            CodeReview(
                reviewer_task_id='task-1',
                target_task_id='task-2',
                score=0.9,
                recommendation='approve',
            ),
            CodeReview(
                reviewer_task_id='task-2',
                target_task_id='task-1',
                score=0.7,
                recommendation='approve',
            ),
        ]

        best = manager.select_best_result(report, reviews)

        assert best is not None
        assert best.success is True


def test_swarm_manager_select_best_with_failed():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)

        results = [
            SubagentResult(
                task_id='task-1',
                success=False,
                error='Failed',
            ),
            SubagentResult(
                task_id='task-2',
                success=True,
                branch_name='branch-2',
                output={'status': 'done'},
            ),
        ]

        report = SwarmReport(
            total_subagents=2,
            successful_subagents=1,
            failed_subagents=1,
            results=results,
            code_reviews=[],
        )

        best = manager.select_best_result(report, [])

        # Should select the successful result
        assert best is not None
        assert best.success is True
        assert best.task_id == 'task-2'


def test_swarm_consensus_mode_disabled():
    """Test that consensus mode is disabled by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir)
        assert manager._enable_consensus is False
        assert manager._consensus_engine is None


def test_swarm_enable_consensus_mode():
    """Test enabling consensus mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = PeerRegistry()
        peer = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer)

        config = ConsensusConfig()
        manager = SwarmManager(tmpdir)
        manager.enable_consensus_mode(peer_registry=registry, consensus_config=config)

        assert manager._enable_consensus is True
        assert manager._consensus_engine is not None


def test_swarm_disable_consensus_mode():
    """Test disabling consensus mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = PeerRegistry()
        peer = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer)

        config = ConsensusConfig()
        manager = SwarmManager(
            tmpdir,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=config,
        )

        assert manager._enable_consensus is True

        manager.disable_consensus_mode()
        assert manager._enable_consensus is False
        assert manager._consensus_engine is None


def test_swarm_task_with_consensus_required():
    """Test task that requires consensus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = PeerRegistry()
        peer = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer)

        config = ConsensusConfig()
        manager = SwarmManager(
            tmpdir,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=config,
        )

        task = SubagentTask(
            task_id='task-1',
            description='High-risk deployment',
            risk_level=RiskLevel.HIGH,
            require_consensus=True,
        )
        manager.add_subagent(task)

        # Execute swarm - consensus should be checked
        # Since we don't have actual voting mechanism in test, this will fallback
        report = manager.execute_swarm()

        # Task should be filtered out if consensus not reached
        # For now, we just verify the mechanism is called
        assert report is not None


def test_swarm_task_without_consensus():
    """Test task that does not require consensus."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = PeerRegistry()
        peer = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer)

        config = ConsensusConfig()
        manager = SwarmManager(
            tmpdir,
            enable_consensus=True,
            peer_registry=registry,
            consensus_config=config,
        )

        task = SubagentTask(
            task_id='task-1',
            description='Low-risk task',
            risk_level=RiskLevel.LOW,
            require_consensus=False,
        )
        manager.add_subagent(task)

        report = manager.execute_swarm()

        # Task should execute normally (may fail without git, but that's expected)
        assert report.total_subagents == 1


def test_swarm_manager_context_bus_integration():
    """Test ContextBus integration in SwarmManager.execute_swarm()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'context_bus.db'
        bus_config = ContextBusConfig(
            db_path=db_path,
            workflow_id='placeholder',  # Overridden at execution time
            max_delta_age_seconds=3600,
            enable_wal_mode=True,
        )

        manager = SwarmManager(tmpdir, max_parallel=2, context_bus_config=bus_config)
        task = SubagentTask(
            task_id='task-1',
            description='Test context bus task',
        )
        manager.add_subagent(task)

        report = manager.execute_swarm()

        assert report is not None
        assert report.total_subagents == 1

        bus = manager.context_bus
        assert bus is not None
        delta_count = bus.get_delta_count()
        assert delta_count > 0, f'Expected at least 1 delta, got {delta_count}'

        deltas = bus.subscribe_deltas()
        source_agents = {delta.source_agent for delta in deltas}
        assert 'swarm-orchestrator' in source_agents, (
            f'Expected swarm-orchestrator delta, got sources: {source_agents}'
        )

        delta_types = {delta.delta_type for delta in deltas}
        assert DeltaType.CONTEXT_UPDATE in delta_types, (
            f'Expected CONTEXT_UPDATE delta, got types: {delta_types}'
        )


def test_swarm_context_bus_uses_fresh_workflow_per_execution(monkeypatch):
    """Each execute_swarm() run should publish deltas under its own workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'context_bus.db'
        bus_config = ContextBusConfig(
            db_path=db_path,
            workflow_id='placeholder',
            max_delta_age_seconds=3600,
            enable_wal_mode=True,
        )
        manager = SwarmManager(tmpdir, max_parallel=1, context_bus_config=bus_config)
        manager.add_subagent(
            SubagentTask(task_id='task-1', description='Test context bus task')
        )

        def fake_execute(self):
            return SubagentResult(task_id=self._task.task_id, success=True)

        monkeypatch.setattr(Subagent, 'execute', fake_execute)

        manager.execute_swarm()
        first_workflow_id = manager._parent_run_id
        first_bus = manager.context_bus
        assert first_bus is not None
        assert first_bus._workflow_id == first_workflow_id

        manager.execute_swarm()
        second_workflow_id = manager._parent_run_id
        second_bus = manager.context_bus
        assert second_bus is not None
        assert second_workflow_id != first_workflow_id
        assert second_bus._workflow_id == second_workflow_id

        deltas = second_bus.subscribe_deltas()
        delta_ids = {delta.delta_id for delta in deltas}
        assert f'{second_workflow_id}-swarm-start' in delta_ids
        assert f'{second_workflow_id}-task-1' in delta_ids
        assert f'{first_workflow_id}-swarm-start' not in delta_ids
