from __future__ import annotations

from teaagent.agent_factory import AgentFactory
from teaagent.coordinator import WorkflowPlan, WorkflowStep
from teaagent.plugin_system import AgentPlugin, PluginRegistry
from teaagent.workflow_engine import (
    StepExecution,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowState,
)


class TestWorkflowEngine:
    """Test suite for WorkflowEngine."""

    def test_engine_initialization(self):
        """Test that engine initializes with registry and factory."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        assert engine._plugin_registry is registry
        assert engine._agent_factory is factory

    def test_execute_single_step_workflow(self):
        """Test executing a single-step workflow."""
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
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Test step',
                    agent_name='test-agent',
                    tools=('read_file',),
                )
            ],
        )

        execution = engine.execute_workflow(plan)

        assert execution.state == WorkflowState.COMPLETED
        assert len(execution.step_results) == 1
        assert execution.step_results[1].success is True

    def test_execute_multi_step_workflow(self):
        """Test executing a multi-step workflow."""
        registry = PluginRegistry()
        registry.register_agent(
            AgentPlugin(
                name='agent-1',
                description='Agent 1',
                system_prompt='Test',
                tools=('read_file',),
            )
        )
        registry.register_agent(
            AgentPlugin(
                name='agent-2',
                description='Agent 2',
                system_prompt='Test',
                tools=('grep',),
            )
        )
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Multi-step task',
            classification=None,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Step 1',
                    agent_name='agent-1',
                    tools=('read_file',),
                ),
                WorkflowStep(
                    step_id=2,
                    description='Step 2',
                    agent_name='agent-2',
                    tools=('grep',),
                ),
            ],
        )

        execution = engine.execute_workflow(plan)

        assert execution.state == WorkflowState.COMPLETED
        assert len(execution.step_results) == 2
        assert execution.step_results[1].success is True
        assert execution.step_results[2].success is True

    def test_execute_workflow_with_missing_agent(self):
        """Test workflow execution fails when agent is missing."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Test step',
                    agent_name='nonexistent-agent',
                    tools=('read_file',),
                )
            ],
        )

        execution = engine.execute_workflow(plan)

        assert execution.state == WorkflowState.FAILED
        assert execution.step_results[1].success is False
        assert 'not found' in execution.step_results[1].error

    def test_enter_polish_mode(self):
        """Test entering polish mode."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[],
        )

        execution = WorkflowExecution(plan=plan)
        engine.enter_polish_mode(execution)

        assert execution.state == WorkflowState.PAUSED
        assert engine._active_workflow is execution

    def test_polish_agent_prompt(self):
        """Test polishing an agent's prompt."""
        registry = PluginRegistry()
        registry.register_agent(
            AgentPlugin(
                name='test-agent',
                description='Test agent',
                system_prompt='Old prompt',
                tools=('read_file',),
            )
        )
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[],
        )

        execution = WorkflowExecution(plan=plan)
        engine.enter_polish_mode(execution)

        new_prompt = 'New prompt'
        applied, message = engine.polish_agent_prompt(
            execution, 'test-agent', new_prompt, show_diff=False
        )

        assert applied is True
        assert 'test-agent' in message

        # Verify agent was updated
        agent = registry.get_agent('test-agent')
        assert agent.system_prompt == new_prompt

    def test_polish_nonexistent_agent(self):
        """Test polishing fails for nonexistent agent."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[],
        )

        execution = WorkflowExecution(plan=plan)
        engine.enter_polish_mode(execution)

        applied, message = engine.polish_agent_prompt(
            execution, 'nonexistent', 'new prompt', show_diff=False
        )

        assert applied is False
        assert 'not found' in message

    def test_resume_workflow(self):
        """Test resuming a paused workflow."""
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
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[
                WorkflowStep(
                    step_id=1,
                    description='Step 1',
                    agent_name='test-agent',
                    tools=('read_file',),
                ),
                WorkflowStep(
                    step_id=2,
                    description='Step 2',
                    agent_name='test-agent',
                    tools=('read_file',),
                ),
            ],
        )

        execution = WorkflowExecution(plan=plan)
        execution.step_results[1] = StepExecution(
            step_id=1, success=True, output='Done'
        )

        resumed = engine.resume_workflow(execution, from_step=2)

        assert len(resumed.step_results) == 2
        assert resumed.step_results[2].success is True

    def test_get_workflow_summary(self):
        """Test getting workflow execution summary."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[],
        )

        execution = WorkflowExecution(plan=plan)
        execution.state = WorkflowState.COMPLETED
        execution.step_results[1] = StepExecution(
            step_id=1, success=True, execution_time_seconds=1.5
        )

        summary = engine.get_workflow_summary(execution)

        assert 'Test task' in summary
        assert 'completed' in summary
        assert 'Step 1' in summary

    def test_cancel_workflow(self):
        """Test cancelling a workflow."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory)

        plan = WorkflowPlan(
            task_description='Test task',
            classification=None,
            steps=[],
        )

        execution = WorkflowExecution(plan=plan)
        engine.cancel_workflow(execution)

        assert execution.state == WorkflowState.FAILED
        assert engine._active_workflow is None
