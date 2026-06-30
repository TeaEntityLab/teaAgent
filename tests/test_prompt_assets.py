"""Behavior-preservation tests for skill-owned LLM prompt assets (ADR-0041 Phase 2).

The substantive LLM prompts for ``teaagent.domain.coordinator`` and
``teaagent.domain.agent_factory`` were moved out of inline Python into reviewed
skill assets under ``teaagent/skills/builtin/``. These tests lock that move as
byte-identical to the prior inline prompts: both the standalone template render
and the full wired path (driven through a recording adapter) must reproduce the
exact prompt text captured before the refactor.
"""

from __future__ import annotations

from typing import Any

import pytest

from teaagent.domain import agent_factory as AF
from teaagent.domain import coordinator as C
from teaagent.domain._prompt_assets import PromptAssetError, load_prompt_template
from teaagent.llm._types import LLMResponse
from teaagent.plugin_system import PluginRegistry

# Exact prompts rendered by the pre-refactor inline f-strings, for the inputs
# used below. Any drift in the skill assets or the wiring fails these tests.
EXPECTED = {
    'classification_system': 'You are a task classification expert. Respond only with valid JSON.',
    'classification_user': 'Classify the following task by type and complexity.\n'
    '\n'
    'Task: «TASK»\n'
    '\n'
    'Respond with JSON:\n'
    '{\n'
    '    "task_type": '
    '"code_review|testing|documentation|refactoring|debugging|feature_implementation|general",\n'
    '    "complexity": "simple|moderate|complex",\n'
    '    "confidence": 0.0-1.0,\n'
    '    "suggested_agent": "agent_name_or_null",\n'
    '    "requires_multi_step": true|false,\n'
    '    "estimated_steps": integer\n'
    '}\n',
    'planning_system': 'You are a workflow planning expert. Respond only with valid JSON.',
    'planning_user': 'Generate a structured workflow plan for the following task.\n'
    '\n'
    'Task: «TASK»\n'
    'Task Type: general\n'
    'Complexity: moderate\n'
    'Estimated Steps: 3\n'
    '\n'
    'Available Agents: \n'
    '\n'
    'Respond with JSON:\n'
    '{\n'
    '    "steps": [\n'
    '        {\n'
    '            "step_id": 1,\n'
    '            "description": "Step description",\n'
    '            "agent_name": "agent_name",\n'
    '            "tools": ["tool1", "tool2"],\n'
    '            "dependencies": []\n'
    '        }\n'
    '    ],\n'
    '    "estimated_duration_seconds": integer\n'
    '}\n',
    'generation_system': 'You are an expert at designing AI agent system prompts. '
    'Generate clear, effective prompts.',
    'generation_user': 'Generate a specialized system prompt for an AI agent.\n'
    '\n'
    'Agent Name: n\n'
    'Description: d\n'
    'Task Domain: «DOMAIN»\n'
    'Specialization Level: expert\n'
    'Required Tools: t1, t2\n'
    'Personality Traits: curious\n'
    'Constraints: safe\n'
    '\n'
    'Generate a comprehensive markdown system prompt that:\n'
    "1. Clearly defines the agent's role and expertise\n"
    '2. Provides specific instructions for the task domain\n'
    '3. Explains how to use the available tools effectively\n'
    '4. Includes personality traits and behavioral guidelines\n'
    '5. Sets clear constraints and safety guidelines\n'
    '\n'
    'Respond with the system prompt as markdown (no JSON wrapper).\n',
    'evolution_system': 'You are an expert at evolving AI agent prompts based on '
    'performance feedback.',
    'evolution_user': 'Evolve the following agent system prompt based on performance feedback.\n'
    '\n'
    'Current Prompt:\n'
    '«CURRENT»\n'
    '\n'
    'Performance Feedback:\n'
    '«FEEDBACK»\n'
    '\n'
    'Success Metrics:\n'
    'accuracy: 0.8\n'
    '\n'
    'Instructions:\n'
    '1. Analyze the performance feedback and success metrics.\n'
    '2. Identify areas where the agent underperforms.\n'
    '3. Refine the system prompt to address these weaknesses.\n'
    '4. Maintain the core purpose and constraints of the agent.\n'
    '5. Return the evolved system prompt as markdown.\n'
    '\n'
    'Respond with the evolved system prompt as markdown (no JSON wrapper).\n',
}


class _RecAdapter:
    """Records the requests it receives and returns a fixed response."""

    provider = 'fake'

    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[Any] = []

    def complete(self, request: object) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(provider='fake', model='m', content=self.content)


