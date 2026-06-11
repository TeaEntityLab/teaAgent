from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.cli import main


def test_subagent_tool_executes_child_run_and_returns_summary(
    chat_agent_config_with_subagent: ChatAgentConfig,
    fake_adapter_with_subagent_response: FakeAdapter,
) -> None:
    result = run_chat_agent(
        chat_agent_config_with_subagent,
        'parent task',
        adapter=fake_adapter_with_subagent_response,
    )

    assert result.status == 'completed'
    assert result.final_answer.content == 'parent done'


def test_subagent_depth_limit_blocks_second_level(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"subagent","arguments":{"task":"level1"},"call_id":"sub-1"}',
            '{"type":"tool","tool_name":"subagent","arguments":{"task":"level2"},"call_id":"sub-2"}',
            '{"type":"final","content":"level1 done"}',
            '{"type":"final","content":"parent done"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(tmp_path, enable_subagent=True, max_subagent_depth=1),
        'parent',
        adapter=adapter,
    )

    assert result.status == 'completed'


def test_subagent_tool_absent_when_disabled(
    chat_agent_config: ChatAgentConfig,
) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"subagent","arguments":{"task":"child"},"call_id":"sub-1"}'
        ]
    )

    result = run_chat_agent(
        chat_agent_config,
        'parent',
        adapter=adapter,
    )

    assert result.status != 'completed'


def test_cli_agent_run_subagent_flag_exposes_tool(
    chat_agent_config_with_subagent: ChatAgentConfig,
    fake_adapter_with_subagent_response: FakeAdapter,
) -> None:
    output = io.StringIO()

    with (
        patch(
            'teaagent.cli.create_llm_adapter',
            return_value=fake_adapter_with_subagent_response,
        ),
        redirect_stdout(output),
    ):
        exit_code = main(
            [
                'agent',
                'run',
                'gpt',
                'delegate work',
                '--subagent',
                '--root',
                str(chat_agent_config_with_subagent.root),
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['status'] == 'completed'
