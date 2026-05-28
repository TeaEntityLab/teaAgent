"""Task Coordinator - Classifies and routes tasks to specialized agents.

This module implements the Cooragent coordination layer that:
1. Classifies incoming tasks by type and complexity
2. Routes tasks to appropriate specialized agents
3. Generates structured step plans for multi-step workflows
4. Manages agent lifecycle and task delegation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from teaagent.llm import LLMAdapter, LLMMessage, LLMRequest
from teaagent.plugin_system import PluginRegistry

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task classification types."""

    CODE_REVIEW = 'code_review'
    TESTING = 'testing'
    DOCUMENTATION = 'documentation'
    REFACTORING = 'refactoring'
    DEBUGGING = 'debugging'
    FEATURE_IMPLEMENTATION = 'feature_implementation'
    GENERAL = 'general'


class TaskComplexity(Enum):
    """Task complexity levels."""

    SIMPLE = 'simple'
    MODERATE = 'moderate'
    COMPLEX = 'complex'


@dataclass
class TaskClassification:
    """Result of task classification."""

    task_type: TaskType
    complexity: TaskComplexity
    confidence: float
    suggested_agent: Optional[str] = None
    requires_multi_step: bool = False
    estimated_steps: int = 1


@dataclass
class WorkflowStep:
    """A single step in a multi-step workflow."""

    step_id: int
    description: str
    agent_name: str
    tools: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[int, ...] = field(default_factory=tuple)


@dataclass
class WorkflowPlan:
    """Structured plan for multi-step task execution."""

    task_description: str
    classification: TaskClassification
    steps: list[WorkflowStep]
    estimated_duration_seconds: int = 0


