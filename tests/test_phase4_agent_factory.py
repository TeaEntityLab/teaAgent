from __future__ import annotations

import pytest

from teaagent.agent_factory import AgentFactory, AgentSpecification
from teaagent.plugin_system import PluginRegistry


class TestAgentFactory:
    """Test suite for AgentFactory."""

    def test_factory_initialization(self):
        """Test that factory initializes with plugin registry."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, persist_to_disk=False)
        assert factory._plugin_registry is registry
        assert factory._persist_to_disk is False

    def test_generate_agent_template(self):
        """Test agent generation with template (no LLM)."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file', 'grep'),
        )

        agent = factory.generate_agent(spec)

        assert agent.name == 'test-agent'
        assert agent.description == 'A test agent'
        assert agent.tools == ('read_file', 'grep')
        assert 'test-agent' in agent.system_prompt
        assert 'testing' in agent.system_prompt

    def test_generate_agent_registers_in_registry(self):
        """Test that generated agents are registered in PluginRegistry."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file',),
        )

        factory.generate_agent(spec)

        registered = registry.get_agent('test-agent')
        assert registered is not None
        assert registered.name == 'test-agent'

    def test_hot_reload_agent(self):
        """Test hot-reloading an agent with new prompt."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file',),
        )

        factory.generate_agent(spec)

        new_prompt = '# Updated Agent\n\nYou are now an expert.'
        updated = factory.hot_reload_agent('test-agent', new_prompt)

        assert updated.system_prompt == new_prompt

        # Verify registry was updated
        registered = registry.get_agent('test-agent')
        assert registered.system_prompt == new_prompt

    def test_hot_reload_nonexistent_agent(self):
        """Test hot-reload fails for nonexistent agent."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        with pytest.raises(ValueError, match='not found'):
            factory.hot_reload_agent('nonexistent', 'new prompt')

    def test_list_dynamic_agents(self):
        """Test listing dynamically generated agents."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec1 = AgentSpecification(
            name='agent-1',
            description='Agent 1',
            task_domain='testing',
            required_tools=('read_file',),
        )

        spec2 = AgentSpecification(
            name='agent-2',
            description='Agent 2',
            task_domain='review',
            required_tools=('grep',),
        )

        factory.generate_agent(spec1)
        factory.generate_agent(spec2)

        agents = factory.list_dynamic_agents()
        assert 'agent-1' in agents
        assert 'agent-2' in agents

    def test_agent_specification_with_personality(self):
        """Test agent generation with personality traits."""
        registry = PluginRegistry()
        factory = AgentFactory(registry, llm_adapter=None, persist_to_disk=False)

        spec = AgentSpecification(
            name='test-agent',
            description='A test agent',
            task_domain='testing',
            required_tools=('read_file',),
            personality_traits=('friendly', 'thorough'),
        )

        agent = factory.generate_agent(spec)

        assert 'friendly' in agent.system_prompt or 'thorough' in agent.system_prompt
