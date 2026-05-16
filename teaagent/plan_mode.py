"""Plan Mode - Read-only exploration mode (Claude Code compatible).

Plan Mode allows the agent to explore the codebase and plan changes
without making any modifications. This is similar to Claude Code's
`EnterPlanMode` / `ExitPlanMode` tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


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
