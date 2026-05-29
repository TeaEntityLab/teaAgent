"""Swarm execution via SubagentManager."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

from teaagent.swarm import Subagent, SubagentTask, SwarmManager


def test_subagent_uses_manager_when_configured() -> None:
    manager = MagicMock()
    manager.run_subagent.return_value = {
        'status': 'completed',
        'run_id': 'child-1',
        'final_answer': 'done',
        'lineage': {'parent_run_id': 'parent-swarm'},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        task = SubagentTask(task_id='t1', description='implement feature')
        subagent = Subagent(
            task,
            tmpdir,
            parent_run_id='parent-swarm',
            subagent_manager=manager,
            batch_index=2,
        )
        output = subagent._execute_task()
        assert output['execution'] == 'subagent_manager'
        assert output['status'] == 'completed'
        manager.run_subagent.assert_called_once()
        call = manager.run_subagent.call_args.kwargs
        assert call['parent_run_id'] == 'parent-swarm'
        assert call['batch_index'] == 2


def test_swarm_manager_with_agent_execution_factory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = MagicMock()
        config.root = tmpdir
        adapter = MagicMock()
        manager = SwarmManager.with_agent_execution(
            tmpdir, config=config, adapter=adapter
        )
        assert manager._subagent_manager is not None
