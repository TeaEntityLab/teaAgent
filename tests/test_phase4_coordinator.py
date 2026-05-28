from __future__ import annotations

from teaagent.coordinator import (
    TaskClassification,
    TaskComplexity,
    TaskCoordinator,
    TaskType,
)
from teaagent.plugin_system import AgentPlugin, PluginRegistry


class TestTaskCoordinator:
    """Test suite for TaskCoordinator."""

    def test_coordinator_initialization(self):
        """Test that coordinator initializes with plugin registry."""
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry)
        assert coordinator._plugin_registry is registry
        assert coordinator._default_agent == 'general'

    def test_classify_task_heuristic(self):
        """Test heuristic task classification without LLM."""
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry, llm_adapter=None)

        # Test code review classification
        result = coordinator.classify_task('Review this code for bugs')
        assert result.task_type == TaskType.CODE_REVIEW
        assert result.suggested_agent == 'code-reviewer'

        # Test testing classification
        result = coordinator.classify_task('Write tests for this module')
        assert result.task_type == TaskType.TESTING
        assert result.suggested_agent == 'tester'

        # Test documentation classification
        result = coordinator.classify_task('Update the README')
        assert result.task_type == TaskType.DOCUMENTATION
        assert result.suggested_agent == 'docs-writer'

    def test_classify_task_multi_step_detection(self):
        """Test that complex tasks are marked as multi-step."""
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry, llm_adapter=None)

        result = coordinator.classify_task('Refactor this module')
        assert result.requires_multi_step is True
        assert result.estimated_steps >= 2

        result = coordinator.classify_task('Fix this bug')
        assert result.requires_multi_step is True

        result = coordinator.classify_task('Implement this feature')
        assert result.requires_multi_step is True
        assert result.estimated_steps >= 3

    def test_generate_single_step_workflow(self):
        """Test workflow generation for simple tasks."""
        registry = PluginRegistry()
        registry.register_agent(
            AgentPlugin(
                name='test-agent',
                description='Test agent',
                system_prompt='Test',
                tools=('read_file',),
            )
        )
        coordinator = TaskCoordinator(registry, llm_adapter=None)

        classification = TaskClassification(
            task_type=TaskType.GENERAL,
            complexity=TaskComplexity.SIMPLE,
            confidence=0.8,
            suggested_agent='test-agent',
            requires_multi_step=False,
        )

        plan = coordinator.generate_workflow_plan('Simple task', classification)

        assert len(plan.steps) == 1
        assert plan.steps[0].agent_name == 'test-agent'
        assert plan.steps[0].description == 'Simple task'

    def test_generate_multi_step_workflow_heuristic(self):
        """Test heuristic multi-step workflow generation."""
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry, llm_adapter=None)

        classification = TaskClassification(
            task_type=TaskType.REFACTORING,
            complexity=TaskComplexity.COMPLEX,
            confidence=0.7,
            requires_multi_step=True,
            estimated_steps=3,
        )

        plan = coordinator.generate_workflow_plan('Refactor module', classification)

        assert len(plan.steps) >= 2
        assert plan.classification == classification

    def test_route_task_integration(self):
        """Test integrated task routing."""
        registry = PluginRegistry()
        coordinator = TaskCoordinator(registry, llm_adapter=None)

        classification, plan = coordinator.route_task('Review this code')

        assert classification.task_type == TaskType.CODE_REVIEW
        assert len(plan.steps) >= 1
        assert plan.task_description == 'Review this code'
