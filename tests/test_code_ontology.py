"""Tests for code ontology AST parsing and graph construction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.code_ontology import (
    CodeEdge,
    CodeNode,
    CodeOntologyBuilder,
    CodeOntologyGraph,
)


class CodeOntologyTests(unittest.TestCase):
    def test_code_node_to_dict(self) -> None:
        node = CodeNode(
            node_id='test_id',
            node_type='Class',
            name='TestClass',
            file_path='test.py',
            line_number=10,
            metadata={'bases': ['BaseClass']},
        )
        
        result = node.to_dict()
        self.assertEqual(result['node_id'], 'test_id')
        self.assertEqual(result['node_type'], 'Class')
        self.assertEqual(result['name'], 'TestClass')
        self.assertEqual(result['bases'], ['BaseClass'])
    
    def test_code_edge_to_dict(self) -> None:
        edge = CodeEdge(
            source='source_id',
            target='target_id',
            edge_type='CALLS',
            metadata={'line': 42},
        )
        
        result = edge.to_dict()
        self.assertEqual(result['source'], 'source_id')
        self.assertEqual(result['target'], 'target_id')
        self.assertEqual(result['edge_type'], 'CALLS')
        self.assertEqual(result['line'], 42)
    
    def test_builder_parses_simple_python_file(self) -> None:
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
            edges = builder.get_edges()
            
            # Should have module, function, class, method
            self.assertGreater(len(nodes), 0)
            
            # Check for function node
            func_nodes = [n for n in nodes if n.name == 'hello']
            self.assertEqual(len(func_nodes), 1)
            self.assertEqual(func_nodes[0].node_type, 'Function')
            
            # Check for class node
            class_nodes = [n for n in nodes if n.name == 'Greeter']
            self.assertEqual(len(class_nodes), 1)
            self.assertEqual(class_nodes[0].node_type, 'Class')
    
    def test_builder_extracts_inheritance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / 'test.py'
            test_file.write_text('''
class Base:
    pass

class Derived(Base):
    pass
''')
            
            builder = CodeOntologyBuilder(tmp_path)
            builder.build_from_directory(['.py'])
            
            edges = builder.get_edges()
            
            # Should have INHERITS edge
            inherit_edges = [e for e in edges if e.edge_type == 'INHERITS']
            self.assertGreater(len(inherit_edges), 0)
    
    def test_builder_extracts_function_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / 'test.py'
            test_file.write_text('''
def helper():
    pass

def main():
    helper()
''')
            
            builder = CodeOntologyBuilder(tmp_path)
            builder.build_from_directory(['.py'])
            
            edges = builder.get_edges()
            
            # Should have CALLS edge
            call_edges = [e for e in edges if e.edge_type == 'CALLS']
            self.assertGreater(len(call_edges), 0)
    
    def test_builder_extracts_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / 'test.py'
            test_file.write_text('''
import os
from sys import argv
''')
            
            builder = CodeOntologyBuilder(tmp_path)
            builder.build_from_directory(['.py'])
            
            edges = builder.get_edges()
            
            # Should have IMPORTS edges
            import_edges = [e for e in edges if e.edge_type == 'IMPORTS']
            self.assertGreater(len(import_edges), 0)
    
    def test_builder_handles_syntax_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / 'invalid.py'
            test_file.write_text('def broken(')
            
            builder = CodeOntologyBuilder(tmp_path)
            # Should not raise exception
            builder.build_from_directory(['.py'])
            
            # Should return empty or partial results
            self.assertIsInstance(builder.get_nodes(), list)
    
    def test_ontology_graph_without_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_file = tmp_path / 'test.py'
            test_file.write_text('def test(): pass')
            
            graph = CodeOntologyGraph(tmp_path, graph_store=None)
            graph.build(['.py'])
            
            # Queries should return empty list without graph store
            result = graph.query_dependencies('test')
            self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
