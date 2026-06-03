from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent import MemoryCatalog
from teaagent.cli import main


class MemoryCatalogTests(unittest.TestCase):
    def test_memory_catalog_add_list_search_show(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)

            entry = catalog.add(
                'GraphQLite uses a SQLite extension', tags=('graph', 'sqlite')
            )

            self.assertEqual(catalog.list()[0].memory_id, entry.memory_id)
            self.assertEqual(
                catalog.search('sqlite extension')[0].memory_id, entry.memory_id
            )
            self.assertEqual(catalog.search('graph')[0].tags, ('graph', 'sqlite'))
            self.assertEqual(
                catalog.show(entry.memory_id).content,
                'GraphQLite uses a SQLite extension',
            )

    def test_memory_catalog_skips_malformed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)
            good = catalog.add('Keep this memory', tags=('valid',))
            path = Path(tmp) / '.teaagent' / 'memory.jsonl'
            with path.open('a', encoding='utf-8') as handle:
                handle.write('not json\n')
                handle.write(json.dumps({'content': 'missing id'}) + '\n')
                handle.write(
                    json.dumps({'memory_id': 'bad-tags', 'content': 'x', 'tags': [1]})
                    + '\n'
                )

            entries = catalog.list()

            self.assertEqual([entry.memory_id for entry in entries], [good.memory_id])

    def test_memory_quarantine_list_promote_maintain(self) -> None:
        """Test memory quarantine list, promote, and maintain functions (TASK-005)."""
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)

            # Add a quarantined entry
            quarantined = catalog.add_quarantined(
                'test memory',
                tags=('test',),
                provenance={'reason': 'test', 'source': 'manual'},
            )

            # List quarantined
            quarantined_list = catalog.list_quarantined()
            self.assertEqual(len(quarantined_list), 1)
            self.assertEqual(quarantined_list[0].memory_id, quarantined.memory_id)

            # Test maintain dry run
            report = catalog.maintain_dry_run()
            self.assertEqual(report['quarantined_entries'], 1)
            self.assertIn('quarantined', str(report['recommendations']).lower())

            # Promote quarantined entry
            promoted = catalog.promote_quarantined(
                quarantined.memory_id, attestation='test attestation'
            )
            self.assertEqual(promoted.memory_id, quarantined.memory_id)

            # Verify it's no longer quarantined
            quarantined_after = catalog.list_quarantined()
            self.assertEqual(len(quarantined_after), 0)

            # Verify it's now in main catalog
            main_entries = catalog.list()
            self.assertEqual(len(main_entries), 1)
            self.assertEqual(main_entries[0].memory_id, promoted.memory_id)

    def test_cli_memory_quarantine_commands(self) -> None:
        """Test CLI memory quarantine commands (TASK-005)."""
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as f:
            # Test quarantine list
            with contextlib.suppress(SystemExit):
                main(['memory', 'quarantine', 'list', '--root', tmp])
            output = f.getvalue()
            self.assertIn('[]', output)  # Empty quarantine initially

    def test_cli_memory_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_output = io.StringIO()
            list_output = io.StringIO()
            search_output = io.StringIO()

            with redirect_stdout(add_output):
                add_code = main(
                    [
                        'memory',
                        'add',
                        'Use prompt mode for risky edits',
                        '--tag',
                        'policy',
                        '--root',
                        tmp,
                    ]
                )
            add_payload = json.loads(add_output.getvalue())
            memory_id = add_payload['memory']['memory_id']
            with redirect_stdout(list_output):
                list_code = main(['memory', 'list', '--root', tmp])
            with redirect_stdout(search_output):
                search_code = main(['memory', 'search', 'risky edits', '--root', tmp])

            self.assertEqual(add_code, 0)
            self.assertEqual(list_code, 0)
            self.assertEqual(search_code, 0)
            self.assertEqual(
                json.loads(list_output.getvalue())[0]['memory_id'], memory_id
            )
            self.assertEqual(
                json.loads(search_output.getvalue())[0]['tags'], ['policy']
            )


if __name__ == '__main__':
    unittest.main()
