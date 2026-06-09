"""Tests for durable checkpoints and depth limit enforcement in WorkflowEngine."""

from __future__ import annotations

import unittest

from teaagent.agent_factory import AgentFactory
from teaagent.checkpoint import InMemoryCheckpointStore
from teaagent.coordinator import (
    TaskClassification,
    TaskComplexity,
    TaskType,
    WorkflowPlan,
    WorkflowStep,
)
from teaagent.plugin_system import AgentPlugin, PluginRegistry
from teaagent.workflow_engine import (
    StepExecution,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowState,
    workflow_execution_to_dict,
)


class TestWorkflowDurableCheckpointDepth(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PluginRegistry()
        self.registry.register_agent(
            AgentPlugin(
                name='test-agent',
                description='Test agent',
                system_prompt='Test',
                tools=('read_file',),
            )
        )
        self.factory = AgentFactory(self.registry, persist_to_disk=False)
        self.dummy_classification = TaskClassification(
            task_type=TaskType.GENERAL,
            complexity=TaskComplexity.SIMPLE,
            confidence=1.0,
        )

    def test_workflow_engine_enforces_depth_limit(self) -> None:
        engine = WorkflowEngine(self.registry, self.factory)
        plan = WorkflowPlan(
            task_description='Nested workflow task',
            classification=self.dummy_classification,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Step 1',
                    agent_name='test-agent',
                )
            ],
        )

        # Execute with depth exceeding max_depth (5)
        execution = engine.execute_workflow(plan, depth=6)
        self.assertEqual(execution.state, WorkflowState.FAILED)
        self.assertIn(0, execution.step_results)
        self.assertFalse(execution.step_results[0].success)
        self.assertIn('depth', execution.step_results[0].error.lower())

    def test_workflow_engine_durable_checkpointing_saves_after_each_step(self) -> None:
        ckpt_store = InMemoryCheckpointStore()
        engine = WorkflowEngine(
            self.registry,
            self.factory,
            checkpoint_store=ckpt_store,
        )

        plan = WorkflowPlan(
            task_description='Checkpointing task',
            classification=self.dummy_classification,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Step 1',
                    agent_name='test-agent',
                ),
                WorkflowStep(
                    step_id=2,
                    description='Step 2',
                    agent_name='test-agent',
                ),
            ],
        )

        execution = engine.execute_workflow(plan, run_id='run-ckpt-1')
        self.assertEqual(execution.state, WorkflowState.COMPLETED)

        # Load checkpoint directly from store and verify it has step results
        ckpt = ckpt_store.load('run-ckpt-1')
        self.assertIsNotNone(ckpt)
        self.assertIn('workflow_execution', ckpt)

        saved_execution = ckpt['workflow_execution']
        self.assertEqual(saved_execution['state'], 'completed')
        self.assertEqual(saved_execution['current_step'], 2)
        self.assertIn('1', saved_execution['step_results'])
        self.assertIn('2', saved_execution['step_results'])

    def test_workflow_engine_restores_from_durable_checkpoint(self) -> None:
        ckpt_store = InMemoryCheckpointStore()
        engine = WorkflowEngine(
            self.registry,
            self.factory,
            checkpoint_store=ckpt_store,
        )

        plan = WorkflowPlan(
            task_description='Restore task',
            classification=self.dummy_classification,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Step 1',
                    agent_name='test-agent',
                ),
                WorkflowStep(
                    step_id=2,
                    description='Step 2',
                    agent_name='test-agent',
                ),
            ],
        )
        run_id = 'run-restore-2'

        # Pre-populate checkpoint representing Step 1 already complete
        pre_execution = WorkflowExecution(plan=plan, run_id=run_id)
        pre_execution.current_step = 1
        pre_execution.state = WorkflowState.IN_PROGRESS
        pre_execution.step_results[1] = StepExecution(
            step_id=1,
            success=True,
            output='Pre-completed step 1 output',
            execution_time_seconds=0.1,
        )

        ckpt_store.save(
            run_id, {'workflow_execution': workflow_execution_to_dict(pre_execution)}
        )

        # Now, execute the workflow. It should pick up the checkpoint and only run step 2
        execution = engine.execute_workflow(plan, run_id=run_id)

        self.assertEqual(execution.state, WorkflowState.COMPLETED)
        # Check step results
        self.assertEqual(
            execution.step_results[1].output, 'Pre-completed step 1 output'
        )
        self.assertTrue(execution.step_results[2].success)
        # The output of step 2 should be simulated newly
        self.assertIn('Step 2 executed', execution.step_results[2].output)


if __name__ == '__main__':
    unittest.main()
