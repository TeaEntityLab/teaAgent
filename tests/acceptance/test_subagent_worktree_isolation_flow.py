"""AC-NEW-26: Subagent worktree isolation flow.

As a user, I want optional worktree isolation so child subagent runs can use a
detached git worktree instead of the parent workspace.

Acceptance criteria:
- subagent tool forwards isolation=worktree to SubagentManager.
- Lineage records isolation=worktree and optional worktree_path.
- Real git worktree lifecycle is covered by tests/test_subagent_isolation.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.chat_agent import ChatAgentConfig
from teaagent.llm import FakeLLMAdapter
from teaagent.subagent_run_context import bind_parent_run_id, reset_parent_run_id
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.types import ToolRegistry


def test_subagent_tool_forwards_worktree_isolation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.teaagent').mkdir()
        registry = ToolRegistry()
        config = ChatAgentConfig(root=root, enable_subagent=True)
        adapter = FakeLLMAdapter()
        manager = SubagentManager(
            root=root, parent_config=config, parent_adapter=adapter
        )
        captured: dict[str, str] = {}

        def fake_run(**kwargs: object) -> dict[str, object]:
            captured['isolation'] = str(kwargs.get('isolation', ''))
            return {
                'run_id': 'child-wt',
                'status': 'completed',
                'iterations': 1,
                'tool_calls': 0,
                'final_answer': 'ok',
                'lineage': {
                    'parent_run_id': str(kwargs.get('parent_run_id', '')),
                    'def_name': 'generic',
                    'depth': 1,
                    'isolation': 'worktree',
                    'worktree_path': '.teaagent/subagent-worktrees/demo',
                },
                'message': '',
            }

        manager.run_subagent = fake_run
        register_subagent_tools(
            registry,
            adapter=adapter,
            config=config,
            depth=0,
            manager=manager,
        )
        token = bind_parent_run_id('parent-flow')
        try:
            result = registry.execute(
                'subagent',
                {'task': 'inspect README', 'isolation': 'worktree'},
            )
        finally:
            reset_parent_run_id(token)

        assert captured['isolation'] == 'worktree'
        assert result['lineage']['isolation'] == 'worktree'
        assert result['lineage']['worktree_path'] == '.teaagent/subagent-worktrees/demo'
