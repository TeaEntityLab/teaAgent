from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.context_pack import build_context_pack
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore
from teaagent.hybrid_search import LocalHybridSearchBackend, register_hybrid_backend
from teaagent.memory import MemoryCatalog
from tests.test_graphqlite_store import FakeGraphQLiteGraph


def test_build_context_pack_is_deterministic_for_task_paths() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        root = tmp_path
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
            readonly=True,
        )
        payload = pack.to_dict()

        assert payload['read_only']
        paths = [entry['path'] for entry in payload['candidate_files']]
        assert 'teaagent/preflight.py' in paths
        assert any(entry['exists'] for entry in payload['candidate_files'])
        assert len(payload['memories']) >= 1
        assert len(payload['symbols']) >= 1
        assert payload['graph_rag']['status'] == 'not_indexed'
        assert payload['graph_rag']['reason'] == 'no_index_present'
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_context_pack_only_touches_memory_catalog_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello', encoding='utf-8')
        before = sorted(root.rglob('*'))
        build_context_pack('inspect README.md', root=root)
        after = sorted(root.rglob('*'))
        new_paths = [path for path in after if path not in before]
        assert all('.teaagent' in str(path) for path in new_paths), (
            f'unexpected writes: {new_paths}'
        )


def test_context_pack_includes_hybrid_hits_when_index_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'docs').mkdir()
        readme = root / 'docs' / 'runner.md'
        readme.write_text('runner audit chain regressions in tests', encoding='utf-8')
        register_hybrid_backend('local', LocalHybridSearchBackend())
        backend = LocalHybridSearchBackend()
        backend.index(root=root, args={'include': 'docs/**', 'collection': 'default'})

        pack = build_context_pack(
            'review runner audit chain regressions in tests',
            root=root,
            search_graph=True,
        )
        graph = pack.to_dict()['graph_rag']
        assert graph['status'] == 'indexed'
        assert graph['reason'] == 'hybrid_search_read'
        assert len(graph['hits']) >= 1
        assert 'docs/runner.md' in graph['hits'][0]['path']


def test_context_pack_uses_lsp_symbols_when_hydration_succeeds() -> None:
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
        assert len(symbols) == 1
        assert symbols[0]['reason'] == 'lsp_document_symbols'
        assert symbols[0]['symbols'][0]['name'] == 'run'


def test_context_pack_includes_knowledge_hits_when_marker_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'docs').mkdir()
        doc = root / 'docs' / 'knowledge.md'
        doc.write_text('runner audit chain regressions in tests', encoding='utf-8')
        register_hybrid_backend('local', LocalHybridSearchBackend())
        backend = LocalHybridSearchBackend()
        backend.index(root=root, args={'include': 'docs/**', 'collection': 'knowledge'})
        (root / '.teaagent').mkdir(exist_ok=True)
        (root / '.teaagent' / 'knowledge').write_text(
            json.dumps({'collection': 'knowledge'}), encoding='utf-8'
        )

        pack = build_context_pack(
            'review runner audit chain regressions in tests',
            root=root,
            search_graph=True,
        )
        graph = pack.to_dict()['graph_rag']
        knowledge = graph['sources']['knowledge']

        assert len(knowledge['hits']) >= 1
        assert knowledge['collection'] == 'knowledge'
        assert graph['hits'][0]['source'] == 'knowledge'


def test_context_pack_includes_graphqlite_hits_when_db_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.teaagent').mkdir()
        db_path = root / '.teaagent' / 'graphqlite.db'
        db_path.write_text('', encoding='utf-8')

        class RecordingGraph(FakeGraphQLiteGraph):
            def query(self, cypher: str, params: dict | None = None):
                self.queries.append((cypher, params))
                return [
                    {
                        'doc_id': 'doc-runner',
                        'text': 'runner audit chain regressions in tests',
                        'source': 'graph',
                    }
                ]

        store = GraphQLiteGraphStore(
            GraphQLiteConfig(database=str(db_path)),
            graph_factory=RecordingGraph,
        )

        with patch(
            'teaagent.graphqlite_store.GraphQLiteGraphStore',
            return_value=store,
        ):
            pack = build_context_pack(
                'runner audit chain regressions in tests',
                root=root,
                search_graph=True,
            )

        graph = pack.to_dict()['graph_rag']
        graphqlite = graph['sources']['graphqlite']

        assert len(graphqlite['hits']) >= 1
        assert graphqlite['hits'][0]['doc_id'] == 'doc-runner'
        assert graph['reason'] == 'graphqlite_read'


