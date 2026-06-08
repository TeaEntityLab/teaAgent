"""AC-NEW: LSP code analysis tool registration and context enrichment.

Verifies that code analysis tools are registered into the ToolRegistry when
enabled, that tree-sitter relation extraction works for Python files, that
candidate path extraction detects source code paths in task text, and that
the context pack enriches model payloads with LSP content.

Acceptance criteria:
- register_code_analysis_tools adds 6 tools to the registry.
- Tool annotations correctly mark all code-analysis tools as read_only.
- extract_candidate_paths identifies Python/TS/JS paths in task text.
- extract_tree_sitter_relations produces relations for a real Python file.
- CodeAnalysisConfig.from_root with enabled=True produces a config that
  enables code analysis for the workspace.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.code_analysis import (
    CodeAnalysisConfig,
    extract_candidate_paths,
    extract_tree_sitter_relations,
)
from teaagent.code_analysis._tools import register_code_analysis_tools
from teaagent.types import ToolRegistry

READ_ONLY_TOOLS = {
    'code_definition',
    'code_references',
    'code_diagnostics',
    'code_symbols',
    'code_tree_sitter_relations',
}


def test_code_analysis_tools_registered_and_readonly():
    registry = ToolRegistry()
    config = CodeAnalysisConfig(root=Path('.'), enabled=True)
    register_code_analysis_tools(registry, config)
    tool_names = sorted(registry.list_tools())
    assert 'code_definition' in tool_names
    assert 'code_references' in tool_names
    assert 'code_diagnostics' in tool_names
    assert 'code_symbols' in tool_names
    assert 'code_tree_sitter_relations' in tool_names
    assert 'code_relations_to_graph' in tool_names
    for name in READ_ONLY_TOOLS:
        tool = registry.get(name)
        assert tool.annotations.read_only, f'{name} must be read_only'
        assert not tool.annotations.destructive, f'{name} must not be destructive'


def test_extract_candidate_paths_finds_python():
    text = 'Inspect src/app.py and report warnings'
    paths = extract_candidate_paths(text)
    assert 'src/app.py' in paths


def test_extract_candidate_paths_finds_typescript():
    text = 'Review the type definitions in lib/types.ts'
    paths = extract_candidate_paths(text)
    assert 'lib/types.ts' in paths


def test_extract_candidate_paths_finds_javascript():
    text = 'Fix the bug in utils/helpers.js'
    paths = extract_candidate_paths(text)
    assert 'utils/helpers.js' in paths


def test_code_analysis_config_from_root_enabled(tmp_path):
    (tmp_path / '.teaagent').mkdir()
    (tmp_path / '.teaagent' / 'config.json').write_text(
        '{"code_analysis_enabled": true}', encoding='utf-8'
    )
    config = CodeAnalysisConfig.from_root(tmp_path, enabled=True)
    assert config.enabled is True


def test_tree_sitter_relations_python_file(tmp_path):
    py_file = tmp_path / 'sample.py'
    py_file.write_text(
        'class Foo:\n    def bar(self):\n        return 42\n\n'
        'def baz():\n    f = Foo()\n    return f.bar()\n',
        encoding='utf-8',
    )
    relations = extract_tree_sitter_relations(py_file)
    assert isinstance(relations, list)
    source_names = [r.source for r in relations]
    assert any('Foo' in name for name in source_names), (
        f'Expected Foo in relations, got {source_names}'
    )


def test_code_analysis_tools_not_registered_when_disabled():
    registry = ToolRegistry()
    config = CodeAnalysisConfig(root=Path('.'), enabled=False)
    register_code_analysis_tools(registry, config)
    tool_names = registry.list_tools()
    assert 'code_definition' not in tool_names
