"""Tests for teaagent.tui._completion module.

Covers:
- complete_file_paths: @-prefixed file path completion
- _get_cached_symbols: ontology symbol caching with TTL and background refresher
- complete_symbols: @-prefixed symbol completion
- TeaAgentCompleter: prompt_toolkit Completer subclass
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document

from teaagent.tui import _completion

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_global_state() -> None:
    """Reset module-level state between tests.

    _completion uses module-level globals (_ontology_cache,
    _background_indexer_started, and threading primitives). We must clear them
    before each test to avoid cross-test contamination.
    """
    _completion._ontology_cache.clear()
    _completion._background_indexer_started = False
    _completion._index_ready.clear()
    yield


# ---------------------------------------------------------------------------
# complete_file_paths
# ---------------------------------------------------------------------------


class TestCompleteFilePaths:
    """Tests for complete_file_paths(text, root)."""

    def test_returns_empty_when_text_does_not_start_with_at(
        self, tmp_path: Path
    ) -> None:
        assert _completion.complete_file_paths('foo', tmp_path) == []

    def test_returns_empty_when_only_at_symbol(self, tmp_path: Path) -> None:
        assert _completion.complete_file_paths('@', tmp_path) == []

    def test_returns_matching_files_from_root(self, tmp_path: Path) -> None:
        (tmp_path / 'file_a.txt').touch()
        (tmp_path / 'file_b.txt').touch()
        (tmp_path / 'other.md').touch()

        result = _completion.complete_file_paths('@file', tmp_path)

        assert sorted(result) == ['@file_a.txt', '@file_b.txt']

    def test_returns_all_files_with_at_only(self, tmp_path: Path) -> None:
        (tmp_path / 'alpha.py').touch()
        (tmp_path / 'beta.py').touch()

        result = _completion.complete_file_paths('@', tmp_path)

        assert sorted(result) == ['@alpha.py', '@beta.py']

    def test_handles_subdirectory_paths(self, tmp_path: Path) -> None:
        sub = tmp_path / 'subdir'
        sub.mkdir()
        (sub / 'nested.py').touch()

        result = _completion.complete_file_paths('@subdir/', tmp_path)

        assert result == ['@subdir/nested.py']

    def test_completes_partial_subdirectory_name(self, tmp_path: Path) -> None:
        sub = tmp_path / 'mydir'
        sub.mkdir()
        (sub / 'inner.py').touch()

        result = _completion.complete_file_paths('@my', tmp_path)

        assert '@mydir/' in result

    def test_appends_trailing_slash_for_directories(self, tmp_path: Path) -> None:
        (tmp_path / 'somedir').mkdir()
        (tmp_path / 'file.py').touch()

        result = _completion.complete_file_paths('@some', tmp_path)

        assert '@somedir/' in result

    def test_skips_dotfiles_except_teaagent(self, tmp_path: Path) -> None:
        (tmp_path / '.hidden').touch()
        (tmp_path / '.teaagent').touch()
        (tmp_path / 'visible.py').touch()

        result = _completion.complete_file_paths('@', tmp_path)

        assert '.teaagent' in str(result)
        assert '.hidden' not in str(result)
        assert 'visible.py' in str(result)

    def test_returns_empty_for_nonexistent_directory(self, tmp_path: Path) -> None:
        result = _completion.complete_file_paths('@nonexistent/', tmp_path)
        assert result == []

    def test_returns_empty_for_paths_outside_root(self, tmp_path: Path) -> None:
        result = _completion.complete_file_paths('@../', tmp_path)
        assert result == []

    def test_returns_empty_for_path_traversal_with_prefix(self, tmp_path: Path) -> None:
        result = _completion.complete_file_paths('@../etc/', tmp_path)
        assert result == []

    def test_returns_sorted_completions(self, tmp_path: Path) -> None:
        (tmp_path / 'z_file.py').touch()
        (tmp_path / 'a_file.py').touch()
        (tmp_path / 'm_file.py').touch()

        result = _completion.complete_file_paths('@', tmp_path)

        assert result == ['@a_file.py', '@m_file.py', '@z_file.py']

    def test_matches_case_insensitively(self, tmp_path: Path) -> None:
        (tmp_path / 'File.TXT').touch()
        (tmp_path / 'file.md').touch()

        result = _completion.complete_file_paths('@FILE', tmp_path)

        names = [c.split('@', 1)[1] for c in result]
        assert all(n.lower().startswith('file') for n in names)

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        empty = tmp_path / 'empty'
        empty.mkdir()

        result = _completion.complete_file_paths('@empty/', tmp_path)
        assert result == []

    def test_handles_deeply_nested_paths(self, tmp_path: Path) -> None:
        nested = tmp_path / 'a' / 'b' / 'c'
        nested.mkdir(parents=True)
        (nested / 'target.py').touch()

        result = _completion.complete_file_paths('@a/b/c/target', tmp_path)

        assert result == ['@a/b/c/target.py']

    def test_handles_partial_nested_paths(self, tmp_path: Path) -> None:
        nested = tmp_path / 'a' / 'b'
        nested.mkdir(parents=True)
        (nested / 'deep.py').touch()

        result = _completion.complete_file_paths('@a/b/de', tmp_path)

        assert result == ['@a/b/deep.py']

    def test_graceful_on_unreadable_directory(self, tmp_path: Path) -> None:
        """Should not raise when a directory is inaccessible."""
        bad_dir = tmp_path / 'bad'
        bad_dir.mkdir()
        bad_dir.chmod(0o000)

        try:
            result = _completion.complete_file_paths('@bad/', tmp_path)
            assert result == []
        finally:
            bad_dir.chmod(0o755)  # Restore for cleanup


# ---------------------------------------------------------------------------
# _get_cached_symbols
# ---------------------------------------------------------------------------


class TestGetCachedSymbols:
    """Tests for _get_cached_symbols(root)."""

    @classmethod
    def _no_background(cls):
        """Patch _ensure_background_indexer to prevent daemon thread from racing."""
        return patch.object(_completion, '_ensure_background_indexer')

    def test_falls_back_to_sync_build_on_first_call(self, tmp_path: Path) -> None:
        """First call before background worker completes uses sync fallback."""
        expected = ['@func_x', '@class_y']

        with (
            patch.object(
                _completion, '_build_ontology_symbols', return_value=expected
            ) as mock_build,
            self._no_background(),
        ):
            result = _completion._get_cached_symbols(tmp_path)

        assert result == expected
        mock_build.assert_called_once()

    def test_caches_results_and_returns_cached_within_ttl(self, tmp_path: Path) -> None:
        """Subsequent calls within TTL return cached symbols without rebuild."""
        symbols_a = ['@func_a', '@class_b']

        with (
            patch.object(
                _completion, '_build_ontology_symbols', return_value=symbols_a
            ),
            self._no_background(),
        ):
            _completion._get_cached_symbols(tmp_path)  # Populates cache

        # Second call — cache is fresh, should return cached value
        root_key = str(tmp_path.resolve())
        assert root_key in _completion._ontology_cache

    def test_returns_empty_when_cache_miss_and_background_ready(
        self, tmp_path: Path
    ) -> None:
        """When no cache exists and background worker is already ready, return []."""
        _completion._ontology_cache.clear()

        with (
            patch.object(_completion, '_index_ready') as mock_ready,
            self._no_background(),
        ):
            mock_ready.is_set.return_value = True
            result = _completion._get_cached_symbols(tmp_path)

        assert result == []

    def test_returns_cached_after_background_worker_populated(
        self, tmp_path: Path
    ) -> None:
        """Once cache is populated, subsequent calls return it regardless of ready state."""
        cached = ['@cached_func']

        with (
            patch.object(_completion, '_build_ontology_symbols', return_value=cached),
            self._no_background(),
        ):
            _completion._get_cached_symbols(tmp_path)

        with patch.object(_completion, '_index_ready') as mock_ready:
            mock_ready.is_set.return_value = True
            result = _completion._get_cached_symbols(tmp_path)

        assert result == cached

    def test_handles_sync_build_exception_gracefully(self, tmp_path: Path) -> None:
        """Returns empty list when sync build raises an exception."""
        with (
            patch.object(
                _completion,
                '_build_ontology_symbols',
                side_effect=Exception('build error'),
            ),
            self._no_background(),
        ):
            result = _completion._get_cached_symbols(tmp_path)

        assert result == []

    def test_expired_cache_entry_has_old_timestamp(self, tmp_path: Path) -> None:
        """Verify that overwriting cache with old timestamp makes entry appear expired."""
        symbols = ['@old_func']

        with (
            patch.object(_completion, '_build_ontology_symbols', return_value=symbols),
            self._no_background(),
        ):
            _completion._get_cached_symbols(tmp_path)

        root_key = str(tmp_path.resolve())
        old_time = 0.0
        _completion._ontology_cache[root_key] = (old_time, symbols)

        entry = _completion._ontology_cache[root_key]
        assert entry[0] == 0.0
        assert entry[1] == symbols

    def test_background_indexer_not_started_twice(self, tmp_path: Path) -> None:
        """Subsequent calls do not start another indexer thread."""
        _completion._background_indexer_started = True

        with (
            patch.object(_completion, '_build_ontology_symbols', return_value=[]),
            patch.object(_completion, '_ensure_background_indexer') as mock_ensure,
        ):
            _completion._get_cached_symbols(tmp_path)

        # _ensure_background_indexer is called but should no-op since already started
        mock_ensure.assert_called_once()

    def test_uses_per_root_cache_key(self, tmp_path: Path) -> None:
        """Different roots have separate cache entries."""
        root_a = tmp_path / 'a'
        root_b = tmp_path / 'b'
        root_a.mkdir()
        root_b.mkdir()

        symbols_a = ['@from_a']
        symbols_b = ['@from_b']

        with (
            patch.object(
                _completion, '_build_ontology_symbols', return_value=symbols_a
            ),
            patch.object(_completion, '_ensure_background_indexer'),
        ):
            _completion._get_cached_symbols(root_a)
        with (
            patch.object(
                _completion, '_build_ontology_symbols', return_value=symbols_b
            ),
            patch.object(_completion, '_ensure_background_indexer'),
        ):
            _completion._get_cached_symbols(root_b)

        # Verify both cached entries exist
        assert len(_completion._ontology_cache) == 2


# ---------------------------------------------------------------------------
# complete_symbols
# ---------------------------------------------------------------------------


class TestCompleteSymbols:
    """Tests for complete_symbols(text, root)."""

    def test_returns_empty_when_text_does_not_start_with_at(
        self, tmp_path: Path
    ) -> None:
        result = _completion.complete_symbols('no_at_prefix', tmp_path)
        assert result == []

    def test_returns_matching_symbols(self, tmp_path: Path) -> None:
        expected = ['@func_a', '@func_b', '@class_c']

        with patch.object(_completion, '_get_cached_symbols', return_value=expected):
            result = _completion.complete_symbols('@func', tmp_path)

        assert result == ['@func_a', '@func_b']

    def test_matches_case_insensitively(self, tmp_path: Path) -> None:
        symbols = ['@FuncA', '@funcB']

        with patch.object(_completion, '_get_cached_symbols', return_value=symbols):
            result = _completion.complete_symbols('@func', tmp_path)

        assert sorted(result) == sorted(['@FuncA', '@funcB'])

    def test_returns_empty_when_no_match(self, tmp_path: Path) -> None:
        symbols = ['@func_a', '@class_b']

        with patch.object(_completion, '_get_cached_symbols', return_value=symbols):
            result = _completion.complete_symbols('@other', tmp_path)

        assert result == []

    def test_returns_all_symbols_with_bare_at(self, tmp_path: Path) -> None:
        symbols = ['@func_a', '@class_b', '@var_c']

        with patch.object(_completion, '_get_cached_symbols', return_value=symbols):
            result = _completion.complete_symbols('@', tmp_path)

        assert sorted(result) == sorted(symbols)

    def test_returns_empty_when_no_symbols_available(self, tmp_path: Path) -> None:
        with patch.object(_completion, '_get_cached_symbols', return_value=[]):
            result = _completion.complete_symbols('@anything', tmp_path)

        assert result == []

    def test_delegates_to_get_cached_symbols(self, tmp_path: Path) -> None:
        with patch.object(
            _completion, '_get_cached_symbols', return_value=[]
        ) as mock_get:
            _completion.complete_symbols('@test', tmp_path)

        mock_get.assert_called_once_with(tmp_path)


# ---------------------------------------------------------------------------
# TeaAgentCompleter
# ---------------------------------------------------------------------------


class TestTeaAgentCompleter:
    """Tests for TeaAgentCompleter."""

    def test_get_completions_returns_completion_objects(self, tmp_path: Path) -> None:
        (tmp_path / 'file_a.py').touch()

        completer = _completion.TeaAgentCompleter(tmp_path)
        doc = Document(text='@file')
        event = CompleteEvent()

        result = completer.get_completions(doc, event)

        assert len(result) >= 1
        assert all(isinstance(c, Completion) for c in result)

    def test_returns_matching_file_completions(self, tmp_path: Path) -> None:
        (tmp_path / 'target.py').touch()
        (tmp_path / 'other.py').touch()

        completer = _completion.TeaAgentCompleter(tmp_path)
        doc = Document(text='@target')
        event = CompleteEvent()

        result = completer.get_completions(doc, event)

        assert len(result) == 1
        assert result[0].text == '@target.py'

    def test_falls_back_to_symbols_when_no_files_match(self, tmp_path: Path) -> None:
        symbols = ['@symbol_func']

        with patch.object(_completion, 'complete_symbols', return_value=symbols):
            completer = _completion.TeaAgentCompleter(tmp_path)
            doc = Document(text='@sym')
            event = CompleteEvent()

            result = completer.get_completions(doc, event)

            assert len(result) == 1
            assert result[0].text == '@symbol_func'

    def test_returns_empty_when_text_does_not_start_with_at(
        self, tmp_path: Path
    ) -> None:
        completer = _completion.TeaAgentCompleter(tmp_path)
        doc = Document(text='no_at')
        event = CompleteEvent()

        result = completer.get_completions(doc, event)

        assert result == []

    def test_sets_start_position_to_replace_partial_text(self, tmp_path: Path) -> None:
        (tmp_path / 'myfile.py').touch()

        completer = _completion.TeaAgentCompleter(tmp_path)
        doc = Document(text='@myf')
        event = CompleteEvent()

        result = completer.get_completions(doc, event)

        assert len(result) == 1
        c = result[0]
        # start_position = -(len(completion_text) - len(text_before_cursor))
        expected = -(len('@myfile.py') - len('@myf'))
        assert c.start_position == expected

    def test_file_completions_take_priority_over_symbols(self, tmp_path: Path) -> None:
        """File completions should be returned first; symbols are fallback only."""
        (tmp_path / 'priority.py').touch()

        with patch.object(
            _completion, 'complete_symbols', return_value=['@priority']
        ) as mock_sym:
            completer = _completion.TeaAgentCompleter(tmp_path)
            doc = Document(text='@priority')
            event = CompleteEvent()

            result = completer.get_completions(doc, event)

            # File completion wins, symbols not consulted
            assert len(result) >= 1
            assert result[0].text == '@priority.py'
            mock_sym.assert_not_called()

    def test_stores_root_parameter(self, tmp_path: Path) -> None:
        completer = _completion.TeaAgentCompleter(tmp_path)
        assert completer._root == tmp_path