def test_context_pack_candidate_quality_for_daily_usage_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, text in {
            'teaagent/preflight.py': 'def preflight():\n    return "ready"\n',
            'teaagent/daily.py': 'def build_daily_brief():\n    return "brief"\n',
            'teaagent/runner.py': 'def run():\n    return "run"\n',
        }.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        (root / 'AGENTS.md').write_text(
            'Daily cockpit work should inspect teaagent/daily.py and teaagent/preflight.py.',
            encoding='utf-8',
        )

        pack = build_context_pack(
            'improve daily cockpit token budget in teaagent/daily.py and teaagent/preflight.py',
            root=root,
        )
        paths = [entry['path'] for entry in pack.to_dict()['candidate_files']]

        assert 'teaagent/daily.py' in paths
        assert 'teaagent/preflight.py' in paths
        assert paths.index('teaagent/daily.py') < 3


class TestContextPackNegativeTests:
    """Negative test cases for context_pack edge cases and error conditions."""

    def test_build_context_pack_with_empty_task(self) -> None:
        """Test that empty task is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = build_context_pack('', root=root)
            payload = pack.to_dict()
            # Should still produce a valid pack
            assert 'candidate_files' in payload
            assert 'memories' in payload

    def test_build_context_pack_with_special_characters_in_task(self) -> None:
        """Test that special characters in task are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            special_task = '你好世界🌍\n\t\r\0test'
            pack = build_context_pack(special_task, root=root)
            payload = pack.to_dict()
            assert 'candidate_files' in payload

    def test_build_context_pack_with_very_long_task(self) -> None:
        """Test that very long task is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            long_task = 'x' * 100000
            pack = build_context_pack(long_task, root=root)
            payload = pack.to_dict()
            assert 'candidate_files' in payload

    def test_build_context_pack_with_empty_directory(self) -> None:
        """Test that empty directory is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should produce empty candidate list
            assert len(payload['candidate_files']) == 0

    def test_build_context_pack_with_permission_denied_directory(self) -> None:
        """Test that permission errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readonly = root / 'readonly'
            readonly.mkdir()
            readonly.chmod(0o000)

            try:
                pack = build_context_pack('test', root=readonly)
                # Should handle gracefully
                assert pack is not None
            except PermissionError:
                # Permission errors are expected for readonly directories
                pass
            finally:
                readonly.chmod(0o755)

    def test_build_context_pack_with_symlink_loops(self) -> None:
        """Test that symlink loops are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a symlink loop
            link = root / 'loop'
            link.symlink_to(root)

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should not hang or crash
            assert 'candidate_files' in payload

    def test_build_context_pack_with_corrupted_memory_catalog(self) -> None:
        """Test that corrupted memory catalog is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'memory').write_text(
                'corrupted json{', encoding='utf-8'
            )

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_invalid_lsp_config(self) -> None:
        """Test that invalid LSP config is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'code_analysis.json').write_text(
                'invalid json', encoding='utf-8'
            )

            pack = build_context_pack('test', root=root, hydrate_lsp=True)
            payload = pack.to_dict()
            # Should handle gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_invalid_hybrid_config(self) -> None:
        """Test that invalid hybrid search config is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'hybrid_search.json').write_text(
                'invalid json', encoding='utf-8'
            )

            pack = build_context_pack('test', root=root, search_graph=True)
            payload = pack.to_dict()
            # Should handle gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_binary_files(self) -> None:
        """Test that binary files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary_file = root / 'binary.bin'
            binary_file.write_bytes(b'\x00\x01\x02\x03\xff\xfe')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle binary files gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_very_deep_directory_structure(self) -> None:
        """Test that very deep directory structures are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deep_path = root
            for i in range(50):
                deep_path = deep_path / f'level{i}'
                deep_path.mkdir(exist_ok=True)

            file_at_bottom = deep_path / 'file.txt'
            file_at_bottom.write_text('deep file', encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle deep structures
            assert 'candidate_files' in payload

    def test_build_context_pack_with_zero_length_files(self) -> None:
        """Test that zero-length files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty_file = root / 'empty.txt'
            empty_file.write_text('', encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle empty files
            assert 'candidate_files' in payload

    def test_build_context_pack_with_mixed_line_endings(self) -> None:
        """Test that files with mixed line endings are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mixed_file = root / 'mixed.py'
            mixed_file.write_text('line1\nline2\r\nline3\r', encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle mixed line endings
            assert 'candidate_files' in payload

    def test_build_context_pack_with_bom_encoding(self) -> None:
        """Test that files with BOM encoding are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bom_file = root / 'bom.py'
            bom_file.write_bytes(b'\xef\xbb\xbfprint("hello")')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle BOM encoding
            assert 'candidate_files' in payload

    def test_build_context_pack_with_special_file_types(self) -> None:
        """Test that special file types (sockets, pipes) are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a FIFO (named pipe) if supported
            try:
                fifo_path = root / 'fifo'
                import os

                os.mkfifo(fifo_path)
            except (OSError, AttributeError):
                # Skip if not supported
                pytest.skip('Named pipes not supported on this platform')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle special file types gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_corrupted_git_repo(self) -> None:
        """Test that corrupted git repository is handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.git').mkdir()
            (root / '.git' / 'config').write_text(
                'corrupted git config', encoding='utf-8'
            )

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle corrupted git gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_null_bytes_in_task(self) -> None:
        """Test that null bytes in task are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_with_null = 'test\x00task'
            pack = build_context_pack(task_with_null, root=root)
            payload = pack.to_dict()
            # Should handle null bytes gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_emoji_in_task(self) -> None:
        """Test that emoji in task are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emoji_task = 'test 🔐🔑 task 🚀'
            pack = build_context_pack(emoji_task, root=root)
            payload = pack.to_dict()
            # Should handle emoji correctly
            assert 'candidate_files' in payload

    def test_build_context_pack_with_control_characters_in_task(self) -> None:
        """Test that control characters in task are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            control_task = 'test\x01\x02\x03task'
            pack = build_context_pack(control_task, root=root)
            payload = pack.to_dict()
            # Should handle control characters gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_very_large_file(self) -> None:
        """Test that very large files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            large_file = root / 'large.txt'
            # Write a 10MB file
            large_file.write_text('x' * (10 * 1024 * 1024), encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle large files gracefully
            assert 'candidate_files' in payload

    def test_build_context_pack_with_many_files(self) -> None:
        """Test that directories with many files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create 1000 files
            for i in range(1000):
                file_path = root / f'file{i}.txt'
                file_path.write_text(f'content {i}', encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle many files
            assert 'candidate_files' in payload

    def test_build_context_pack_with_hidden_files(self) -> None:
        """Test that hidden files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden_file = root / '.hidden.py'
            hidden_file.write_text('print("hidden")', encoding='utf-8')

            pack = build_context_pack('test', root=root)
            payload = pack.to_dict()
            # Should handle hidden files
            assert 'candidate_files' in payload

    def test_build_context_pack_with_readonly_files(self) -> None:
        """Test that readonly files are handled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readonly_file = root / 'readonly.py'
            readonly_file.write_text('print("readonly")', encoding='utf-8')
            readonly_file.chmod(0o444)

            try:
                pack = build_context_pack('test', root=root)
                payload = pack.to_dict()
                # Should handle readonly files
                assert 'candidate_files' in payload
            except PermissionError:
                # Permission errors are expected for readonly files
                pass
            finally:
                readonly_file.chmod(0o644)
