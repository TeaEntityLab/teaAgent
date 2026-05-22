from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.context_pack import build_context_pack
from teaagent.hybrid_search import LocalHybridSearchBackend, register_hybrid_backend
from teaagent.memory import MemoryCatalog


class ContextPackTests(unittest.TestCase):
    def test_build_context_pack_is_deterministic_for_task_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'teaagent' / 'preflight.py'
            target.parent.mkdir(parents=True)
            target.write_text('def preflight():\n    pass\n', encoding='utf-8')
            (root / 'AGENTS.md').write_text(
                'See teaagent/preflight.py for planning.', encoding='utf-8'
            )
            MemoryCatalog(root).add(
                'plan changes to teaagent/preflight.py before editing',
                tags=('preflight',),
            )

            pack = build_context_pack(
                'plan changes to teaagent/preflight.py before editing',
                root=root,
            )
            payload = pack.to_dict()

            self.assertTrue(payload['read_only'])
            paths = [entry['path'] for entry in payload['candidate_files']]
            self.assertIn('teaagent/preflight.py', paths)
            self.assertTrue(
                any(entry['exists'] for entry in payload['candidate_files'])
            )
            self.assertGreaterEqual(len(payload['memories']), 1)
            self.assertGreaterEqual(len(payload['symbols']), 1)
            self.assertEqual(payload['graph_rag']['status'], 'not_indexed')
            self.assertEqual(payload['graph_rag']['reason'], 'no_index_present')

    def test_context_pack_only_touches_memory_catalog_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('hello', encoding='utf-8')
            before = sorted(root.rglob('*'))
            build_context_pack('inspect README.md', root=root)
            after = sorted(root.rglob('*'))
            new_paths = [path for path in after if path not in before]
            self.assertTrue(
                all('.teaagent' in str(path) for path in new_paths),
                msg=f'unexpected writes: {new_paths}',
            )

    def test_context_pack_includes_hybrid_hits_when_index_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'docs').mkdir()
            readme = root / 'docs' / 'runner.md'
            readme.write_text(
                'runner audit chain regressions in tests', encoding='utf-8'
            )
            register_hybrid_backend('local', LocalHybridSearchBackend())
            backend = LocalHybridSearchBackend()
            backend.index(
                root=root, args={'include': 'docs/**', 'collection': 'default'}
            )

            pack = build_context_pack(
                'review runner audit chain regressions in tests',
                root=root,
                search_graph=True,
            )
            graph = pack.to_dict()['graph_rag']
            self.assertEqual(graph['status'], 'indexed')
            self.assertEqual(graph['reason'], 'hybrid_search_read')
            self.assertGreaterEqual(len(graph['hits']), 1)
            self.assertIn('docs/runner.md', graph['hits'][0]['path'])

    def test_context_pack_uses_lsp_symbols_when_hydration_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'teaagent' / 'runner.py'
            target.parent.mkdir(parents=True)
            target.write_text('def run():\n    pass\n', encoding='utf-8')

            symbol = MagicMock()
            symbol.kind = 'function'
            symbol.symbol = 'run'
            symbol.line = 0
            symbol.column = 0
            symbol.detail = ''

            manager = MagicMock()
            manager.document_symbols.return_value = [symbol]
            manager.shutdown_all = MagicMock()

            with (
                patch('teaagent.context_pack.LSPServerManager', return_value=manager),
                patch(
                    'teaagent.context_pack._resolve_code_analysis_config',
                    return_value=MagicMock(enabled=True),
                ),
            ):
                pack = build_context_pack(
                    'review teaagent/runner.py for regressions',
                    root=root,
                    hydrate_lsp=True,
                )

            symbols = pack.to_dict()['symbols']
            self.assertEqual(len(symbols), 1)
            self.assertEqual(symbols[0]['reason'], 'lsp_document_symbols')
            self.assertEqual(symbols[0]['symbols'][0]['name'], 'run')


if __name__ == '__main__':
    unittest.main()
