"""AC-NEW-27: Subagent container isolation flow.

As a user, I want optional container isolation so child subagent runs use a
gitignore-respecting workspace snapshot instead of the parent tree.

Acceptance criteria:
- subagent tool forwards isolation=container to SubagentManager.
- Lineage records isolation=container and optional container_path.
- Snapshot lifecycle is covered by tests/test_subagent_isolation.py.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.chat_agent import ChatAgentConfig
from teaagent.subagent_run_context import bind_parent_run_id, reset_parent_run_id
from teaagent.subagents import SubagentManager
from teaagent.subagents._tools import register_subagent_tools
from teaagent.tools import ToolRegistry


class SubagentContainerIsolationFlowTests(unittest.TestCase):
    def test_subagent_tool_forwards_container_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            registry = ToolRegistry()
            config = ChatAgentConfig(root=root, enable_subagent=True)
            manager = SubagentManager(
                root=root, parent_config=config, parent_adapter=MagicMock()
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
                        'isolation': 'container',
                        'container_path': '.teaagent/subagent-containers/demo',
                    },
                    'message': '',
                }

            with patch.object(manager, 'run_subagent', side_effect=fake_run):
                register_subagent_tools(
                    registry,
                    adapter=MagicMock(),
                    config=config,
                    depth=0,
                    manager=manager,
                )
                token = bind_parent_run_id('parent-flow')
                try:
                    result = registry.execute(
                        'subagent',
                        {'task': 'inspect app', 'isolation': 'container'},
                    )
                finally:
                    reset_parent_run_id(token)

            self.assertEqual(captured['isolation'], 'container')
            self.assertEqual(result['lineage']['isolation'], 'container')
            self.assertEqual(
                result['lineage']['container_path'],
                '.teaagent/subagent-containers/demo',
            )


if __name__ == '__main__':
    unittest.main()
