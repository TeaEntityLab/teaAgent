from __future__ import annotations

from teaagent.agent_factory import AgentFactory
from teaagent.coordinator import WorkflowStep
from teaagent.plugin_system import PluginRegistry
from teaagent.workflow_engine import WorkflowEngine


class TestWorkflowEngineSelfHealing:
    """Test suite for WorkflowEngine self-healing validation loops."""

    def test_self_healing_enabled(self):
        """Test that self-healing can be enabled."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory, enable_self_healing=True)

        assert engine._enable_self_healing is True
        assert engine._max_self_healing_attempts == 3

    def test_self_healing_disabled(self):
        """Test that self-healing can be disabled."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory, enable_self_healing=False)

        assert engine._enable_self_healing is False

    def test_max_self_healing_attempts_configurable(self):
        """Test that max self-healing attempts is configurable."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(
            registry, factory, enable_self_healing=True, max_self_healing_attempts=5
        )

        assert engine._max_self_healing_attempts == 5

    def test_validation_result_passed(self):
        """Test ValidationResult when validation passes."""
        from teaagent.workflow_engine import ValidationResult

        result = ValidationResult(passed=True, errors=[])

        assert result.passed is True
        assert len(result.errors) == 0

    def test_validation_result_failed(self):
        """Test ValidationResult when validation fails."""
        from teaagent.workflow_engine import ValidationResult

        result = ValidationResult(passed=False, errors=['Error 1', 'Error 2'])

        assert result.passed is False
        assert len(result.errors) == 2

    def test_step_execution_validation_fields(self):
        """Test that StepExecution has validation fields."""
        from teaagent.workflow_engine import StepExecution

        result = StepExecution(
            step_id=1,
            success=True,
            validation_passed=True,
            validation_errors=[],
            self_healing_attempts=0,
        )

        assert result.validation_passed is True
        assert result.self_healing_attempts == 0

    def test_self_correction_prompt_generation(self):
        """Test self-correction prompt generation."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        engine = WorkflowEngine(registry, factory, enable_self_healing=True)

        step = WorkflowStep(
            step_id=1,
            description='Test step',
            agent_name='test-agent',
            tools=('read_file',),
        )

        errors = ['Ruff error: line too long', 'Mypy error: type mismatch']

        prompt = engine._generate_self_correction_prompt(step, errors)

        assert 'Self-Correction Instructions' in prompt
        assert 'Ruff error: line too long' in prompt
        assert 'Mypy error: type mismatch' in prompt
