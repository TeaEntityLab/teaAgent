from __future__ import annotations

from teaagent.code_analysis import (
    CodeAnalysisConfig,
    extract_tree_sitter_relations,
    ingest_code_relations_to_graph,
    register_code_analysis_tools,
)
from teaagent.graph_rag import KnowledgeGraph
from teaagent.tools import ToolRegistry


def test_code_analysis_tools_not_registered_when_disabled(tmp_path):
    registry = ToolRegistry()
    config = CodeAnalysisConfig.from_root(tmp_path, enabled=False)
    register_code_analysis_tools(registry, config)
    for name in (
        'code_definition',
        'code_references',
        'code_diagnostics',
        'code_symbols',
        'code_tree_sitter_relations',
        'code_relations_to_graph',
    ):
        try:
            registry.get(name)
            raise AssertionError(f'{name} should not exist when disabled')
        except KeyError:
            pass


def test_code_analysis_tools_registered_and_callable(tmp_path):
    registry = ToolRegistry()
    config = CodeAnalysisConfig.from_root(tmp_path, enabled=True)
    register_code_analysis_tools(registry, config)

    out1 = registry.execute(
        'code_definition', {'path': 'README.md', 'line': 1, 'column': 1}
    )
    out2 = registry.execute(
        'code_references', {'path': 'README.md', 'line': 1, 'column': 1}
    )
    out3 = registry.execute('code_diagnostics', {'path': 'README.md'})
    out4 = registry.execute('code_symbols', {'path': 'README.md'})
    out5 = registry.execute('code_tree_sitter_relations', {'path': 'README.md'})
    out6 = registry.execute('code_relations_to_graph', {'path': 'README.md'})

    assert out1 == {'references': []}
    assert out2 == {'references': []}
    assert out3 == {'diagnostics': []}
    assert out4 == {'symbols': []}
    assert out5 == {'relations': []}
    assert out6['relations'] == 0


def test_ingest_code_relations_to_graph(tmp_path, monkeypatch):
    sample = tmp_path / 'sample.py'
    sample.write_text(
        'import os\ndef outer():\n    print(os.getcwd())\n',
        encoding='utf-8',
    )
    graph = KnowledgeGraph()
    from teaagent.code_analysis import _treesitter

    monkeypatch.setattr(_treesitter, '_try_tree_sitter_parse', lambda *_: object())

    relations = ingest_code_relations_to_graph(str(sample), graph, doc_id='doc-code-1')

    assert len(relations) >= 2
    assert len(graph.all_documents()) == 1
    assert len(graph.all_edges()) >= 2
    assert graph.all_documents()[0].doc_id == 'doc-code-1'


def test_extract_tree_sitter_relations_unknown_extension_returns_empty(tmp_path):
    sample = tmp_path / 'sample.txt'
    sample.write_text('hello', encoding='utf-8')
    assert extract_tree_sitter_relations(str(sample)) == []


def test_extract_tree_sitter_relations_known_extension_parser_failure_falls_back(
    tmp_path, monkeypatch
):
    sample = tmp_path / 'broken.py'
    sample.write_text('def x():\n  pass\n', encoding='utf-8')

    from teaagent.code_analysis import _treesitter

    def _raise(*_: object) -> None:
        raise RuntimeError('boom')

    monkeypatch.setattr(_treesitter, '_try_tree_sitter_parse', _raise)
    relations = extract_tree_sitter_relations(str(sample))
    assert len(relations) >= 1


def test_extract_tree_sitter_relations_non_python_parser_failure_raises(
    tmp_path, monkeypatch
):
    sample = tmp_path / 'broken.js'
    sample.write_text('function x() { return 1; }', encoding='utf-8')

    from teaagent.code_analysis import _treesitter

    def _raise(*_: object) -> None:
        raise RuntimeError('boom')

    monkeypatch.setattr(_treesitter, '_try_tree_sitter_parse', _raise)
    try:
        extract_tree_sitter_relations(str(sample))
        raise AssertionError('expected non-python parser failure to raise')
    except RuntimeError:
        pass
