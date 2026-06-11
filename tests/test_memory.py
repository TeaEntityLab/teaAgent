from __future__ import annotations

import contextlib
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4

from teaagent import MemoryCatalog
from teaagent.cli import main


def test_memory_catalog_add_list_search_show() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)

        entry = catalog.add(
            'GraphQLite uses a SQLite extension', tags=('graph', 'sqlite')
        )

        assert catalog.list()[0].memory_id == entry.memory_id
        assert catalog.search('sqlite extension')[0].memory_id == entry.memory_id
        assert catalog.search('graph')[0].tags == ('graph', 'sqlite')
        assert (
            catalog.show(entry.memory_id).content
            == 'GraphQLite uses a SQLite extension'
        )


def test_memory_catalog_skips_malformed_entries() -> None:
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

        assert [entry.memory_id for entry in entries] == [good.memory_id]


def test_memory_catalog_health_report_tracks_corrupt_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        # Add a valid entry
        catalog.add('valid memory entry')
        # Write a corrupt line to memory.jsonl
        memory_file = Path(tmp) / '.teaagent' / 'memory.jsonl'
        with memory_file.open('a', encoding='utf-8') as f:
            f.write('not valid json\n')

        report = catalog.health_report()
        assert report['corrupt_entries'] == 1
        assert report['total_entries'] == 1
        assert not report['healthy']


def test_memory_catalog_refreshes_after_external_update() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        first = catalog.add('first memory entry', tags=('alpha',))

        # Prime the cache with an initial read.
        assert catalog.list()[0].memory_id == first.memory_id

        memory_file = Path(tmp) / '.teaagent' / 'memory.jsonl'
        second = {
            'memory_id': uuid4().hex,
            'content': 'second memory entry',
            'tags': ['beta'],
            'created_at': first.created_at,
            'branch_name': None,
            'run_id': None,
        }
        with memory_file.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(second, sort_keys=True) + '\n')

        entries = catalog.list()
        assert entries[0].content == 'second memory entry'
        assert entries[1].memory_id == first.memory_id
        assert catalog.search('second memory')[0].content == 'second memory entry'


def test_memory_quarantine_list_promote_maintain() -> None:
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
        assert len(quarantined_list) == 1
        assert quarantined_list[0].memory_id == quarantined.memory_id

        # Test maintain dry run
        report = catalog.maintain_dry_run()
        assert report['quarantined_entries'] == 1
        assert 'quarantined' in str(report['recommendations']).lower()

        # Promote quarantined entry
        promoted = catalog.promote_quarantined(
            quarantined.memory_id, attestation='test attestation'
        )
        assert promoted.memory_id == quarantined.memory_id

        # Verify it's no longer quarantined
        quarantined_after = catalog.list_quarantined()
        assert len(quarantined_after) == 0

        # Verify it's now in main catalog
        main_entries = catalog.list()
        assert len(main_entries) == 1
        assert main_entries[0].memory_id == promoted.memory_id


def test_cli_memory_quarantine_commands() -> None:
    """Test CLI memory quarantine commands (TASK-005)."""
    with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as f:
        # Test quarantine list
        with contextlib.suppress(SystemExit):
            main(['memory', 'quarantine', 'list', '--root', tmp])
        output = f.getvalue()
        assert '[]' in output  # Empty quarantine initially


def test_cli_memory_commands() -> None:
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

        assert add_code == 0
        assert list_code == 0
        assert search_code == 0
        assert json.loads(list_output.getvalue())[0]['memory_id'] == memory_id
        assert json.loads(search_output.getvalue())[0]['tags'] == ['policy']
