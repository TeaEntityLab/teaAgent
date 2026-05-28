from __future__ import annotations

import pytest

from teaagent.agent_factory import AgentFactory, AgentSpecification
from teaagent.plugin_system import PluginRegistry


class TestAgentFactoryEvolution:
    """Test suite for AgentFactory evolutionary prompt tuning."""

    def test_evolve_agent_prompt_heuristic(self):
        """Test heuristic prompt evolution without LLM."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file',),
        )

        factory.generate_agent(spec)

        # Evolve with feedback
        evolved = factory.evolve_agent_prompt(
            'test-agent',
            'Performance was poor on edge cases',
            {'accuracy': 0.7, 'speed': 0.9},
        )

        assert evolved.name == 'test-agent'
        assert 'Performance Feedback' in evolved.system_prompt
        assert 'edge cases' in evolved.system_prompt

    def test_evolve_nonexistent_agent(self):
        """Test evolution fails for nonexistent agent."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        with pytest.raises(ValueError, match='not found'):
            factory.evolve_agent_prompt('nonexistent', 'Feedback', {'accuracy': 0.5})

    def test_evolution_preserves_tools(self):
        """Test that evolution preserves agent tools."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file', 'grep'),
        )

        factory.generate_agent(spec)

        evolved = factory.evolve_agent_prompt(
            'test-agent', 'Feedback', {'accuracy': 0.8}
        )

        assert evolved.tools == ('read_file', 'grep')
