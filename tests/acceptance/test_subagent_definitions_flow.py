"""AC-NEW: Declarative sub-agent definitions with Markdown frontmatter.

Verifies that sub-agent definitions can be loaded from YAML, JSON, and Markdown
files with YAML frontmatter (matching Claude Code's ``.claude/agents/*.md``
convention). Also verifies that new SubagentDef fields (isolation, background,
disallowed_tools, effort) are properly parsed.

Acceptance criteria:
- load_subagent_defs discovers .yaml/.yml/.json/.md files in .teaagent/subagents/.
- Markdown files with YAML frontmatter are parsed correctly.
- system_prompt falls back to body text after frontmatter.
- disallowed_tools (Claude Code compatible) and disallowedTools are both accepted.
- isolation and background fields are read from definition files.
"""

from __future__ import annotations

from teaagent.subagents import DEFAULT_SUBAGENT_ISOLATION, load_subagent_defs


def test_markdown_frontmatter_agent_definition(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'code-reviewer.md').write_text(
        '---\n'
        'name: code-reviewer\n'
        'description: Reviews code for bugs and conventions\n'
        'model: gpt-4\n'
        'tools:\n'
        '  - workspace_read_file\n'
        '  - workspace_search_text\n'
        'max_depth: 2\n'
        'isolation: worktree\n'
        'background: true\n'
        '---\n'
        'You are a code reviewer. Look for bugs, style issues, and suggest improvements.\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'code-reviewer' in defs
    d = defs['code-reviewer']
    assert d.description == 'Reviews code for bugs and conventions'
    assert d.model == 'gpt-4'
    assert d.isolation == 'worktree'
    assert d.background is True
    assert 'code reviewer' in d.system_prompt.lower()


def test_markdown_without_frontmatter_uses_body_as_prompt(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'greeter.md').write_text(
        '---\nname: greeter\n---\nSay hello and ask how you can help.\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'greeter' in defs
    assert defs['greeter'].system_prompt == 'Say hello and ask how you can help.'


def test_yaml_agent_definition(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'explorer.yaml').write_text(
        'name: explorer\n'
        'description: Explores codebase structure\n'
        'tools:\n'
        '  - workspace_read_file\n'
        '  - workspace_list_files\n'
        'max_iterations: 10\n'
        'disallowed_tools:\n'
        '  - workspace_run_shell_mutate\n'
        'effort: high\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'explorer' in defs
    d = defs['explorer']
    assert d.max_iterations == 10
    assert d.disallowed_tools is not None
    assert 'workspace_run_shell_mutate' in d.disallowed_tools
    assert d.effort == 'high'


def test_json_agent_definition(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'tester.json').write_text(
        '{"name": "tester", "description": "Runs tests",'
        '"permission_mode": "read-only", "max_tool_calls": 12}',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'tester' in defs
    d = defs['tester']
    assert d.max_tool_calls == 12
    from teaagent.types import PermissionMode

    assert d.permission_mode == PermissionMode.READ_ONLY


def test_default_isolation_is_shared(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'simple.yaml').write_text(
        'name: simple\ndescription: A simple agent\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert defs['simple'].isolation == DEFAULT_SUBAGENT_ISOLATION


def test_unsupported_file_extensions_ignored(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'notes.txt').write_text(
        'name: ignored\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'ignored' not in defs


def test_no_subagents_dir_returns_empty(tmp_path):
    defs = load_subagent_defs(tmp_path)
    assert defs == {}


def test_disallowedTools_camelcase_accepted(tmp_path):
    agents_dir = tmp_path / '.teaagent' / 'subagents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'guarded.yaml').write_text(
        'name: guarded\n'
        'disallowedTools:\n'
        '  - workspace_run_shell_mutate\n'
        '  - workspace_write_file\n',
        encoding='utf-8',
    )
    defs = load_subagent_defs(tmp_path)
    assert 'guarded' in defs
    d = defs['guarded']
    assert d.disallowed_tools is not None
    assert 'workspace_run_shell_mutate' in d.disallowed_tools
    assert 'workspace_write_file' in d.disallowed_tools
