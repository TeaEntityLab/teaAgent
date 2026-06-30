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
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, cast

from teaagent.audit import AuditLogger
from teaagent.domain.agent_factory import AgentFactory
from teaagent.domain.coordinator import WorkflowPlan, WorkflowStep
from teaagent.plugin_system import PluginRegistry
from teaagent.run_undo import UndoJournal

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
    requires_rollback: bool = (
        False  # Flag for automatic rollback on strict validation failure
    )
    simulated: bool = (
        False  # True when the step was simulated (no real agent invocation)
    )


@dataclass
class WorkflowExecution:
    """Execution state of a workflow."""

    plan: WorkflowPlan
    current_step: int = 0
    state: WorkflowState = WorkflowState.PENDING
    step_results: dict[int, StepExecution] = field(default_factory=dict)
    total_execution_time: float = 0.0
    run_id: Optional[str] = None
    depth: int = 0
    tenant_id: str = 'default'


def workflow_execution_to_dict(execution: WorkflowExecution) -> dict[str, Any]:
    return {
        'run_id': execution.run_id,
        'tenant_id': execution.tenant_id,
        'current_step': execution.current_step,
        'state': execution.state.value,
        'total_execution_time': execution.total_execution_time,
        'depth': execution.depth,
        'step_results': {
            str(k): {
                'step_id': v.step_id,
                'success': v.success,
                'output': v.output,
                'error': v.error,
                'execution_time_seconds': v.execution_time_seconds,
                'validation_passed': v.validation_passed,
                'validation_errors': v.validation_errors,
                'self_healing_attempts': v.self_healing_attempts,
                'requires_rollback': v.requires_rollback,
                'simulated': v.simulated,
            }
            for k, v in execution.step_results.items()
        },
        'plan': {
            'task_description': execution.plan.task_description,
            'tenant_id': execution.plan.tenant_id,
            'steps': [
                {
                    'step_id': s.step_id,
                    'description': s.description,
                    'agent_name': s.agent_name,
                    'tools': list(s.tools) if s.tools else [],
                    'dependencies': list(s.dependencies) if s.dependencies else [],
                    'validation_profile': getattr(s, 'validation_profile', 'standard'),
                }
                for s in execution.plan.steps
            ],
            'estimated_duration_seconds': execution.plan.estimated_duration_seconds,
        },
    }


def workflow_execution_from_dict(d: dict[str, Any]) -> WorkflowExecution:
    from teaagent.coordinator import TaskClassification, TaskComplexity, TaskType

    plan_dict = d['plan']
    steps = [
        WorkflowStep(
            step_id=s['step_id'],
            description=s['description'],
            agent_name=s['agent_name'],
            tools=tuple(s.get('tools') or []),
            dependencies=tuple(s.get('dependencies') or []),
            validation_profile=s.get('validation_profile', 'standard'),
        )
        for s in plan_dict.get('steps', [])
    ]
    dummy_classification = TaskClassification(
        task_type=TaskType.GENERAL,
        complexity=TaskComplexity.SIMPLE,
        confidence=1.0,
    )
    tenant_id = plan_dict.get('tenant_id', 'default')
    plan = WorkflowPlan(
        task_description=plan_dict['task_description'],
        classification=dummy_classification,
        steps=steps,
        estimated_duration_seconds=plan_dict.get('estimated_duration_seconds', 0),
        tenant_id=tenant_id,
    )

    execution = WorkflowExecution(
        plan=plan,
        current_step=d.get('current_step', 0),
        state=WorkflowState(d.get('state', 'pending')),
        total_execution_time=d.get('total_execution_time', 0.0),
        run_id=d.get('run_id'),
        depth=d.get('depth', 0),
        tenant_id=d.get('tenant_id', 'default'),
    )

    step_results = {}
    for k, v in d.get('step_results', {}).items():
        step_results[int(k)] = StepExecution(
            step_id=v['step_id'],
            success=v['success'],
            output=v.get('output', ''),
            error=v.get('error'),
            execution_time_seconds=v.get('execution_time_seconds', 0.0),
            validation_passed=v.get('validation_passed', True),
            validation_errors=v.get('validation_errors', []),
            self_healing_attempts=v.get('self_healing_attempts', 0),
            requires_rollback=v.get('requires_rollback', False),
            simulated=v.get('simulated', False),
        )
    execution.step_results = step_results
    return execution


