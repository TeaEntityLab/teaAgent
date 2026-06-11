"""Tests for code ontology AST parsing and graph construction."""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.code_ontology import (
    CodeEdge,
    CodeNode,
    CodeOntologyBuilder,
    CodeOntologyGraph,
)


def test_code_node_to_dict() -> None:
    node = CodeNode(
        node_id='test_id',
        node_type='Class',
        name='TestClass',
        file_path='test.py',
        line_number=10,
        metadata={'bases': ['BaseClass']},
    )

    result = node.to_dict()
    assert result['node_id'] == 'test_id'
    assert result['node_type'] == 'Class'
    assert result['name'] == 'TestClass'
    assert result['bases'] == ['BaseClass']


def test_code_edge_to_dict() -> None:
    edge = CodeEdge(
        source='source_id',
        target='target_id',
        edge_type='CALLS',
        metadata={'line': 42},
    )

    result = edge.to_dict()
    assert result['source'] == 'source_id'
    assert result['target'] == 'target_id'
    assert result['edge_type'] == 'CALLS'
    assert result['line'] == 42


def test_builder_parses_simple_python_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'test.py'
        test_file.write_text('''
def hello():
    """Say hello."""
    print("Hello, world!")

class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
''')

        builder = CodeOntologyBuilder(tmp_path)
        builder.build_from_directory(['.py'])

        nodes = builder.get_nodes()
        builder.get_edges()

        # Should have module, function, class, method
        assert len(nodes) > 0

        # Check for function node
        func_nodes = [n for n in nodes if n.name == 'hello']
        assert len(func_nodes) == 1
        assert func_nodes[0].node_type == 'Function'

        # Check for class node
        class_nodes = [n for n in nodes if n.name == 'Greeter']
        assert len(class_nodes) == 1
        assert class_nodes[0].node_type == 'Class'


def test_builder_extracts_inheritance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'test.py'
        test_file.write_text("""
class Base:
    pass

class Derived(Base):
    pass
""")

        builder = CodeOntologyBuilder(tmp_path)
        builder.build_from_directory(['.py'])

        edges = builder.get_edges()

        # Should have INHERITS edge
        inherit_edges = [e for e in edges if e.edge_type == 'INHERITS']
        assert len(inherit_edges) > 0


def test_builder_extracts_function_calls() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'test.py'
        test_file.write_text("""
def helper():
    pass

def main():
    helper()
""")

        builder = CodeOntologyBuilder(tmp_path)
        builder.build_from_directory(['.py'])

        edges = builder.get_edges()

        # Should have CALLS edge
        call_edges = [e for e in edges if e.edge_type == 'CALLS']
        assert len(call_edges) > 0


def test_builder_extracts_imports() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'test.py'
        test_file.write_text("""
import os
from sys import argv
""")

        builder = CodeOntologyBuilder(tmp_path)
        builder.build_from_directory(['.py'])

        edges = builder.get_edges()

        # Should have IMPORTS edges
        import_edges = [e for e in edges if e.edge_type == 'IMPORTS']
        assert len(import_edges) > 0


def test_builder_handles_syntax_errors() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'invalid.py'
        test_file.write_text('def broken(')

        builder = CodeOntologyBuilder(tmp_path)
        # Should not raise exception
        builder.build_from_directory(['.py'])

        # Should return empty or partial results
        assert isinstance(builder.get_nodes(), list)


def test_ontology_graph_without_store() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / 'test.py'
        test_file.write_text('def test(): pass')

        graph = CodeOntologyGraph(tmp_path, graph_store=None)
        graph.build(['.py'])

        # Queries should return empty list without graph store
        result = graph.query_dependencies('test')
        assert result == []
