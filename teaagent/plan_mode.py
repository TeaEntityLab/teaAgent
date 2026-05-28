"""Plan Mode - Read-only exploration mode (Claude Code compatible).

Plan Mode allows the agent to explore the codebase and plan changes
without making any modifications. This is similar to Claude Code's
`EnterPlanMode` / `ExitPlanMode` tools.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class InsufficientContextError(Exception):
    """Raised when context gathering exceeds hard limit without sufficient information."""

    pass


@dataclass
class ContextGatherer:
    """Self-sufficient context gatherer with turn limits and Skill-RAG integration."""

    soft_limit: int = 3
    hard_limit: int = 5
    current_turn: int = 0
    use_skill_rag: bool = True
    skill_rag_max_rounds: int = 3

    def gather_context(
        self,
        task: str,
        memories: list[str],
        llm_check_fn: Callable[[str, list[str]], tuple[bool, list[str]]],
        gather_fn: Callable[[list[str]], None],
        retriever: Optional[Any] = None,
        answer_generator: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        """Gather context with turn-based self-checking and optional Skill-RAG.

        Args:
            task: Current task description.
            memories: Current memory/context list.
            llm_check_fn: Function that checks context sufficiency.
                Returns (is_sufficient, needs_list).
            gather_fn: Function that gathers additional context based on needs.
            retriever: Optional InMemoryRetriever for Skill-RAG integration.
            answer_generator: Optional answer generator for Skill-RAG.

        Raises:
            InsufficientContextError: If hard limit exceeded without sufficient context.
        """
        self.current_turn = 0

        while self.current_turn < self.hard_limit:
            self.current_turn += 1

            is_sufficient, needs = llm_check_fn(task, memories)

            if is_sufficient:
                return

            if self.current_turn > self.soft_limit:
                logger.warning(
                    f'Context sufficiency check round {self.current_turn}/{self.hard_limit}: '
                    f'Context may be insufficient. Needs: {needs}'
                )

            if self.current_turn >= self.hard_limit:
                raise InsufficientContextError(
                    f'Context gathering exceeded hard limit ({self.hard_limit} turns) '
                    f'without achieving sufficiency. Unmet needs: {needs}'
                )

            # Use Skill-RAG for collaborative retrieval if enabled and retriever provided
            if self.use_skill_rag and retriever is not None and answer_generator is not None:
                try:
                    self._gather_with_skill_rag(needs, retriever, answer_generator, memories)
                except Exception:
                    # Fall back to regular gather_fn if Skill-RAG fails
                    gather_fn(needs)
            else:
                gather_fn(needs)

    def _gather_with_skill_rag(
        self,
        needs: list[str],
        retriever: Any,
        answer_generator: Callable[[str, str], str],
        memories: list[str],
    ) -> None:
        """Gather context using Skill-RAG for precision retrieval.

        This method uses the Skill-RAG engine to perform multi-round adaptive
        retrieval, which can reduce context token volume by 50%+ through
        evidence_focusing and query rewriting.

        Args:
            needs: List of information needs to gather.
            retriever: InMemoryRetriever instance.
            answer_generator: Answer generator callable.
            memories: Memory list to append retrieved context to.
        """
        from teaagent.rag import skill_rag_retrieve

        for need in needs:
            try:
                result = skill_rag_retrieve(
                    query=need,
                    retriever=retriever,
                    answer_generator=answer_generator,
                    max_rounds=self.skill_rag_max_rounds,
                )
                logger.info(
                    f'Skill-RAG retrieval for need "{need}": '
                    f'{result["rounds"]} rounds, state={result["final_state"]}, '
                    f'skills={result["skills_used"]}'
                )
                # Append the retrieved context to memories
                memories.append(f'[Skill-RAG: {need}]\n{result["context"]}')
            except Exception as exc:
                logger.warning(f'Skill-RAG retrieval failed for need "{need}": {exc}')
                # Fall back to regular gather_fn if Skill-RAG fails
                raise


class PlanModeState(Enum):
    """Plan mode states."""

    DISABLED = 'disabled'
    ENABLED = 'enabled'
    CONFIRMING = 'confirming'


@dataclass
class PlanModeConfig:
    """Configuration for plan mode behavior."""

    allow_file_reads: bool = True
    allow_search: bool = True
    allow_lsp_navigation: bool = True
    allow_web_search: bool = True
    block_writes: bool = True
    block_shell: bool = True
    require_confirmation_before_exit: bool = True


@dataclass
class PlanMode:
    """Plan Mode implementation - read-only exploration.

    When enabled, the agent can explore the codebase but cannot:
    - Write or edit files
    - Execute shell commands
    - Make system changes

    The mode is useful for:
    - Understanding existing code
    - Planning refactoring approaches
    - Exploring unfamiliar codebases
    - Reviewing code without accidental changes
    """

    state: PlanModeState = PlanModeState.DISABLED
    config: PlanModeConfig = field(default_factory=PlanModeConfig)
    reason: Optional[str] = None
    exploration_notes: list[str] = field(default_factory=list)

    def enable(self, reason: Optional[str] = None) -> None:
        """Enable plan mode."""
        self.state = PlanModeState.ENABLED
        self.reason = reason or 'User requested plan mode'
        self.exploration_notes.clear()

    def disable(self) -> None:
        """Disable plan mode."""
        if self.config.require_confirmation_before_exit and self.exploration_notes:
            self.state = PlanModeState.CONFIRMING
        else:
            self._force_disable()

    def confirm_exit(self) -> None:
        """Confirm exit from confirmation state."""
        self._force_disable()

    def cancel_exit(self) -> None:
        """Cancel exit and remain in plan mode."""
        self.state = PlanModeState.ENABLED

    def _force_disable(self) -> None:
        """Force disable plan mode."""
        self.state = PlanModeState.DISABLED
        self.reason = None

    def is_enabled(self) -> bool:
        """Check if plan mode is currently enabled."""
        return self.state == PlanModeState.ENABLED

    def can_execute_tool(self, tool_name: str) -> tuple[bool, Optional[str]]:
        """Check if a tool can be executed in current state.

        Returns (allowed, reason_if_not_allowed)
        """
        if not self.is_enabled():
            return True, None

        write_tools = {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'workspace_create_directory',
            'workspace_delete',
        }

        shell_tools = {'shell', 'terminal', 'process'}

        if tool_name in write_tools and self.config.block_writes:
            return (
                False,
                'Plan mode blocks file writes. Use ExitPlanMode to enable edits.',
            )

        if tool_name in shell_tools and self.config.block_shell:
            return (
                False,
                'Plan mode blocks shell execution. Use ExitPlanMode to enable commands.',
            )

        if tool_name in shell_tools and not self.config.allow_file_reads:
            return False, 'Plan mode blocks shell in read-only config.'

        return True, None

    def add_note(self, note: str) -> None:
        """Add an exploration note during plan mode."""
        if self.is_enabled():
            self.exploration_notes.append(note)

    def get_exploration_summary(self) -> str:
        """Get summary of exploration notes."""
        if not self.exploration_notes:
            return 'No exploration notes recorded.'
        return '\n'.join(f'- {note}' for note in self.exploration_notes)


# --- Plan Mode Tools ---


def create_plan_mode_tools() -> dict[str, Any]:
    """Create the EnterPlanMode and ExitPlanMode tool definitions."""

    def enter_plan_mode(arguments: dict[str, Any]) -> dict[str, Any]:
        reason = arguments.get('reason', 'Exploration mode enabled')
        return {'status': 'enabled', 'reason': reason}

    def exit_plan_mode(arguments: dict[str, Any]) -> dict[str, Any]:
        confirm = arguments.get('confirm', False)
        return {'status': 'exited', 'confirm': confirm}

    return {
        'enter_plan_mode': {
            'description': 'Enter plan mode for read-only exploration. No file writes or shell commands allowed.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'reason': {
                        'type': 'string',
                        'description': 'Reason for entering plan mode',
                    }
                },
            },
            'handler': enter_plan_mode,
        },
        'exit_plan_mode': {
            'description': 'Exit plan mode and return to normal execution.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'confirm': {
                        'type': 'boolean',
                        'description': 'Confirm exit from plan mode',
                    }
                },
            },
            'handler': exit_plan_mode,
        },
    }
