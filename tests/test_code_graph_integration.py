"""Acceptance tests for Tree-Sitter + KnowledgeGraph integration."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.code_analysis._treesitter import extract_tree_sitter_relations
from teaagent.graph_rag import KnowledgeGraph


class TestCodeGraphIntegration(unittest.TestCase):
    def test_ingest_code_relations_to_graph(self) -> None:
        """
        Verify that CodeRelations extracted via Tree-Sitter (or AST fallback)
        can be correctly ingested into a KnowledgeGraph.
        """
        with TemporaryDirectory() as td:
            root = Path(td)
            code_file = root / 'example.py'
            code_file.write_text(
                'import os\n'
                'class Base:\n'
                '    pass\n'
                'class Sub(Base):\n'
                '    def run(self):\n'
                "        print('hello')\n",
                encoding='utf-8',
            )

            # 1. Extract relations
            relations = extract_tree_sitter_relations(str(code_file))
            self.assertTrue(len(relations) > 0)

            # 2. Ingest into graph (we will implement this helper)
            from teaagent.code_analysis._graph_rag import ingest_code_to_graph

            graph = KnowledgeGraph()
            ingest_code_to_graph(graph, relations, document_id='doc_example')

            # 3. Verify edges
            edges = graph.all_edges()
            for e in edges:
                print(f'DEBUG EDGE: {e.source} --({e.relation})--> {e.target}')

            # Check for 'defines'
            self.assertTrue(
                any(
                    e.source == 'example'
                    and e.relation == 'defines'
                    and 'Base' in e.target
                    for e in edges
                )
            )
            self.assertTrue(
                any(
                    e.source == 'example'
                    and e.relation == 'defines'
                    and 'Sub' in e.target
                    for e in edges
                )
            )

            # Check for 'inherits'
            self.assertTrue(
                any(
                    e.source == 'example.Sub'
                    and e.relation == 'inherits'
                    and e.target == 'Base'
                    for e in edges
                )
            )

            # Check for 'calls'
            self.assertTrue(
                any(
                    e.source == 'example.Sub.run'
                    and e.relation == 'calls'
                    and e.target == 'print'
                    for e in edges
                )
            )

            # Check for document association
            for edge in edges:
                self.assertIn('doc_example', edge.document_ids)


if __name__ == '__main__':
    unittest.main()
