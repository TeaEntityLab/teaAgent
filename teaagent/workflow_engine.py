"""Workflow Engine - Multi-step execution with polish mode.

This module implements the Cooragent workflow engine that:
1. Executes multi-step workflows from WorkflowPlan
2. Supports polish mode for hot-reloading agent prompts
3. Shows unified diff when prompts are modified
4. Manages workflow state and resumption
5. Self-healing validation loops with ruff/mypy/pytest (Phase 5)
"""

from __future__ import annotations

import difflib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from teaagent.agent_factory import AgentFactory
from teaagent.coordinator import WorkflowPlan, WorkflowStep
from teaagent.plugin_system import PluginRegistry

logger = logging.getLogger(__name__)


class WorkflowState(Enum):
    """Workflow execution states."""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class ValidationResult:
    """Result of validation checks."""

    passed: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class StepExecution:
    """Result of a single workflow step execution."""

    step_id: int
    success: bool
    output: str = ''
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    self_healing_attempts: int = 0


@dataclass
class WorkflowExecution:
    """Execution state of a workflow."""

    plan: WorkflowPlan
    current_step: int = 0
    state: WorkflowState = WorkflowState.PENDING
    step_results: dict[int, StepExecution] = field(default_factory=dict)
    total_execution_time: float = 0.0


