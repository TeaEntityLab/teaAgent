"""Acceptance test for prompt change evaluation gating flow."""

from __future__ import annotations

import sys
import unittest

from teaagent.plugin_system import AgentPlugin, PluginRegistry
from teaagent.prompt_gate import PromptChangeEvalGate


class TestPromptChangeEvalGateFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PluginRegistry()
        self.agent = AgentPlugin(
            name='helper-agent',
            description='Helper Agent',
            system_prompt='Original prompt text',
            tools=(),
        )
        self.registry.register_agent(self.agent)
        self.gate = PromptChangeEvalGate(self.registry)

    def test_gate_accepts_on_successful_tests(self) -> None:
        # A test command that exits with 0
        cmd = [sys.executable, '-c', 'exit(0)']

        success, msg = self.gate.propose_prompt_change(
            agent_name='helper-agent',
            new_prompt='New improved prompt text',
            test_command=cmd,
        )

        self.assertTrue(success)
        self.assertIn('accepted', msg.lower())
        # The prompt should be updated
        self.assertEqual(self.agent.system_prompt, 'New improved prompt text')

    def test_gate_rejects_and_reverts_on_failed_tests(self) -> None:
        # A test command that exits with 1 (regression)
        cmd = [sys.executable, '-c', 'print("regression failure"); exit(1)']

        success, msg = self.gate.propose_prompt_change(
            agent_name='helper-agent',
            new_prompt='New broken prompt text',
            test_command=cmd,
        )

        self.assertFalse(success)
        self.assertIn('rejected', msg.lower())
        self.assertIn('regression failure', msg)
        # The prompt should be reverted back to original
        self.assertEqual(self.agent.system_prompt, 'Original prompt text')


if __name__ == '__main__':
    unittest.main()
