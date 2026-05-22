from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.context_pack import build_context_pack
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
            self.assertEqual(
                payload['graph_rag']['reason'], 'read_only_preflight_no_search'
            )

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


if __name__ == '__main__':
    unittest.main()
