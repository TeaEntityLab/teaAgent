"""Prompt Gate - Gates agent prompt modifications on zero-regression verification suites."""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from teaagent.plugin_system import PluginRegistry

logger = logging.getLogger(__name__)


class PromptChangeEvalGate:
    """Gates prompt changes on successful runs of test suites (zero-regression)."""

    def __init__(self, registry: PluginRegistry, root: str = '.') -> None:
        self.registry = registry
        self.root = root

    def propose_prompt_change(
        self,
        agent_name: str,
        new_prompt: str,
        test_command: list[str],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """Apply a new prompt, run tests, and revert the change if they fail.

        Args:
            agent_name: Name of the agent whose prompt is being changed.
            new_prompt: The proposed system prompt.
            test_command: Command to execute to verify zero regression.

        Returns:
            Tuple of (success, message).
        """
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return False, f"Agent '{agent_name}' not found."

        old_prompt = agent.system_prompt
        logger.info(
            f"Proposing prompt change for agent '{agent_name}'. Running verification suite..."
        )

        # Apply the proposed prompt
        agent.system_prompt = new_prompt

        # Execute verification tests
        try:
            res = subprocess.run(
                test_command,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                logger.info(
                    f"Verification tests passed. Prompt change allowed for agent '{agent_name}'."
                )
                return True, 'Prompt change accepted: zero regression detected.'
            else:
                # Revert change
                agent.system_prompt = old_prompt
                logger.warning(
                    f'Verification tests failed (exit code {res.returncode}). '
                    f"Reverted prompt change for agent '{agent_name}'."
                )
                error_msg = res.stdout + res.stderr
                return False, f'Prompt change rejected due to regression:\n{error_msg}'
        except Exception as exc:
            # Revert change
            agent.system_prompt = old_prompt
            logger.error(f'Error during verification: {exc}. Reverted prompt change.')
            return False, f'Verification failed with exception: {exc}'
