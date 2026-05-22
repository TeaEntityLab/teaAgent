from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_AT_REF = re.compile(r'@([\w./\-]+)')


def expand_at_references(
    task: str, *, root: str | Path, max_bytes: int = 32_000
) -> tuple[str, list[dict[str, Any]]]:
    """Expand ``@path`` references in a task string with file excerpts."""
    root_path = Path(root).resolve()
    injections: list[dict[str, Any]] = []
    expanded = task

    def _replace(match: re.Match[str]) -> str:
        rel = match.group(1)
        path = (root_path / rel).resolve()
        if not path.is_file() or root_path not in path.parents and path != root_path:
            injections.append({'path': rel, 'error': 'not found'})
            return match.group(0)
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            injections.append({'path': rel, 'error': str(exc)})
            return match.group(0)
        snippet = text[:max_bytes]
        injections.append(
            {'path': rel, 'bytes': len(text), 'snippet_chars': len(snippet)}
        )
        return f'{match.group(0)}\n\n--- context: {rel} ---\n{snippet}\n--- end ---\n'

    expanded = _AT_REF.sub(_replace, expanded)
    return expanded, injections