class TaskCoordinator:
    """Coordinates task classification, routing, and workflow planning."""

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        llm_adapter: Optional[LLMAdapter] = None,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._llm_adapter = llm_adapter
        self._default_agent = 'general'

    def classify_task(self, task_description: str) -> TaskClassification:
        """Classify a task by type and complexity.

        Args:
            task_description: The task description to classify.

        Returns:
            TaskClassification with type, complexity, and routing suggestions.
        """
        if self._llm_adapter is None:
            return self._classify_task_heuristic(task_description)

        return self._classify_task_with_llm(task_description)

    def _classify_task_heuristic(self, task_description: str) -> TaskClassification:
        """Classify task using heuristic rules (no LLM)."""
        description_lower = task_description.lower()

        # Simple keyword-based classification
        if 'review' in description_lower or 'audit' in description_lower:
            return TaskClassification(
                task_type=TaskType.CODE_REVIEW,
                complexity=TaskComplexity.MODERATE,
                confidence=0.7,
                suggested_agent='code-reviewer',
            )
        elif 'test' in description_lower or 'spec' in description_lower:
            return TaskClassification(
                task_type=TaskType.TESTING,
                complexity=TaskComplexity.MODERATE,
                confidence=0.7,
                suggested_agent='tester',
            )
        elif 'doc' in description_lower or 'readme' in description_lower:
            return TaskClassification(
                task_type=TaskType.DOCUMENTATION,
                complexity=TaskComplexity.SIMPLE,
                confidence=0.7,
                suggested_agent='docs-writer',
            )
        elif 'refactor' in description_lower or 'clean' in description_lower:
            return TaskClassification(
                task_type=TaskType.REFACTORING,
                complexity=TaskComplexity.COMPLEX,
                confidence=0.6,
                requires_multi_step=True,
                estimated_steps=3,
            )
        elif 'bug' in description_lower or 'fix' in description_lower:
            return TaskClassification(
                task_type=TaskType.DEBUGGING,
                complexity=TaskComplexity.MODERATE,
                confidence=0.6,
                requires_multi_step=True,
                estimated_steps=2,
            )
        elif 'implement' in description_lower or 'add' in description_lower:
            return TaskClassification(
                task_type=TaskType.FEATURE_IMPLEMENTATION,
                complexity=TaskComplexity.COMPLEX,
                confidence=0.5,
                requires_multi_step=True,
                estimated_steps=4,
            )
        else:
            return TaskClassification(
                task_type=TaskType.GENERAL,
                complexity=TaskComplexity.SIMPLE,
                confidence=0.4,
                suggested_agent=self._default_agent,
            )

    def _classify_task_with_llm(self, task_description: str) -> TaskClassification:
        """Classify task using LLM for better accuracy."""
        classification_prompt = f"""Classify the following task by type and complexity.

Task: {task_description}

Respond with JSON:
{{
    "task_type": "code_review|testing|documentation|refactoring|debugging|feature_implementation|general",
    "complexity": "simple|moderate|complex",
    "confidence": 0.0-1.0,
    "suggested_agent": "agent_name_or_null",
    "requires_multi_step": true|false,
    "estimated_steps": integer
}}
"""

        try:
            if self._llm_adapter is None:
                raise RuntimeError('LLM adapter is not configured')
            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role='system',
                        content='You are a task classification expert. Respond only with valid JSON.',
                    ),
                    LLMMessage(role='user', content=classification_prompt),
                ],
                response_format={'type': 'json_object'},
            )

            response = self._llm_adapter.complete(request)
            import json

            data = json.loads(response.content)

            return TaskClassification(
                task_type=TaskType(data['task_type']),
                complexity=TaskComplexity(data['complexity']),
                confidence=data['confidence'],
                suggested_agent=data.get('suggested_agent'),
                requires_multi_step=data.get('requires_multi_step', False),
                estimated_steps=data.get('estimated_steps', 1),
            )
        except Exception as exc:
            logger.warning(
                f'LLM classification failed, falling back to heuristic: {exc}'
            )
            return self._classify_task_heuristic(task_description)

    def generate_workflow_plan(
        self, task_description: str, classification: TaskClassification
    ) -> WorkflowPlan:
        """Generate a structured workflow plan for a task.

        Args:
            task_description: The task to plan.
            classification: Task classification result.

        Returns:
            WorkflowPlan with structured steps.
        """
        if not classification.requires_multi_step:
            # Single-step workflow
            agent_name = classification.suggested_agent or self._default_agent
            agent = self._plugin_registry.get_agent(agent_name)

            return WorkflowPlan(
                task_description=task_description,
                classification=classification,
                steps=[
                    WorkflowStep(
                        step_id=1,
                        description=task_description,
                        agent_name=agent_name,
                        tools=agent.tools if agent else (),
                    )
                ],
                estimated_duration_seconds=60,
            )

        # Multi-step workflow - use LLM for planning if available
        if self._llm_adapter:
            return self._generate_llm_workflow_plan(task_description, classification)

        # Fallback to heuristic multi-step planning
        return self._generate_heuristic_workflow_plan(task_description, classification)

    def _generate_heuristic_workflow_plan(
        self, task_description: str, classification: TaskClassification
    ) -> WorkflowPlan:
        """Generate workflow plan using heuristic rules."""
        steps: list[WorkflowStep] = []

        if classification.task_type == TaskType.REFACTORING:
            steps = [
                WorkflowStep(
                    step_id=1,
                    description='Analyze current code structure',
                    agent_name='code-reviewer',
                    tools=('workspace_read_file', 'grep'),
                ),
                WorkflowStep(
                    step_id=2,
                    description='Plan refactoring approach',
                    agent_name='code-reviewer',
                    tools=('workspace_read_file',),
                    dependencies=(1,),
                ),
                WorkflowStep(
                    step_id=3,
                    description='Execute refactoring',
                    agent_name='general',
                    tools=('workspace_write_file', 'shell'),
                    dependencies=(2,),
                ),
            ]
        elif classification.task_type == TaskType.DEBUGGING:
            steps = [
                WorkflowStep(
                    step_id=1,
                    description='Analyze error and locate bug',
                    agent_name='code-reviewer',
                    tools=('workspace_read_file', 'grep', 'shell'),
                ),
                WorkflowStep(
                    step_id=2,
                    description='Fix the bug',
                    agent_name='general',
                    tools=('workspace_write_file', 'shell'),
                    dependencies=(1,),
                ),
            ]
        elif classification.task_type == TaskType.FEATURE_IMPLEMENTATION:
            steps = [
                WorkflowStep(
                    step_id=1,
                    description='Understand requirements and existing code',
                    agent_name='code-reviewer',
                    tools=('workspace_read_file', 'grep'),
                ),
                WorkflowStep(
                    step_id=2,
                    description='Design implementation approach',
                    agent_name='code-reviewer',
                    tools=('workspace_read_file',),
                    dependencies=(1,),
                ),
                WorkflowStep(
                    step_id=3,
                    description='Implement the feature',
                    agent_name='general',
                    tools=('workspace_write_file', 'shell'),
                    dependencies=(2,),
                ),
                WorkflowStep(
                    step_id=4,
                    description='Write tests',
                    agent_name='tester',
                    tools=('workspace_read_file', 'workspace_write_file', 'shell'),
                    dependencies=(3,),
                ),
            ]
        else:
            # Generic multi-step plan
            for i in range(classification.estimated_steps):
                agent_name = classification.suggested_agent or self._default_agent
                agent = self._plugin_registry.get_agent(agent_name)
                steps.append(
                    WorkflowStep(
                        step_id=i + 1,
                        description=f'Step {i + 1}: {task_description}',
                        agent_name=agent_name,
                        tools=agent.tools if agent else (),
                        dependencies=(i,) if i > 0 else (),
                    )
                )

        return WorkflowPlan(
            task_description=task_description,
            classification=classification,
            steps=steps,
            estimated_duration_seconds=len(steps) * 120,
        )

    def _generate_llm_workflow_plan(
        self, task_description: str, classification: TaskClassification
    ) -> WorkflowPlan:
        """Generate workflow plan using LLM for better planning."""
        available_agents = [agent.name for agent in self._plugin_registry.list_agents()]

        planning_prompt = f"""Generate a structured workflow plan for the following task.

Task: {task_description}
Task Type: {classification.task_type.value}
Complexity: {classification.complexity.value}
Estimated Steps: {classification.estimated_steps}

Available Agents: {', '.join(available_agents)}

Respond with JSON:
{{
    "steps": [
        {{
            "step_id": 1,
            "description": "Step description",
            "agent_name": "agent_name",
            "tools": ["tool1", "tool2"],
            "dependencies": []
        }}
    ],
    "estimated_duration_seconds": integer
}}
"""

        try:
            if self._llm_adapter is None:
                raise RuntimeError('LLM adapter is not configured')
            request = LLMRequest(
                messages=[
                    LLMMessage(
                        role='system',
                        content='You are a workflow planning expert. Respond only with valid JSON.',
                    ),
                    LLMMessage(role='user', content=planning_prompt),
                ],
                response_format={'type': 'json_object'},
            )

            response = self._llm_adapter.complete(request)
            import json

            data = json.loads(response.content)

            steps = [
                WorkflowStep(
                    step_id=step['step_id'],
                    description=step['description'],
                    agent_name=step['agent_name'],
                    tools=tuple(step.get('tools', [])),
                    dependencies=tuple(step.get('dependencies', [])),
                )
                for step in data['steps']
            ]

            return WorkflowPlan(
                task_description=task_description,
                classification=classification,
                steps=steps,
                estimated_duration_seconds=data.get('estimated_duration_seconds', 300),
            )
        except Exception as exc:
            logger.warning(
                f'LLM workflow planning failed, falling back to heuristic: {exc}'
            )
            return self._generate_heuristic_workflow_plan(
                task_description, classification
            )

    def route_task(
        self, task_description: str
    ) -> tuple[TaskClassification, WorkflowPlan]:
        """Classify task and generate workflow plan in one call.

        Args:
            task_description: The task to route.

        Returns:
            Tuple of (TaskClassification, WorkflowPlan).
        """
        classification = self.classify_task(task_description)
        workflow_plan = self.generate_workflow_plan(task_description, classification)
        return classification, workflow_plan