def test_template_render_classification_byte_identical() -> None:
    tmpl = load_prompt_template('task-classification', 'classification_prompt.md')
    assert tmpl.format(task_description='«TASK»') == EXPECTED['classification_user']


def test_template_render_planning_byte_identical() -> None:
    tmpl = load_prompt_template('task-classification', 'planning_prompt.md')
    rendered = tmpl.format(
        task_description='«TASK»',
        task_type='general',
        complexity='moderate',
        estimated_steps=3,
        available_agents='',
    )
    assert rendered == EXPECTED['planning_user']


def test_template_render_generation_byte_identical() -> None:
    tmpl = load_prompt_template('agent-prompt-authoring', 'generation_prompt.md')
    rendered = tmpl.format(
        name='n',
        description='d',
        task_domain='«DOMAIN»',
        specialization_level='expert',
        required_tools='t1, t2',
        personality_traits='curious',
        constraints='safe',
    )
    assert rendered == EXPECTED['generation_user']


def test_template_render_evolution_byte_identical() -> None:
    tmpl = load_prompt_template('agent-prompt-authoring', 'evolution_prompt.md')
    rendered = tmpl.format(
        current_prompt='«CURRENT»',
        performance_feedback='«FEEDBACK»',
        success_metrics='accuracy: 0.8',
    )
    assert rendered == EXPECTED['evolution_user']


def test_wired_classification_prompt_byte_identical() -> None:
    adapter = _RecAdapter(
        '{"task_type": "general", "complexity": "simple", "confidence": 0.5}'
    )
    C.TaskCoordinator(PluginRegistry(), llm_adapter=adapter)._classify_task_with_llm(
        '«TASK»'
    )
    msgs = adapter.requests[0].messages
    assert msgs[0].content == EXPECTED['classification_system']
    assert msgs[1].content == EXPECTED['classification_user']


def test_wired_planning_prompt_byte_identical() -> None:
    adapter = _RecAdapter(
        '{"steps": [{"step_id": 1, "description": "d", "agent_name": "general", '
        '"tools": [], "dependencies": []}], "estimated_duration_seconds": 60}'
    )
    clsf = C.TaskClassification(
        task_type=C.TaskType.GENERAL,
        complexity=C.TaskComplexity.MODERATE,
        confidence=0.5,
        requires_multi_step=True,
        estimated_steps=3,
    )
    C.TaskCoordinator(
        PluginRegistry(), llm_adapter=adapter
    )._generate_llm_workflow_plan('«TASK»', clsf)
    msgs = adapter.requests[0].messages
    assert msgs[0].content == EXPECTED['planning_system']
    assert msgs[1].content == EXPECTED['planning_user']


def test_wired_generation_prompt_byte_identical() -> None:
    adapter = _RecAdapter('SYSTEM PROMPT MD')
    spec = AF.AgentSpecification(
        name='n',
        description='d',
        task_domain='«DOMAIN»',
        required_tools=('t1', 't2'),
        specialization_level='expert',
        personality_traits=('curious',),
        constraints=('safe',),
    )
    AF.AgentFactory(PluginRegistry(), llm_adapter=adapter)._generate_llm_prompt(spec)
    msgs = adapter.requests[0].messages
    assert msgs[0].content == EXPECTED['generation_system']
    assert msgs[1].content == EXPECTED['generation_user']


def test_wired_evolution_prompt_byte_identical() -> None:
    adapter = _RecAdapter('EVOLVED MD')
    AF.AgentFactory(PluginRegistry(), llm_adapter=adapter)._llm_evolve_prompt(
        '«CURRENT»', '«FEEDBACK»', {'accuracy': 0.8}
    )
    msgs = adapter.requests[0].messages
    assert msgs[0].content == EXPECTED['evolution_system']
    assert msgs[1].content == EXPECTED['evolution_user']


def test_missing_asset_raises_prompt_asset_error() -> None:
    with pytest.raises(PromptAssetError):
        load_prompt_template('nonexistent-skill', 'nope.md')


@pytest.mark.parametrize(
    'skill',
    [
        'task-classification',
        'agent-prompt-authoring',
        'intent-clarification',
        'workflow-orchestration',
        'issue-intake',
    ],
)
def test_skill_doc_present(skill: str) -> None:
    text = load_prompt_template(skill, 'SKILL.md')
    assert text.startswith('---')
    assert f'name: {skill}' in text
