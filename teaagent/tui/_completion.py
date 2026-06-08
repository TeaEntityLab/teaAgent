"""prompt_toolkit Completer for @-referenced files and symbols."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

_ontology_cache: dict[str, tuple[float, list[str]]] = {}
_ONTOLOGY_CACHE_TTL = 5.0
_index_lock = threading.Lock()
_index_ready = threading.Event()
_background_indexer_started = False


def complete_file_paths(text: str, root: Path) -> list[str]:
    if not text.startswith('@'):
        return []

    partial = text[1:]

    if '/' in partial:
        dir_part, _, file_part = partial.rpartition('/')
        search_dir = root / dir_part
    else:
        dir_part = ''
        file_part = partial
        search_dir = root

    try:
        search_dir = search_dir.resolve()
        if not search_dir.is_dir():
            return []
        _ = search_dir.relative_to(root.resolve())
    except (ValueError, OSError):
        return []

    completions: list[str] = []
    try:
        for item in search_dir.iterdir():
            if item.name.startswith('.') and item.name != '.teaagent':
                continue
            if not item.name.lower().startswith(file_part.lower()):
                continue
            suffix = '/' if item.is_dir() else ''
            if dir_part:
                completions.append(f'@{dir_part}/{item.name}{suffix}')
            else:
                completions.append(f'@{item.name}{suffix}')
    except OSError:
        # Directory may not exist or be inaccessible; gracefully skip completion
        pass

    return sorted(completions)


def _build_ontology_symbols(root: Path) -> list[str]:
    """Build ontology symbols list synchronously (blocking)."""
    from teaagent.code_ontology import CodeOntologyBuilder

    builder = CodeOntologyBuilder(root)
    builder.build_from_directory()
    return sorted({f'@{node.name}' for node in builder.nodes})


def _cache_refresher_worker(root: Path) -> None:
    """Background daemon that periodically refreshes the ontology cache."""
    first_run = True
    while True:
        try:
            now = time.time()
            symbols = _build_ontology_symbols(root)
            root_key = str(root.resolve())
            with _index_lock:
                _ontology_cache[root_key] = (now, symbols)
            if first_run:
                _index_ready.set()
                first_run = False
        except Exception:
            if first_run:
                _index_ready.set()
                first_run = False
        time.sleep(_ONTOLOGY_CACHE_TTL * 2)


def _ensure_background_indexer(root: Path) -> None:
    """Start the background cache refresher thread if not already running."""
    global _background_indexer_started
    with _index_lock:
        if _background_indexer_started:
            return
        _background_indexer_started = True
    t = threading.Thread(target=_cache_refresher_worker, args=(root,), daemon=True)
    t.start()


def _get_cached_symbols(root: Path) -> list[str]:
    """Return all symbol names from code ontology, cached with a TTL."""
    _ensure_background_indexer(root)
    root_key = str(root.resolve())
    now = time.time()

    with _index_lock:
        cached = _ontology_cache.get(root_key)
        if cached is not None and (now - cached[0]) < _ONTOLOGY_CACHE_TTL:
            return cached[1]

    if _index_ready.is_set():
        # Background worker has populated at least once; return empty rather than block
        return []

    # Synchronous fallback for first call before background worker completes
    try:
        symbols = _build_ontology_symbols(root)
        with _index_lock:
            _ontology_cache[root_key] = (now, symbols)
        return symbols
    except Exception:
        return []


def complete_symbols(text: str, root: Path) -> list[str]:
    if not text.startswith('@'):
        return []

    all_symbols = _get_cached_symbols(root)
    return [s for s in all_symbols if s.lower().startswith(text.lower())]


class TeaAgentCompleter(Completer):
    """prompt_toolkit Completer for @file and @symbol workspace references."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> list[Completion]:
        text = document.text_before_cursor
        if not text.startswith('@'):
            return []

        completions = complete_file_paths(text, self._root)
        if not completions:
            completions = complete_symbols(text, self._root)

        return [
            Completion(c, start_position=-(len(c) - len(text))) for c in completions
        ]
