"""AC-NEW-27: Subagent directory-snapshot isolation flow.

As a user, I want optional directory-snapshot isolation so child subagent runs use a
gitignore-respecting workspace snapshot instead of the parent tree.

Acceptance criteria:
- subagent tool forwards isolation=directory-snapshot to SubagentManager.
- Lineage records isolation=directory-snapshot and optional container_path.
- Snapshot lifecycle is covered by tests/test_subagent_isolation.py.
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


def test_subagent_tool_forwards_directory_snapshot_isolation() -> None:
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
                'run_id': 'child-ds',
                'status': 'completed',
                'iterations': 1,
                'tool_calls': 0,
                'final_answer': 'ok',
                'lineage': {
                    'parent_run_id': str(kwargs.get('parent_run_id', '')),
                    'def_name': 'generic',
                    'depth': 1,
                    'isolation': 'directory-snapshot',
                    'container_path': '.teaagent/subagent-snapshots/demo',
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
                {'task': 'inspect app', 'isolation': 'directory-snapshot'},
            )
        finally:
            reset_parent_run_id(token)

        assert captured['isolation'] == 'directory-snapshot'
        assert result['lineage']['isolation'] == 'directory-snapshot'
        assert (
            result['lineage']['container_path'] == '.teaagent/subagent-snapshots/demo'
        )


def test_deprecated_container_alias_still_works() -> None:
    """Test that deprecated 'container' alias still works for backward compatibility."""
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
                'run_id': 'child-ct',
                'status': 'completed',
                'iterations': 1,
                'tool_calls': 0,
                'final_answer': 'ok',
                'lineage': {
                    'parent_run_id': str(kwargs.get('parent_run_id', '')),
                    'def_name': 'generic',
                    'depth': 1,
                    'isolation': 'directory-snapshot',  # Should be normalized
                    'container_path': '.teaagent/subagent-snapshots/demo',
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
                {
                    'task': 'inspect app',
                    'isolation': 'container',
                },  # Use deprecated alias
            )
        finally:
            reset_parent_run_id(token)

        # The isolation should be normalized to directory-snapshot
        assert captured['isolation'] == 'directory-snapshot'
        assert result['lineage']['isolation'] == 'directory-snapshot'
        assert (
            result['lineage']['container_path'] == '.teaagent/subagent-snapshots/demo'
        )
