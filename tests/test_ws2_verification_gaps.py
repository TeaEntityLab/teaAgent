"""WDE-003 named WS2 verification gap closures."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.subagent_run_context import (
    bind_parent_session_cost_cents,
    reset_parent_session_cost_cents,
)
from teaagent.subagents._manager import SubagentManager


def test_ws2_004_depth_concurrency_bypass_blocked() -> None:
    """WS2-004: subagent depth bypass at manager boundary returns error."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.teaagent').mkdir()
        config = ChatAgentConfig(root=root, max_subagent_depth=1)
        manager = SubagentManager(
            root=root,
            parent_config=config,
            parent_adapter=MagicMock(),
        )
        result = manager.run_subagent(
            task='nested',
            parent_run_id='parent-ws2-004',
            depth=1,
            isolation='shared',
        )
        assert result['status'] == 'error'
        assert 'depth' in result['message'].lower()


def test_ws2_003_cost_cents_inheritance_caps_child() -> None:
    """WS2-003: child max_estimated_cost_cents inherits parent remaining budget."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.teaagent').mkdir()
        config = ChatAgentConfig(
            root=root,
            max_estimated_cost_cents=1000,
            max_subagent_depth=2,
        )
        manager = SubagentManager(
            root=root,
            parent_config=config,
            parent_adapter=MagicMock(),
        )
        token = bind_parent_session_cost_cents(700.0)
        captured: dict[str, float | None] = {}

        def fake_run_chat_agent(cfg, *args, **kwargs):
            captured['max_estimated_cost_cents'] = cfg.max_estimated_cost_cents
            from teaagent.runner import FinalAnswer, RunResult

            return RunResult(
                run_id='child-ws2-003',
                final_answer=FinalAnswer(content='ok'),
                iterations=1,
                tool_calls=0,
                status='completed',
            )

        try:
            with patch('teaagent.chat_agent.run_chat_agent', fake_run_chat_agent):
                manager.run_subagent(
                    task='budget child',
                    parent_run_id='parent-ws2-003',
                    depth=0,
                    isolation='shared',
                )
        finally:
            reset_parent_session_cost_cents(token)

        assert captured['max_estimated_cost_cents'] == 300