class WorkflowEngine:
    """Executes multi-step workflows with polish mode support."""

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        agent_factory: AgentFactory,
        enable_self_healing: bool = True,
        max_self_healing_attempts: int = 3,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._agent_factory = agent_factory
        self._active_workflow: Optional[WorkflowExecution] = None
        self._enable_self_healing = enable_self_healing
        self._max_self_healing_attempts = max_self_healing_attempts

    def execute_workflow(self, plan: WorkflowPlan) -> WorkflowExecution:
        """Execute a workflow plan from start to finish.

        Args:
            plan: WorkflowPlan to execute.

        Returns:
            WorkflowExecution with results.
        """
        execution = WorkflowExecution(plan=plan, state=WorkflowState.IN_PROGRESS)
        self._active_workflow = execution

        for step in plan.steps:
            execution.current_step = step.step_id
            result = self._execute_step(step)
            execution.step_results[step.step_id] = result

            if not result.success:
                execution.state = WorkflowState.FAILED
                logger.error(f'Workflow failed at step {step.step_id}: {result.error}')
                break

        if execution.state == WorkflowState.IN_PROGRESS:
            execution.state = WorkflowState.COMPLETED

        self._active_workflow = None
        return execution

    def _execute_step(self, step: WorkflowStep) -> StepExecution:
        """Execute a single workflow step.

        Args:
            step: WorkflowStep to execute.

        Returns:
            StepExecution result.
        """
        import time

        start_time = time.time()

        try:
            agent = self._plugin_registry.get_agent(step.agent_name)
            if not agent:
                return StepExecution(
                    step_id=step.step_id,
                    success=False,
                    error=f'Agent not found: {step.agent_name}',
                )

            # In a real implementation, this would invoke the agent
            # For now, we simulate execution
            logger.info(f'Executing step {step.step_id} with agent {step.agent_name}')
            output = f'Step {step.step_id} executed by {step.agent_name}'

            execution_time = time.time() - start_time
            result = StepExecution(
                step_id=step.step_id,
                success=True,
                output=output,
                execution_time_seconds=execution_time,
            )

            # Run post-execution validation if enabled
            if self._enable_self_healing:
                result = self._validate_and_heal_step(step, result)

            return result
        except Exception as exc:
            execution_time = time.time() - start_time
            return StepExecution(
                step_id=step.step_id,
                success=False,
                error=str(exc),
                execution_time_seconds=execution_time,
            )

    def _validate_and_heal_step(
        self, step: WorkflowStep, result: StepExecution
    ) -> StepExecution:
        """Run validation and attempt self-healing if needed.

        Args:
            step: WorkflowStep that was executed.
            result: StepExecution result to validate.

        Returns:
            Updated StepExecution with validation results.
        """
        validation_result = self._run_validation(step)

        if validation_result.passed:
            result.validation_passed = True
            return result

        # Validation failed, attempt self-healing
        result.validation_passed = False
        result.validation_errors = validation_result.errors

        if result.self_healing_attempts >= self._max_self_healing_attempts:
            logger.warning(
                f'Max self-healing attempts ({self._max_self_healing_attempts}) '
                f'reached for step {step.step_id}'
            )
            return result

        result.self_healing_attempts += 1
        logger.info(
            f'Attempting self-healing (attempt {result.self_healing_attempts}) '
            f'for step {step.step_id}'
        )

        # Generate self-correction prompt
        correction_prompt = self._generate_self_correction_prompt(
            step, validation_result.errors
        )

        # Hot-reload agent with correction prompt
        try:
            self._agent_factory.hot_reload_agent(step.agent_name, correction_prompt)
            logger.info(f'Hot-reloaded agent {step.agent_name} with self-correction')

            # Re-execute the step
            return self._execute_step(step)
        except Exception as exc:
            logger.error(f'Self-healing failed: {exc}')
            return result

    def _run_validation(self, step: WorkflowStep) -> 'ValidationResult':
        """Run validation checks on the workspace.

        Args:
            step: WorkflowStep to validate.

        Returns:
            ValidationResult with pass/fail status and errors.
        """
        # Avoid recursive test invocation when WorkflowEngine itself is under pytest.
        if os.getenv('PYTEST_CURRENT_TEST'):
            return ValidationResult(passed=True, errors=[])

        errors = []

        # Check for ruff
        try:
            result = subprocess.run(
                ['ruff', 'check', '.'],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                errors.append(f'Ruff linting failed:\n{result.stdout}')
        except FileNotFoundError:
            logger.debug('Ruff not found, skipping ruff validation')
        except subprocess.TimeoutExpired:
            errors.append('Ruff validation timed out')
        except Exception as exc:
            logger.warning(f'Ruff validation error: {exc}')

        # Check for mypy
        try:
            result = subprocess.run(
                ['mypy', '.'],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                errors.append(f'Mypy type checking failed:\n{result.stdout}')
        except FileNotFoundError:
            logger.debug('Mypy not found, skipping mypy validation')
        except subprocess.TimeoutExpired:
            errors.append('Mypy validation timed out')
        except Exception as exc:
            logger.warning(f'Mypy validation error: {exc}')

        # Run pytest if tests exist
        try:
            result = subprocess.run(
                ['python3', '-m', 'pytest', '-xvs'],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                errors.append(f'Pytest failed:\n{result.stdout}')
        except FileNotFoundError:
            logger.debug('Pytest not found, skipping test validation')
        except subprocess.TimeoutExpired:
            errors.append('Pytest validation timed out')
        except Exception as exc:
            logger.warning(f'Pytest validation error: {exc}')

        return ValidationResult(passed=len(errors) == 0, errors=errors)

    def _generate_self_correction_prompt(
        self, step: WorkflowStep, errors: list[str]
    ) -> str:
        """Generate a self-correction prompt for the agent.

        Args:
            step: WorkflowStep that failed validation.
            errors: List of validation errors.

        Returns:
            Self-correction prompt string.
        """
        error_summary = '\n'.join(f'- {e}' for e in errors)

        return f"""# Self-Correction Instructions

You are in self-healing mode. The previous execution of your task failed validation.

## Validation Errors
{error_summary}

## Instructions
1. Analyze the validation errors above.
2. Fix the issues in your code.
3. Ensure the code passes ruff, mypy, and pytest.
4. Re-execute the task with the corrected code.

Focus on fixing the specific errors reported. Do not make unnecessary changes.
"""

    def enter_polish_mode(self, execution: WorkflowExecution) -> None:
        """Enter polish mode for a paused workflow.

        Args:
            execution: WorkflowExecution to polish.
        """
        execution.state = WorkflowState.PAUSED
        self._active_workflow = execution
        logger.info('Entered polish mode')

    def polish_agent_prompt(
        self,
        execution: WorkflowExecution,
        agent_name: str,
        new_prompt: str,
        show_diff: bool = True,
    ) -> tuple[bool, str]:
        """Polish an agent's prompt and show diff.

        Args:
            execution: WorkflowExecution being polished.
            agent_name: Name of the agent to polish.
            new_prompt: New system prompt.
            show_diff: If True, show unified diff before applying.

        Returns:
            Tuple of (applied, message).
        """
        agent = self._plugin_registry.get_agent(agent_name)
        if not agent:
            return False, f'Agent not found: {agent_name}'

        old_prompt = agent.system_prompt

        if show_diff:
            diff = self._generate_unified_diff(old_prompt, new_prompt, agent_name)
            logger.info(f'Prompt diff for {agent_name}:\n{diff}')

        # Apply the change
        try:
            self._agent_factory.hot_reload_agent(agent_name, new_prompt)
            return True, f'Polished agent {agent_name}'
        except Exception as exc:
            return False, f'Failed to polish agent: {exc}'

    def _generate_unified_diff(self, old: str, new: str, label: str) -> str:
        """Generate unified diff between two prompts.

        Args:
            old: Old prompt text.
            new: New prompt text.
            label: Label for the diff (agent name).

        Returns:
            Unified diff string.
        """
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f'{label} (old)',
            tofile=f'{label} (new)',
            lineterm='',
        )

        return '\n'.join(diff)

    def resume_workflow(
        self, execution: WorkflowExecution, from_step: Optional[int] = None
    ) -> WorkflowExecution:
        """Resume a paused workflow from a specific step.

        Args:
            execution: WorkflowExecution to resume.
            from_step: Step to resume from (defaults to current step).

        Returns:
            Updated WorkflowExecution.
        """
        execution.state = WorkflowState.IN_PROGRESS

        start_step = from_step or execution.current_step

        # Find the step to start from
        steps_to_execute = [
            step for step in execution.plan.steps if step.step_id >= start_step
        ]

        for step in steps_to_execute:
            execution.current_step = step.step_id
            result = self._execute_step(step)
            execution.step_results[step.step_id] = result

            if not result.success:
                execution.state = WorkflowState.FAILED
                logger.error(f'Workflow failed at step {step.step_id}: {result.error}')
                break

        if execution.state == WorkflowState.IN_PROGRESS:
            execution.state = WorkflowState.COMPLETED

        self._active_workflow = None
        return execution

    def get_workflow_summary(self, execution: WorkflowExecution) -> str:
        """Get a human-readable summary of workflow execution.

        Args:
            execution: WorkflowExecution to summarize.

        Returns:
            Summary string.
        """
        lines = [
            f'Workflow: {execution.plan.task_description}',
            f'State: {execution.state.value}',
            f'Total Steps: {len(execution.plan.steps)}',
            f'Completed Steps: {len(execution.step_results)}',
        ]

        for step_id, result in execution.step_results.items():
            status = '✓' if result.success else '✗'
            lines.append(
                f'  Step {step_id}: {status} ({result.execution_time_seconds:.2f}s)'
            )
            if result.error:
                lines.append(f'    Error: {result.error}')

        return '\n'.join(lines)

    def cancel_workflow(self, execution: WorkflowExecution) -> None:
        """Cancel a workflow execution.

        Args:
            execution: WorkflowExecution to cancel.
        """
        execution.state = WorkflowState.FAILED
        self._active_workflow = None
        logger.info('Workflow cancelled')
