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
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from teaagent.llm import LLMAdapter, LLMMessage, LLMRequest
from teaagent.plugin_system import _USER_PLUGIN_DIR, AgentPlugin, PluginRegistry

from ._prompt_assets import load_prompt_template

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


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically using temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except (OSError, IOError):
        with suppress(OSError):
            os.unlink(tmp_path)
        raise


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

        logger.info('Generated dynamic agent: %s', spec.name)
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
        personality = (
            ', '.join(spec.personality_traits)
            if spec.personality_traits
            else 'professional'
        )
        constraints = (
            '\n'.join(f'- {c}' for c in spec.constraints) if spec.constraints else ''
        )

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
        try:
            if self._llm_adapter is None:
                raise RuntimeError('LLM adapter is not configured')
            generation_prompt = load_prompt_template(
                'agent-prompt-authoring', 'generation_prompt.md'
            ).format(
                name=spec.name,
                description=spec.description,
                task_domain=spec.task_domain,
                specialization_level=spec.specialization_level,
                required_tools=', '.join(spec.required_tools),
                personality_traits=', '.join(spec.personality_traits)
                if spec.personality_traits
                else 'professional',
                constraints=', '.join(spec.constraints) if spec.constraints else 'none',
            )
            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role='system',
                        content='You are an expert at designing AI agent system prompts. Generate clear, effective prompts.',
                    ),
                    LLMMessage(role='user', content=generation_prompt),
                ],
            )

            response = self._llm_adapter.complete(request)
            return response.content.strip()
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            ConnectionError,
            TimeoutError,
        ) as exc:
            logger.warning(
                'LLM prompt generation failed, falling back to template: %s',
                exc,
            )
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

        _atomic_write(
            agent_dir / 'plugin.json',
            json.dumps(manifest, indent=2),
        )

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

        _atomic_write(agent_dir / 'agent.py', agent_code)

        logger.info('Persisted agent to disk: %s', agent_dir)

    def hot_reload_agent(self, agent_name: str, new_system_prompt: str) -> AgentPlugin:
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

        logger.info('Hot-reloaded agent: %s', agent_name)
        return updated

    def list_dynamic_agents(self) -> list[str]:
        """List all dynamically generated agents.

        Returns:
            List of agent names that were generated by this factory.
        """
        # This is a simple implementation - in production, track factory-generated agents
        all_agents = self._plugin_registry.list_agents()
        return [agent.name for agent in all_agents]

    def evolve_agent_prompt(
        self,
        agent_name: str,
        performance_feedback: str,
        success_metrics: dict[str, float],
    ) -> AgentPlugin:
        """Evolve an agent's prompt based on performance feedback.

        Args:
            agent_name: Name of the agent to evolve.
            performance_feedback: Feedback on agent performance.
            success_metrics: Dictionary of success metrics (accuracy, speed, etc.).

        Returns:
            Evolved AgentPlugin instance.
        """
        existing = self._plugin_registry.get_agent(agent_name)
        if not existing:
            raise ValueError(f'Agent not found: {agent_name}')

        # Generate evolution prompt
        evolution_prompt = self._generate_evolution_prompt(
            existing.system_prompt, performance_feedback, success_metrics
        )

        # Apply evolved prompt
        return self.hot_reload_agent(agent_name, evolution_prompt)

    def _generate_evolution_prompt(
        self,
        current_prompt: str,
        performance_feedback: str,
        success_metrics: dict[str, float],
    ) -> str:
        """Generate an evolved prompt based on performance feedback.

        Args:
            current_prompt: Current system prompt.
            performance_feedback: Feedback on performance.
            success_metrics: Success metrics dictionary.

        Returns:
            Evolved system prompt.
        """
        if self._llm_adapter is None:
            # Simple heuristic evolution
            return self._heuristic_evolve_prompt(
                current_prompt, performance_feedback, success_metrics
            )

        return self._llm_evolve_prompt(
            current_prompt, performance_feedback, success_metrics
        )

    def _heuristic_evolve_prompt(
        self,
        current_prompt: str,
        performance_feedback: str,
        success_metrics: dict[str, float],
    ) -> str:
        """Heuristic prompt evolution without LLM."""
        # Add performance feedback section
        evolution_section = f"""

## Performance Feedback
{performance_feedback}

## Success Metrics
{', '.join(f'{k}: {v}' for k, v in success_metrics.items())}

## Evolution Instructions
Based on the feedback above, adjust your approach to improve performance.
Focus on areas with low success metrics.
"""

        return current_prompt + evolution_section

    def _llm_evolve_prompt(
        self,
        current_prompt: str,
        performance_feedback: str,
        success_metrics: dict[str, float],
    ) -> str:
        """LLM-based prompt evolution."""
        try:
            if self._llm_adapter is None:
                raise RuntimeError('LLM adapter is not configured')
            evolution_prompt = load_prompt_template(
                'agent-prompt-authoring', 'evolution_prompt.md'
            ).format(
                current_prompt=current_prompt,
                performance_feedback=performance_feedback,
                success_metrics=', '.join(
                    f'{k}: {v}' for k, v in success_metrics.items()
                ),
            )
            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role='system',
                        content='You are an expert at evolving AI agent prompts based on performance feedback.',
                    ),
                    LLMMessage(role='user', content=evolution_prompt),
                ],
            )

            response = self._llm_adapter.complete(request)
            return response.content.strip()
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            ConnectionError,
            TimeoutError,
        ) as exc:
            logger.warning(
                'LLM prompt evolution failed, falling back to heuristic: %s',
                exc,
            )
            return self._heuristic_evolve_prompt(
                current_prompt, performance_feedback, success_metrics
            )

    def remove_agent(self, agent_name: str) -> None:
        """Remove a dynamically generated agent.

        Args:
            agent_name: Name of the agent to remove.
        """
        # Remove from memory (PluginRegistry doesn't have remove, so we'd need to add it)
        # For now, this is a placeholder
        logger.warning('Agent removal not fully implemented: %s', agent_name)

        # Remove from disk if persisted
        if self._persist_to_disk:
            agent_dir = self._user_plugin_dir / agent_name
            if agent_dir.exists():
                import shutil

                shutil.rmtree(agent_dir)
                logger.info('Removed agent from disk: %s', agent_dir)
