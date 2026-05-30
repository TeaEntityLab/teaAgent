"""prompt_toolkit Completer for @-referenced files and symbols."""

from __future__ import annotations

import time
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

_ontology_cache: dict[str, tuple[float, list[str]]] = {}
_ONTOLOGY_CACHE_TTL = 5.0


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


def _get_cached_symbols(root: Path) -> list[str]:
    """Return all symbol names from code ontology, cached with a TTL."""
    root_key = str(root.resolve())
    now = time.time()
    cached = _ontology_cache.get(root_key)
    if cached is not None and (now - cached[0]) < _ONTOLOGY_CACHE_TTL:
        return cached[1]
    try:
        from teaagent.code_ontology import CodeOntologyBuilder

        builder = CodeOntologyBuilder(root)
        builder.build_from_directory()
        symbols = sorted({f'@{node.name}' for node in builder.nodes})
        _ontology_cache[root_key] = (now, symbols)
        return symbols
    except Exception:
        return []


def complete_symbols(text: str, root: Path) -> list[str]:
    if not text.startswith('@'):
        return []

    partial = text[1:]
    all_symbols = _get_cached_symbols(root)
    return [s for s in all_symbols if s.lower().startswith(partial.lower())]


class TeaAgentCompleter(Completer):
    """prompt_toolkit Completer for @file and @symbol workspace references."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> list[Completion]:
        text = document.text_before_cursor
        if not text.startswith('@'):
            return []

        completions = complete_file_paths(text, self._root)
        if not completions:
            completions = complete_symbols(text, self._root)

        return [
            Completion(c, start_position=-(len(c) - len(text)))
            for c in completions
        ]
