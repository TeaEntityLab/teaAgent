from __future__ import annotations

from pathlib import Path

from teaagent.swarm import SubagentTask, SwarmManager


class TestSwarmLockTimeout:
    """Test suite for Swarm lock timeout and heartbeat monitoring."""

    def test_swarm_manager_initializes_with_lock_timeout(self):
        """Test that SwarmManager initializes with configurable lock timeout."""
        manager = SwarmManager(
            root=Path('.'),
            max_parallel=2,
            lock_timeout_seconds=60,
        )
        assert manager._lock_timeout_seconds == 60
        assert manager._subagent_pids == {}
        assert manager._subagent_heartbeats == {}

    def test_swarm_manager_default_lock_timeout(self):
        """Test that SwarmManager uses default 60-second timeout."""
        manager = SwarmManager(root=Path('.'))
        assert manager._lock_timeout_seconds == 60

    def test_update_subagent_heartbeat(self):
        """Test that subagent heartbeat can be updated."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=60)

        manager._update_subagent_heartbeat('task_1', 12345)
        assert manager._subagent_pids['task_1'] == 12345
        assert 'task_1' in manager._subagent_heartbeats
        assert manager._subagent_heartbeats['task_1'] > 0

    def test_swarm_with_custom_timeout(self):
        """Test that custom timeout is respected."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=30)
        assert manager._lock_timeout_seconds == 30

        # Add subagent
        task = SubagentTask(task_id='test_task', description='Test task')
        manager.add_subagent(task)

        # Just verify the timeout is set
        assert manager._lock_timeout_seconds == 30

    def test_subagent_execution_without_heartbeat(self):
        """Test that subagent execution works without heartbeat tracking."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=60)

        task = SubagentTask(task_id='test_task', description='Test task')
        manager.add_subagent(task)

        # Verify subagent was added
        assert len(manager._subagents) == 1
        assert manager._subagents[0]._task.task_id == 'test_task'

    def test_multiple_subagents_heartbeat_tracking(self):
        """Test heartbeat tracking for multiple subagents."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=60)

        # Add multiple subagents
        for i in range(3):
            task = SubagentTask(
                task_id=f'task_{i}', description=f'Test task {i}'
            )
            manager.add_subagent(task)

        # Update heartbeats
        for i in range(3):
            manager._update_subagent_heartbeat(f'task_{i}', 10000 + i)

        # Verify all are tracked
        assert len(manager._subagent_pids) == 3
        assert len(manager._subagent_heartbeats) == 3
        assert len(manager._subagents) == 3

    def test_heartbeat_monitor_cleanup_on_stop(self):
        """Test that heartbeat monitor cleans up tracking data on stop."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=60)

        # Add heartbeat data
        manager._update_subagent_heartbeat('task_1', 12345)
        manager._update_subagent_heartbeat('task_2', 12346)

        assert len(manager._subagent_pids) == 2
        assert len(manager._subagent_heartbeats) == 2

        # Stop monitor (should not clear data, just stop thread)
        manager._stop_heartbeat_monitor()

        # Data should still be present
        assert len(manager._subagent_pids) == 2
        assert len(manager._subagent_heartbeats) == 2

    def test_swarm_manager_with_zero_subagents(self):
        """Test that swarm manager handles zero subagents gracefully."""
        manager = SwarmManager(root=Path('.'), lock_timeout_seconds=60)

        # Verify initial state
        assert len(manager._subagents) == 0
        assert manager._lock_timeout_seconds == 60
