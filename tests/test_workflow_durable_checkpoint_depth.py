"""Tests for durable checkpoints and depth limit enforcement in WorkflowEngine."""

from __future__ import annotations

import pytest

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


@pytest.fixture
def workflow_fixtures():
    """Set up test fixtures."""
    registry = PluginRegistry()
    registry.register_agent(
        AgentPlugin(
            name='test-agent',
            description='Test agent',
            system_prompt='Test',
            tools=('read_file',),
        )
    )
    factory = AgentFactory(registry, persist_to_disk=False)
    dummy_classification = TaskClassification(
        task_type=TaskType.GENERAL,
        complexity=TaskComplexity.SIMPLE,
        confidence=1.0,
    )
    return registry, factory, dummy_classification


def test_workflow_engine_enforces_depth_limit(workflow_fixtures) -> None:
    registry, factory, dummy_classification = workflow_fixtures
    engine = WorkflowEngine(registry, factory)
    plan = WorkflowPlan(
        task_description='Nested workflow task',
        classification=dummy_classification,
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
    assert execution.state == WorkflowState.FAILED
    assert 0 in execution.step_results
    assert not execution.step_results[0].success
    assert 'depth' in execution.step_results[0].error.lower()


def test_workflow_engine_durable_checkpointing_saves_after_each_step(
    workflow_fixtures,
) -> None:
    registry, factory, dummy_classification = workflow_fixtures
    ckpt_store = InMemoryCheckpointStore()
    engine = WorkflowEngine(
        registry,
        factory,
        checkpoint_store=ckpt_store,
    )

    plan = WorkflowPlan(
        task_description='Checkpointing task',
        classification=dummy_classification,
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
    assert execution.state == WorkflowState.COMPLETED

    # Load checkpoint directly from store and verify it has step results
    ckpt = ckpt_store.load('run-ckpt-1')
    assert ckpt is not None
    assert 'workflow_execution' in ckpt

    saved_execution = ckpt['workflow_execution']
    assert saved_execution['state'] == 'completed'
    assert saved_execution['current_step'] == 2
    assert '1' in saved_execution['step_results']
    assert '2' in saved_execution['step_results']


def test_workflow_engine_restores_from_durable_checkpoint(
    workflow_fixtures,
) -> None:
    registry, factory, dummy_classification = workflow_fixtures
    ckpt_store = InMemoryCheckpointStore()
    engine = WorkflowEngine(
        registry,
        factory,
        checkpoint_store=ckpt_store,
    )

    plan = WorkflowPlan(
        task_description='Restore task',
        classification=dummy_classification,
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

    assert execution.state == WorkflowState.COMPLETED
    # Check step results
    assert execution.step_results[1].output == 'Pre-completed step 1 output'
    assert execution.step_results[2].success
    # The output of step 2 should be simulated newly
    assert 'Step 2 executed' in execution.step_results[2].output
