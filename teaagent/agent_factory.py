"""Agent Factory - Dynamic agent generation with LLM-structured prompts.

This module implements the Cooragent agent factory that:
1. Generates specialized system prompts using LLM structured output
2. Creates dynamic AgentPlugin instances
3. Registers agents in PluginRegistry (memory or disk)
4. Manages agent lifecycle and hot-reload for polish mode
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from teaagent.llm import LLMAdapter, LLMMessage, LLMRequest
from teaagent.plugin_system import _USER_PLUGIN_DIR, AgentPlugin, PluginRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentSpecification:
    """Specification for generating a dynamic agent."""

    name: str
    description: str
    task_domain: str
    required_tools: tuple[str, ...]
    specialization_level: str = 'expert'  # expert, intermediate, basic
    personality_traits: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()


class AgentFactory:
    """Factory for generating and registering dynamic agents."""

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        llm_adapter: Optional[LLMAdapter] = None,
        persist_to_disk: bool = False,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._llm_adapter = llm_adapter
        self._persist_to_disk = persist_to_disk
        self._user_plugin_dir = _USER_PLUGIN_DIR

        if self._persist_to_disk:
            self._user_plugin_dir.mkdir(parents=True, exist_ok=True)

    def generate_agent(
        self, spec: AgentSpecification, flush: bool = False
    ) -> AgentPlugin:
        """Generate a dynamic agent from specification.

        Args:
            spec: Agent specification.
            flush: If True, persist to disk (requires persist_to_disk=True).

        Returns:
            Generated AgentPlugin instance.
        """
        system_prompt = self._generate_system_prompt(spec)

        agent = AgentPlugin(
            name=spec.name,
            description=spec.description,
            system_prompt=system_prompt,
            tools=spec.required_tools,
        )

        # Register in memory
        self._plugin_registry.register_agent(agent)

        # Persist to disk if requested
        if flush and self._persist_to_disk:
            self._persist_agent(agent)

        logger.info(f'Generated dynamic agent: {spec.name}')
        return agent

    def _generate_system_prompt(self, spec: AgentSpecification) -> str:
        """Generate system prompt using LLM structured output.

        Args:
            spec: Agent specification.

        Returns:
            Generated system prompt as markdown.
        """
        if self._llm_adapter is None:
            return self._generate_template_prompt(spec)

        return self._generate_llm_prompt(spec)

    def _generate_template_prompt(self, spec: AgentSpecification) -> str:
        """Generate system prompt using template (no LLM)."""
        personality = ', '.join(spec.personality_traits) if spec.personality_traits else 'professional'
        constraints = '\n'.join(f'- {c}' for c in spec.constraints) if spec.constraints else ''

        prompt = f"""# {spec.name}

You are a {spec.specialization_level} {spec.task_domain} agent.

## Description
{spec.description}

## Personality
You are {personality} and focused on delivering high-quality results.

## Constraints
{constraints}

## Available Tools
You have access to the following tools: {', '.join(spec.required_tools)}

## Instructions
1. Analyze the task carefully before taking action.
2. Use your available tools efficiently.
3. Provide clear explanations for your actions.
4. Ask for clarification if the task is ambiguous.
5. Report your findings and results clearly.
"""
        return prompt

    def _generate_llm_prompt(self, spec: AgentSpecification) -> str:
        """Generate system prompt using LLM for higher quality."""
        generation_prompt = f"""Generate a specialized system prompt for an AI agent.

Agent Name: {spec.name}
Description: {spec.description}
Task Domain: {spec.task_domain}
Specialization Level: {spec.specialization_level}
Required Tools: {', '.join(spec.required_tools)}
Personality Traits: {', '.join(spec.personality_traits) if spec.personality_traits else 'professional'}
Constraints: {', '.join(spec.constraints) if spec.constraints else 'none'}

Generate a comprehensive markdown system prompt that:
1. Clearly defines the agent's role and expertise
2. Provides specific instructions for the task domain
3. Explains how to use the available tools effectively
4. Includes personality traits and behavioral guidelines
5. Sets clear constraints and safety guidelines

Respond with the system prompt as markdown (no JSON wrapper).
"""

        try:
            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role='system',
                        content='You are an expert at designing AI agent system prompts. Generate clear, effective prompts.',
                    ),
                    LLMMessage(role='user', content=generation_prompt),
                ],
            )

            response = self._llm_adapter.generate(request)
            return response.content.strip()
        except Exception as exc:
            logger.warning(f'LLM prompt generation failed, falling back to template: {exc}')
            return self._generate_template_prompt(spec)

    def _persist_agent(self, agent: AgentPlugin) -> None:
        """Persist agent to disk as a plugin.

        Args:
            agent: AgentPlugin to persist.
        """
        agent_dir = self._user_plugin_dir / agent.name
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Create plugin.json manifest
        manifest = {
            'name': agent.name,
            'version': '1.0.0',
            'type': 'agent',
            'description': agent.description,
            'author': 'agent-factory',
            'license': 'MIT',
        }

        manifest_path = agent_dir / 'plugin.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        # Create agent.py with the plugin
        agent_code = f'''"""Dynamic agent: {agent.name}"""

from teaagent.plugin_system import AgentPlugin

def register(registry):
    """Register this agent with the plugin registry."""
    registry.register_agent(
        AgentPlugin(
            name="{agent.name}",
            description="{agent.description}",
            system_prompt="""{agent.system_prompt}""",
            tools={list(agent.tools)},
        )
    )
'''

        agent_path = agent_dir / 'agent.py'
        with open(agent_path, 'w', encoding='utf-8') as f:
            f.write(agent_code)

        logger.info(f'Persisted agent to disk: {agent_dir}')

    def hot_reload_agent(
        self, agent_name: str, new_system_prompt: str
    ) -> AgentPlugin:
        """Hot-reload an agent with a new system prompt (polish mode).

        Args:
            agent_name: Name of the agent to reload.
            new_system_prompt: New system prompt to use.

        Returns:
            Updated AgentPlugin instance.
        """
        existing = self._plugin_registry.get_agent(agent_name)
        if not existing:
            raise ValueError(f'Agent not found: {agent_name}')

        # Create updated agent
        updated = AgentPlugin(
            name=existing.name,
            description=existing.description,
            system_prompt=new_system_prompt,
            tools=existing.tools,
            model=existing.model,
        )

        # Re-register (overwrites existing)
        self._plugin_registry.register_agent(updated)

        # Update disk if persisted
        if self._persist_to_disk:
            self._persist_agent(updated)

        logger.info(f'Hot-reloaded agent: {agent_name}')
        return updated

    def list_dynamic_agents(self) -> list[str]:
        """List all dynamically generated agents.

        Returns:
            List of agent names that were generated by this factory.
        """
        # This is a simple implementation - in production, track factory-generated agents
        all_agents = self._plugin_registry.list_agents()
        return [agent.name for agent in all_agents]

    def remove_agent(self, agent_name: str) -> None:
        """Remove a dynamically generated agent.

        Args:
            agent_name: Name of the agent to remove.
        """
        # Remove from memory (PluginRegistry doesn't have remove, so we'd need to add it)
        # For now, this is a placeholder
        logger.warning(f'Agent removal not fully implemented: {agent_name}')

        # Remove from disk if persisted
        if self._persist_to_disk:
            agent_dir = self._user_plugin_dir / agent_name
            if agent_dir.exists():
                import shutil

                shutil.rmtree(agent_dir)
                logger.info(f'Removed agent from disk: {agent_dir}')
