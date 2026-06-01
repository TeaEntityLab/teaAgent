"""Guided Recovery module for failure analysis and recovery recommendations.

This module provides tools to analyze failed agent runs and recommend
appropriate recovery actions (undo, resume, inspect, retry, manual).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from teaagent.audit import AuditLogger
from teaagent.run_undo import UndoJournal
from teaagent.runner._types import RunResult

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    """Classification of failure types."""

    TOOL_FAILURE = 'tool_failure'
    APPROVAL_DENIED = 'approval_denied'
    BUDGET_EXCEEDED = 'budget_exceeded'
    TIMEOUT = 'timeout'
    PERMISSION_ERROR = 'permission_error'
    PARTIAL_SUCCESS = 'partial_success'
    UNKNOWN = 'unknown'


class FailureSeverity(Enum):
    """Severity level of a failure."""

    LOW = 'low'  # recoverable without data loss
    MEDIUM = 'medium'  # recoverable with potential minor data loss
    HIGH = 'high'  # requires manual intervention
    CRITICAL = 'critical'  # data loss likely


@dataclass
class FailureType:
    """Classification of a run failure."""

    category: FailureCategory
    severity: FailureSeverity
    recoverable: bool
    tool_name: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RecoveryStrategy:
    """A recovery action that can be taken."""

    name: str  # "undo", "resume", "inspect", "retry", "manual"
    command_template: str  # e.g., "teaagent undo --run {run_id}"
    requires_confirmation: bool
    destructive: bool


@dataclass
class RecoveryAdvice:
    """Recommended recovery action with reasoning."""

    strategy: RecoveryStrategy
    reasoning: str
    confidence: float  # 0.0 to 1.0
    alternatives: list[RecoveryStrategy]


class FailureAnalyzer:
    """Analyzes run results to classify failures."""

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self._audit = audit_logger

    def classify(self, result: RunResult) -> FailureType:
        """Classify the failure type from run result and audit events.

        Args:
            result: RunResult from a failed or partially successful run

        Returns:
            FailureType with category, severity, and recovery information
        """
        # Check status first
        if result.status == 'completed':
            # Successful run - check for partial success indicators
            if self._has_partial_success_indicators(result):
                return FailureType(
                    category=FailureCategory.PARTIAL_SUCCESS,
                    severity=FailureSeverity.MEDIUM,
                    recoverable=True,
                    error_message='Run completed but may have partial success',
                )
            else:
                # Fully successful - no failure
                return FailureType(
                    category=FailureCategory.UNKNOWN,
                    severity=FailureSeverity.LOW,
                    recoverable=True,
                    error_message='Run completed successfully',
                )

        # Analyze error message for specific failure patterns
        error_msg = result.error_message or ''
        metadata = result.metadata or {}

        # Check for approval denied
        if self._is_approval_denied(error_msg, metadata):
            return FailureType(
                category=FailureCategory.APPROVAL_DENIED,
                severity=FailureSeverity.LOW,
                recoverable=True,
                error_message=error_msg,
            )

        # Check for budget exceeded
        if self._is_budget_exceeded(error_msg, metadata):
            return FailureType(
                category=FailureCategory.BUDGET_EXCEEDED,
                severity=FailureSeverity.HIGH,
                recoverable=False,
                error_message=error_msg,
            )

        # Check for timeout
        if self._is_timeout(error_msg, metadata):
            return FailureType(
                category=FailureCategory.TIMEOUT,
                severity=FailureSeverity.MEDIUM,
                recoverable=True,
                error_message=error_msg,
            )

        # Check for permission error
        if self._is_permission_error(error_msg, metadata):
            return FailureType(
                category=FailureCategory.PERMISSION_ERROR,
                severity=FailureSeverity.MEDIUM,
                recoverable=True,
                error_message=error_msg,
            )

        # Check for tool failure
        tool_name = self._extract_failed_tool(metadata)
        if tool_name:
            return FailureType(
                category=FailureCategory.TOOL_FAILURE,
                severity=FailureSeverity.MEDIUM,
                recoverable=True,
                tool_name=tool_name,
                error_message=error_msg,
            )

        # Default to unknown
        return FailureType(
            category=FailureCategory.UNKNOWN,
            severity=FailureSeverity.HIGH,
            recoverable=False,
            error_message=error_msg or 'Unknown failure',
        )

    def analyze(self, result: RunResult) -> dict[str, Any]:
        """Return detailed analysis including tool failures, errors, etc.

        Args:
            result: RunResult from a failed or partially successful run

        Returns:
            Dictionary with detailed analysis information
        """
        failure_type = self.classify(result)

        analysis = {
            'category': failure_type.category.value,
            'severity': failure_type.severity.value,
            'recoverable': failure_type.recoverable,
            'tool_name': failure_type.tool_name,
            'error_message': failure_type.error_message,
            'run_id': result.run_id,
            'status': result.status,
            'iterations': result.iterations,
            'tool_calls': result.tool_calls,
        }

        # Add audit event analysis if audit logger is available
        if self._audit:
            analysis['audit_events_available'] = True
            # Could add more detailed audit analysis here
        else:
            analysis['audit_events_available'] = False

        return analysis

    def _has_partial_success_indicators(self, result: RunResult) -> bool:
        """Check if a completed run has partial success indicators."""
        metadata = result.metadata or {}
        # Check for partial success flags in metadata
        return metadata.get('partial_success', False) or metadata.get(
            'incomplete', False
        )

    def _is_approval_denied(self, error_msg: str, metadata: dict[str, Any]) -> bool:
        """Check if failure is due to approval denial."""
        approval_keywords = ['approval', 'rejected', 'blocked']
        error_lower = error_msg.lower()
        return any(
            keyword in error_lower for keyword in approval_keywords
        ) or metadata.get('approval_denied', False)

    def _is_budget_exceeded(self, error_msg: str, metadata: dict[str, Any]) -> bool:
        """Check if failure is due to budget exceeded."""
        budget_keywords = ['budget', 'cost', 'limit', 'exceeded']
        error_lower = error_msg.lower()
        return any(
            keyword in error_lower for keyword in budget_keywords
        ) or metadata.get('budget_exceeded', False)

    def _is_timeout(self, error_msg: str, metadata: dict[str, Any]) -> bool:
        """Check if failure is due to timeout."""
        timeout_keywords = ['timeout', 'timed out', 'time limit']
        error_lower = error_msg.lower()
        return any(
            keyword in error_lower for keyword in timeout_keywords
        ) or metadata.get('timeout', False)

    def _is_permission_error(self, error_msg: str, metadata: dict[str, Any]) -> bool:
        """Check if failure is due to permission error."""
        permission_keywords = [
            'permission',
            'unauthorized',
            'forbidden',
            'access denied',
        ]
        error_lower = error_msg.lower()
        return any(
            keyword in error_lower for keyword in permission_keywords
        ) or metadata.get('permission_error', False)

    def _extract_failed_tool(self, metadata: dict[str, Any]) -> Optional[str]:
        """Extract the name of the failed tool from metadata."""
        return metadata.get('failed_tool') or metadata.get('last_tool')


class RecoverySelector:
    """Selects appropriate recovery strategies based on failure type."""

    def __init__(self, undo_journal: Optional[UndoJournal] = None):
        self._undo_journal = undo_journal
        self._strategy_matrix = self._build_strategy_matrix()

    def select(self, failure: FailureType) -> RecoveryAdvice:
        """Select the best recovery strategy for the failure.

        Args:
            failure: Classified failure type

        Returns:
            RecoveryAdvice with recommended strategy and reasoning
        """
        strategies = self._strategy_matrix.get(failure.category, [])

        if not strategies:
            # Default to inspect for unknown failures
            strategies = [
                RecoveryStrategy(
                    name='inspect',
                    command_template='teaagent audit view --run {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                )
            ]

        # Select primary strategy
        primary = strategies[0]
        alternatives = strategies[1:] if len(strategies) > 1 else []

        # Build reasoning
        reasoning = self._build_reasoning(failure, primary)

        # Calculate confidence based on failure type and journal state
        confidence = self._calculate_confidence(failure, primary)

        return RecoveryAdvice(
            strategy=primary,
            reasoning=reasoning,
            confidence=confidence,
            alternatives=alternatives,
        )

    def rank(self, failure: FailureType) -> list[RecoveryStrategy]:
        """Rank all applicable recovery strategies.

        Args:
            failure: Classified failure type

        Returns:
            List of RecoveryStrategy in priority order
        """
        return self._strategy_matrix.get(failure.category, [])

    def _build_strategy_matrix(self) -> dict[FailureCategory, list[RecoveryStrategy]]:
        """Build the failure-to-strategy mapping."""
        return {
            FailureCategory.TOOL_FAILURE: [
                RecoveryStrategy(
                    name='inspect',
                    command_template='teaagent audit view --run {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='undo',
                    command_template='teaagent undo --run {run_id}',
                    requires_confirmation=True,
                    destructive=True,
                ),
                RecoveryStrategy(
                    name='retry',
                    command_template='teaagent run --resume {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
            FailureCategory.APPROVAL_DENIED: [
                RecoveryStrategy(
                    name='inspect',
                    command_template='teaagent audit view --run {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='manual',
                    command_template='# Manual intervention required',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
            FailureCategory.BUDGET_EXCEEDED: [
                RecoveryStrategy(
                    name='manual',
                    command_template='# Manual intervention required to adjust budget',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='resume',
                    command_template='teaagent run --resume {run_id} --budget-adjusted',
                    requires_confirmation=True,
                    destructive=False,
                ),
            ],
            FailureCategory.TIMEOUT: [
                RecoveryStrategy(
                    name='resume',
                    command_template='teaagent run --resume {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='retry',
                    command_template='teaagent run --retry {run_id} --timeout-extended',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
            FailureCategory.PERMISSION_ERROR: [
                RecoveryStrategy(
                    name='retry',
                    command_template='teaagent run --retry {run_id} --permission-mode safer',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='manual',
                    command_template='# Manual intervention required to fix permissions',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
            FailureCategory.PARTIAL_SUCCESS: [
                RecoveryStrategy(
                    name='undo',
                    command_template='teaagent undo --run {run_id}',
                    requires_confirmation=True,
                    destructive=True,
                ),
                RecoveryStrategy(
                    name='manual',
                    command_template='# Manual intervention required to clean partial state',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
            FailureCategory.UNKNOWN: [
                RecoveryStrategy(
                    name='inspect',
                    command_template='teaagent audit view --run {run_id}',
                    requires_confirmation=False,
                    destructive=False,
                ),
                RecoveryStrategy(
                    name='manual',
                    command_template='# Manual intervention required',
                    requires_confirmation=False,
                    destructive=False,
                ),
            ],
        }

    def _build_reasoning(self, failure: FailureType, strategy: RecoveryStrategy) -> str:
        """Build reasoning for the recommended strategy."""
        reasoning_parts = [
            f'Failure type: {failure.category.value}',
            f'Severity: {failure.severity.value}',
        ]

        if failure.tool_name:
            reasoning_parts.append(f'Failed tool: {failure.tool_name}')

        if self._undo_journal and self._undo_journal.has_entries:
            reasoning_parts.append('Undo journal has entries available')

        reasoning_parts.append(f'Recommended action: {strategy.name}')

        if strategy.destructive:
            reasoning_parts.append(
                '⚠️  This action is destructive and will modify workspace state'
            )

        return '. '.join(reasoning_parts)

    def _calculate_confidence(
        self, failure: FailureType, strategy: RecoveryStrategy
    ) -> float:
        """Calculate confidence score for the recommendation."""
        base_confidence = 0.8

        # Increase confidence for well-understood failure types
        if failure.category in {
            FailureCategory.TOOL_FAILURE,
            FailureCategory.APPROVAL_DENIED,
            FailureCategory.TIMEOUT,
        }:
            base_confidence = 0.9

        # Decrease confidence for unknown failures
        if failure.category == FailureCategory.UNKNOWN:
            base_confidence = 0.5

        # Adjust based on undo journal availability
        if strategy.name == 'undo' and self._undo_journal:
            if self._undo_journal.has_entries:
                base_confidence += 0.1
            else:
                base_confidence -= 0.3

        return min(max(base_confidence, 0.0), 1.0)


class RecoveryAdviceFormatter:
    """Formats recovery advice for display to the operator."""

    def format(self, advice: RecoveryAdvice, run_id: str) -> str:
        """Format advice as human-readable text.

        Args:
            advice: RecoveryAdvice to format
            run_id: Run ID for command template substitution

        Returns:
            Formatted string with recovery recommendations
        """
        lines = [
            '═══════════════════════════════════════════════════════════════',
            '                    RECOVERY RECOMMENDATION',
            '═══════════════════════════════════════════════════════════════',
            '',
            f'Recommended Action: {advice.strategy.name.upper()}',
            f'Confidence: {advice.confidence:.0%}',
            '',
            'Reasoning:',
            f'  {advice.reasoning}',
            '',
            'Command to execute:',
            f'  {self._format_command(advice.strategy, run_id)}',
            '',
        ]

        if advice.strategy.destructive:
            lines.append(
                '⚠️  WARNING: This action is destructive and will modify workspace state'
            )
            lines.append('')

        if advice.strategy.requires_confirmation:
            lines.append('⚠️  This action requires confirmation before execution')
            lines.append('')

        if advice.alternatives:
            lines.append('Alternative actions:')
            for i, alt in enumerate(advice.alternatives, 1):
                lines.append(f'  {i}. {alt.name}: {self._format_command(alt, run_id)}')
                if alt.destructive:
                    lines.append('     (destructive)')
            lines.append('')

        lines.append('═══════════════════════════════════════════════════════════════')

        return '\n'.join(lines)

    def format_json(self, advice: RecoveryAdvice, run_id: str) -> dict[str, Any]:
        """Format advice as JSON for programmatic use.

        Args:
            advice: RecoveryAdvice to format
            run_id: Run ID for command template substitution

        Returns:
            Dictionary with structured advice data
        """
        return {
            'recommended_strategy': {
                'name': advice.strategy.name,
                'command': self._format_command(advice.strategy, run_id),
                'requires_confirmation': advice.strategy.requires_confirmation,
                'destructive': advice.strategy.destructive,
            },
            'reasoning': advice.reasoning,
            'confidence': advice.confidence,
            'alternatives': [
                {
                    'name': alt.name,
                    'command': self._format_command(alt, run_id),
                    'requires_confirmation': alt.requires_confirmation,
                    'destructive': alt.destructive,
                }
                for alt in advice.alternatives
            ],
        }

    def _format_command(self, strategy: RecoveryStrategy, run_id: str) -> str:
        """Format command template with run_id."""
        return strategy.command_template.format(run_id=run_id)
