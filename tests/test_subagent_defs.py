from __future__ import annotations

from pathlib import Path

from conftest import FakeAdapter

from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.subagents import SubagentManager, load_subagent_defs


def test_load_subagent_defs_from_yaml_without_pyyaml(tmp_path, monkeypatch):
    dot = tmp_path / '.teaagent' / 'subagents'
    dot.mkdir(parents=True)
    (dot / 'code-reviewer.yaml').write_text(
        """
name: code-reviewer
description: review code quality
permission_mode: read-only
max_iterations: 3
max_tool_calls: 4
tools:
  - code_read_file
  - grep
system_prompt: |
  Be strict.
  Focus on defects.
""".strip()
        + '\n',
        encoding='utf-8',
    )

    # Force fallback parser path.
    import builtins

    original_import = builtins.__import__

    def blocked_yaml(name, *args, **kwargs):
        if name == 'yaml':
            raise ModuleNotFoundError('blocked in test')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', blocked_yaml)

    defs = load_subagent_defs(tmp_path)
    sub = defs['code-reviewer']
    assert sub.max_iterations == 3
    assert sub.max_tool_calls == 4
    assert sub.tool_whitelist == frozenset({'code_read_file', 'grep'})
    assert 'Focus on defects.' in sub.system_prompt


def test_named_subagent_tool_is_registered_and_callable(tmp_path: Path):
    sub_dir = tmp_path / '.teaagent' / 'subagents'
    sub_dir.mkdir(parents=True)
    (sub_dir / 'code-reviewer.yaml').write_text(
        'name: code-reviewer\ndescription: review helper\n',
        encoding='utf-8',
    )

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"subagent_code-reviewer","arguments":{"task":"review this"},"call_id":"sub-1"}',
            '{"type":"final","content":"child done"}',
            '{"type":"final","content":"parent done"}',
        ]
    )
    manager = SubagentManager(
        root=tmp_path,
        parent_config=ChatAgentConfig.from_root(tmp_path, enable_subagent=True),
        parent_adapter=adapter,
    )
    result = run_chat_agent(
        task='parent task',
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            tmp_path, enable_subagent=True, subagent_manager=manager
        ),
    )

    assert result.status == 'completed'
    assert result.final_answer is not None
    assert result.final_answer.content == 'parent done'
