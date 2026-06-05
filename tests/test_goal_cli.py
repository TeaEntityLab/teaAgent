"""Tests for goal CLI handlers."""

import argparse
import tempfile
from pathlib import Path

from teaagent.cli._handlers._goal import goal_list_command, goal_status_command
from teaagent.goal_record import GoalRecord


def _save_goal(root: Path, goal: GoalRecord) -> None:
    from teaagent.goal_record import GoalStore

    store = GoalStore(str(root))
    store.save(goal)


def test_goal_list_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        args = argparse.Namespace(root=tmpdir)
        result = goal_list_command(args)
        assert result == 0


def test_goal_list_with_goals():
    with tempfile.TemporaryDirectory() as tmpdir:
        g1 = GoalRecord(goal_id='g-test-001', objective='Refactor auth module', status='active')
        g2 = GoalRecord(goal_id='g-test-002', objective='Add new API endpoint', status='completed')
        _save_goal(Path(tmpdir), g1)
        _save_goal(Path(tmpdir), g2)

        args = argparse.Namespace(root=tmpdir)
        result = goal_list_command(args)
        assert result == 0


def test_goal_list_truncates_long_objective():
    with tempfile.TemporaryDirectory() as tmpdir:
        long_obj = 'A' * 80
        goal = GoalRecord(goal_id='g-long', objective=long_obj, status='proposed')
        _save_goal(Path(tmpdir), goal)

        args = argparse.Namespace(root=tmpdir)
        result = goal_list_command(args)
        assert result == 0


def test_goal_status_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        goal = GoalRecord(
            goal_id='g-status-001',
            objective='Test status command',
            status='active',
            cost_cents=42.5,
            blockers=['waiting for review'],
            next_gate='approval',
            spec_id='spec-abc',
        )
        _save_goal(Path(tmpdir), goal)

        args = argparse.Namespace(goal_id='g-status-001', root=tmpdir)
        result = goal_status_command(args)
        assert result == 0


def test_goal_status_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        args = argparse.Namespace(goal_id='nonexistent', root=tmpdir)
        result = goal_status_command(args)
        assert result == 1
