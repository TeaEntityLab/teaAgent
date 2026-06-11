"""Acceptance test for prompt change evaluation gating flow."""

from __future__ import annotations

import sys

import pytest

from teaagent.plugin_system import AgentPlugin, PluginRegistry
from teaagent.prompt_gate import PromptChangeEvalGate


@pytest.fixture
def gate_setup():
    registry = PluginRegistry()
    agent = AgentPlugin(
        name='helper-agent',
        description='Helper Agent',
        system_prompt='Original prompt text',
        tools=(),
    )
    registry.register_agent(agent)
    gate = PromptChangeEvalGate(registry)
    return registry, agent, gate


def test_gate_accepts_on_successful_tests(gate_setup) -> None:
    registry, agent, gate = gate_setup
    # A test command that exits with 0
    cmd = [sys.executable, '-c', 'exit(0)']

    success, msg = gate.propose_prompt_change(
        agent_name='helper-agent',
        new_prompt='New improved prompt text',
        test_command=cmd,
    )

    assert success
    assert 'accepted' in msg.lower()
    # The prompt should be updated
    assert agent.system_prompt == 'New improved prompt text'


def test_gate_rejects_and_reverts_on_failed_tests(gate_setup) -> None:
    registry, agent, gate = gate_setup
    # A test command that exits with 1 (regression)
    cmd = [sys.executable, '-c', 'print("regression failure"); exit(1)']

    success, msg = gate.propose_prompt_change(
        agent_name='helper-agent',
        new_prompt='New broken prompt text',
        test_command=cmd,
    )

    assert not success
    assert 'rejected' in msg.lower()
    assert 'regression failure' in msg
    # The prompt should be reverted back to original
    assert agent.system_prompt == 'Original prompt text'
