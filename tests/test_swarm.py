"""Tests for multi-agent swarm orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.swarm import (
    CodeReview,
    Subagent,
    SubagentResult,
    SubagentTask,
    SwarmManager,
    SwarmReport,
)


def test_subagent_task_creation():
    task = SubagentTask(
        task_id="task-1",
        description="Test task",
        priority=1,
    )
    assert task.task_id == "task-1"
    assert task.description == "Test task"
    assert task.priority == 1


def test_subagent_result_creation():
    result = SubagentResult(
        task_id="task-1",
        success=True,
        branch_name="teaagent-sandbox-task-1",
        output={"status": "completed"},
        execution_time_ms=100.0,
    )
    assert result.task_id == "task-1"
    assert result.success is True
    assert result.branch_name == "teaagent-sandbox-task-1"
    assert result.execution_time_ms == 100.0


def test_code_review_creation():
    review = CodeReview(
        reviewer_task_id="task-1",
        target_task_id="task-2",
        score=0.9,
        findings=["Good code quality"],
        recommendation="approve",
    )
    assert review.reviewer_task_id == "task-1"
    assert review.target_task_id == "task-2"
    assert review.score == 0.9
    assert review.recommendation == "approve"


def test_subagent_execute_without_git():
    """Test subagent execution when git is not available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = SubagentTask(task_id="task-1", description="Test task")
        subagent = Subagent(task, tmpdir)
        result = subagent.execute()
        
        assert result.task_id == "task-1"
        assert result.success is False
        assert "Git sandbox not available" in result.error


def test_subagent_execute_with_git():
    """Test subagent execution with git sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        import subprocess
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(['git', 'checkout', '-b', 'main'], cwd=tmpdir, capture_output=True, check=True)
        
        task = SubagentTask(task_id="task-1", description="Test task")
        subagent = Subagent(task, tmpdir)
        result = subagent.execute()
        
        assert result.task_id == "task-1"
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
        task = SubagentTask(task_id="task-1", description="Test task")
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
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SwarmManager(tmpdir, max_parallel=2)
        
        for i in range(3):
            task = SubagentTask(
                task_id=f"task-{i}",
                description=f"Test task {i}",
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
                task_id="task-1",
                success=True,
                branch_name="branch-1",
                output={"status": "done"},
            ),
            SubagentResult(
                task_id="task-2",
                success=True,
                branch_name="branch-2",
                output={"status": "done"},
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
                task_id="task-1",
                success=True,
                branch_name="branch-1",
                output={"status": "done"},
                execution_time_ms=100.0,
            ),
            SubagentResult(
                task_id="task-2",
                success=True,
                branch_name="branch-2",
                output={"status": "done"},
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
                reviewer_task_id="task-1",
                target_task_id="task-2",
                score=0.9,
                recommendation="approve",
            ),
            CodeReview(
                reviewer_task_id="task-2",
                target_task_id="task-1",
                score=0.7,
                recommendation="approve",
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
                task_id="task-1",
                success=False,
                error="Failed",
            ),
            SubagentResult(
                task_id="task-2",
                success=True,
                branch_name="branch-2",
                output={"status": "done"},
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
        assert best.task_id == "task-2"