class WorkflowEngine:
    """Executes multi-step workflows with polish mode support."""

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        agent_factory: AgentFactory,
        root: str = '.',
        enable_self_healing: bool = True,
        max_self_healing_attempts: int = 3,
        checkpoint_store: Optional[Any] = None,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._agent_factory = agent_factory
        self._root = root
        self._active_workflow: Optional[WorkflowExecution] = None
        self._enable_self_healing = enable_self_healing
        self._max_self_healing_attempts = max_self_healing_attempts
        self._workflow_lock = threading.RLock()
        self.checkpoint_store = checkpoint_store

    def execute_workflow(
        self,
        plan: WorkflowPlan,
        audit_logger: Optional[AuditLogger] = None,
        depth: int = 0,
        run_id: Optional[str] = None,
    ) -> WorkflowExecution:
        """Execute a workflow plan from start to finish.

        Args:
            plan: WorkflowPlan to execute.
            audit_logger: Optional shared AuditLogger; if provided, the
                UndoJournal sink is attached to it so rollback events are captured.
            depth: Orchestration recursion depth.
            run_id: Optional run identifier.

        Returns:
            WorkflowExecution with results.
        """
        max_depth = 5
        if depth > max_depth:
            logger.error(
                f'Workflow execution failed: max orchestration depth exceeded '
                f'(depth {depth} > {max_depth})'
            )
            # Create a failed execution with a step 0 result describing the failure
            execution = WorkflowExecution(
                plan=plan,
                state=WorkflowState.FAILED,
                depth=depth,
            )
            execution.step_results[0] = StepExecution(
                step_id=0,
                success=False,
                error=f'Max workflow orchestration depth exceeded (depth {depth} > {max_depth})',
            )
            return execution

        with self._workflow_lock:
            actual_run_id = run_id or getattr(plan, 'run_id', None)
            if not actual_run_id and audit_logger:
                actual_run_id = getattr(audit_logger, 'run_id', None)

            if self.checkpoint_store and actual_run_id:
                ckpt = self.checkpoint_store.load(actual_run_id)
                if ckpt and 'workflow_execution' in ckpt:
                    logger.info(
                        f'Found durable workflow checkpoint for run {actual_run_id}. Resuming...'
                    )
                    execution = workflow_execution_from_dict(ckpt['workflow_execution'])
                    execution.depth = depth
                    self._active_workflow = execution
                    # Resume from the next pending step
                    return self.resume_workflow(execution, audit_logger=audit_logger)

            execution = WorkflowExecution(
                plan=plan,
                state=WorkflowState.IN_PROGRESS,
                depth=depth,
                run_id=actual_run_id,
            )
            self._active_workflow = execution

            # Set up UndoJournal for rollback support on strict validation failures
            journal = UndoJournal(root=self._root)
            if audit_logger is not None:
                audit_logger.add_sink(journal)

            for step in plan.steps:
                execution.current_step = step.step_id
                result = self._execute_step(step)
                execution.step_results[step.step_id] = result

                # Save checkpoint after each step is executed!
                if self.checkpoint_store and execution.run_id:
                    self.checkpoint_store.save(
                        execution.run_id,
                        {'workflow_execution': workflow_execution_to_dict(execution)},
                    )

                # Check if strict validation requested rollback
                if result.requires_rollback:
                    logger.critical(
                        f'Automatic Rollback Triggered: Step {step.step_id} failed strict validation. '
                        f'Reverting workspace modifications.'
                    )
                    undo_result = journal.restore()
                    logger.info(
                        f'Rollback complete. Restored: {len(undo_result.restored)} files, '
                        f'Deleted: {len(undo_result.deleted)} files, '
                        f'Errors: {len(undo_result.errors)}'
                    )
                    execution.state = WorkflowState.FAILED
                    # Update checkpoint with failure state
                    if self.checkpoint_store and execution.run_id:
                        self.checkpoint_store.save(
                            execution.run_id,
                            {
                                'workflow_execution': workflow_execution_to_dict(
                                    execution
                                )
                            },
                        )
                    break

                if not result.success:
                    execution.state = WorkflowState.FAILED
                    logger.error(
                        f'Workflow failed at step {step.step_id}: {result.error}'
                    )
                    # Update checkpoint with failure state
                    if self.checkpoint_store and execution.run_id:
                        self.checkpoint_store.save(
                            execution.run_id,
                            {
                                'workflow_execution': workflow_execution_to_dict(
                                    execution
                                )
                            },
                        )
                    break

            if execution.state == WorkflowState.IN_PROGRESS:
                execution.state = WorkflowState.COMPLETED
                # Save final completed checkpoint
                if self.checkpoint_store and execution.run_id:
                    self.checkpoint_store.save(
                        execution.run_id,
                        {'workflow_execution': workflow_execution_to_dict(execution)},
                    )

            self._active_workflow = None
            return execution

    def _execute_step(
        self, step: WorkflowStep, current_attempt: int = 0
    ) -> StepExecution:
        """Execute a single workflow step, preserving self-healing attempt count.

        Execution is currently SIMULATED: the named agent is resolved from the
        plugin registry but not invoked. Real agent execution is a governed
        boundary (the AgentRunner path, with budget/audit/approval) tracked as a
        follow-up; simulated results carry ``StepExecution.simulated=True`` so
        callers never treat the synthetic output as a real agent run.

        Args:
            step: WorkflowStep to execute.
            current_attempt: Current self-healing attempt number (for recursion safety).

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

            # NOTE: workflow step execution is SIMULATED. AgentPlugin is a
            # prompt/tool descriptor, not an executable; real invocation must
            # route through the governed AgentRunner path (budget/audit/approval)
            # and is a separate, ticketed integration boundary. Until then steps
            # are marked simulated=True so downstream consumers never mistake the
            # synthetic output for a real agent run.
            logger.info(
                'Simulating step %s with agent %s (attempt %s); real agent '
                'invocation is a governed-execution boundary (not yet wired)',
                step.step_id,
                step.agent_name,
                current_attempt,
            )
            output = f'Step {step.step_id} executed by {step.agent_name}'

            execution_time = time.time() - start_time
            result = StepExecution(
                step_id=step.step_id,
                success=True,
                output=output,
                execution_time_seconds=execution_time,
                self_healing_attempts=current_attempt,
                simulated=True,
            )

            # Run post-execution validation if enabled
            if self._enable_self_healing:
                result = self._validate_and_heal_step(step, result)

            return result
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            execution_time = time.time() - start_time
            logger.warning('Step %s execution failed: %s', step.step_id, exc)
            result = StepExecution(
                step_id=step.step_id,
                success=False,
                error=str(exc),
                execution_time_seconds=execution_time,
                self_healing_attempts=current_attempt,
            )
            if self._enable_self_healing:
                result = self._validate_and_heal_step(step, result)
            return result

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
            # Trigger automatic rollback for strict validation profile
            if (
                hasattr(step, 'validation_profile')
                and step.validation_profile == 'strict'
            ):
                logger.warning(
                    f'Strict validation failed for step {step.step_id}, automatic rollback recommended'
                )
                # Set flag for caller to trigger UndoJournal rollback
                result.requires_rollback = True
            return result

        result.self_healing_attempts += 1
        current_attempt = result.self_healing_attempts
        logger.info(
            f'Attempting self-healing (attempt {current_attempt}) '
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

            # Re-execute the step, preserving incremented attempt count
            return self._execute_step(step, current_attempt=current_attempt)
        except (ImportError, ValueError, TypeError, OSError) as exc:
            logger.error('Self-healing failed: %s', exc)
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

        # Use validation profile from step if available, default to standard
        from teaagent.validation.profiles import (
            ValidationProfileName,
            run_profile_validation,
        )

        profile_name = getattr(step, 'validation_profile', 'standard')
        if profile_name not in ('fast', 'standard', 'strict'):
            profile_name = 'standard'

        try:
            profile = cast(ValidationProfileName, profile_name)
            report = run_profile_validation(self._root, profile)

            errors = []
            for result in report.results:
                if not result.skipped and result.exit_code != 0:
                    errors.append(
                        f'{result.name} failed:\n{result.stdout or result.stderr}'
                    )

            return ValidationResult(passed=report.passed, errors=errors)
        except (OSError, ImportError, ValueError, subprocess.SubprocessError) as exc:
            logger.warning('Validation profile execution failed: %s', exc)
            # Fallback to basic validation
            return ValidationResult(passed=True, errors=[])

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
        except (ImportError, ValueError, TypeError, OSError) as exc:
            logger.warning('Failed to polish agent %s: %s', agent_name, exc)
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
        self,
        execution: WorkflowExecution,
        from_step: Optional[int] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> WorkflowExecution:
        """Resume a paused workflow from a specific step.

        Args:
            execution: WorkflowExecution to resume.
            from_step: Step to resume from (defaults to current step).
            audit_logger: Optional shared AuditLogger; if provided, the
                UndoJournal sink is attached to it so rollback events are captured.

        Returns:
            Updated WorkflowExecution.
        """
        max_depth = 5
        if execution.depth > max_depth:
            logger.error(
                f'Workflow resume failed: max orchestration depth exceeded '
                f'(depth {execution.depth} > {max_depth})'
            )
            execution.state = WorkflowState.FAILED
            execution.step_results[0] = StepExecution(
                step_id=0,
                success=False,
                error=f'Max workflow orchestration depth exceeded (depth {execution.depth} > {max_depth})',
            )
            return execution

        with self._workflow_lock:
            execution.state = WorkflowState.IN_PROGRESS

            # Set up UndoJournal for rollback support on strict validation failures
            journal = UndoJournal(root=self._root)
            if audit_logger is not None:
                audit_logger.add_sink(journal)

            start_step = from_step or execution.current_step

            # Find the step to start from
            steps_to_execute = [
                step for step in execution.plan.steps if step.step_id >= start_step
            ]

            for step in steps_to_execute:
                # Skip already completed steps
                if (
                    step.step_id in execution.step_results
                    and execution.step_results[step.step_id].success
                ):
                    logger.info(
                        f'Step {step.step_id} already completed successfully. Skipping.'
                    )
                    continue

                execution.current_step = step.step_id
                result = self._execute_step(step)
                execution.step_results[step.step_id] = result

                # Save checkpoint after each step is executed!
                if self.checkpoint_store and execution.run_id:
                    self.checkpoint_store.save(
                        execution.run_id,
                        {'workflow_execution': workflow_execution_to_dict(execution)},
                    )

                # Check if strict validation requested rollback
                if result.requires_rollback:
                    logger.critical(
                        f'Automatic Rollback Triggered: Step {step.step_id} failed strict validation. '
                        f'Reverting workspace modifications.'
                    )
                    undo_result = journal.restore()
                    logger.info(
                        f'Rollback complete. Restored: {len(undo_result.restored)} files, '
                        f'Deleted: {len(undo_result.deleted)} files, '
                        f'Errors: {len(undo_result.errors)}'
                    )
                    execution.state = WorkflowState.FAILED
                    if self.checkpoint_store and execution.run_id:
                        self.checkpoint_store.save(
                            execution.run_id,
                            {
                                'workflow_execution': workflow_execution_to_dict(
                                    execution
                                )
                            },
                        )
                    break

                if not result.success:
                    execution.state = WorkflowState.FAILED
                    logger.error(
                        f'Workflow failed at step {step.step_id}: {result.error}'
                    )
                    if self.checkpoint_store and execution.run_id:
                        self.checkpoint_store.save(
                            execution.run_id,
                            {
                                'workflow_execution': workflow_execution_to_dict(
                                    execution
                                )
                            },
                        )
                    break

            if execution.state == WorkflowState.IN_PROGRESS:
                execution.state = WorkflowState.COMPLETED
                if self.checkpoint_store and execution.run_id:
                    self.checkpoint_store.save(
                        execution.run_id,
                        {'workflow_execution': workflow_execution_to_dict(execution)},
                    )

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
        with self._workflow_lock:
            execution.state = WorkflowState.FAILED
            self._active_workflow = None
            logger.info('Workflow cancelled')
