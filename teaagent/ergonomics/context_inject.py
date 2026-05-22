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


def list_at_candidates(
    root: str | Path, *, prefix: str = '', limit: int = 40
) -> list[str]:
    """Return workspace-relative paths suitable for ``@`` injection."""
    root_path = Path(root).resolve()
    matches: list[str] = []
    for path in sorted(root_path.rglob('*')):
        if len(matches) >= limit:
            break
        if not path.is_file():
            continue
        if '.teaagent' in path.parts or path.name.startswith('.'):
            continue
        rel = path.relative_to(root_path).as_posix()
        if prefix and not rel.startswith(prefix):
            continue
        if path.stat().st_size > 512_000:
            continue
        matches.append(rel)
    return matches


def merge_acp_context_blocks(
    task: str, blocks: list[dict[str, Any]], *, max_bytes: int = 32_000
) -> tuple[str, list[dict[str, Any]]]:
    """Append IDE/ACP context blocks (selection, diff, file) to a task preamble."""
    if not blocks:
        return task, []
    parts = [task]
    meta: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        kind = str(block.get('type', 'text'))
        label = str(block.get('label', kind))
        content = block.get('content', block.get('text', ''))
        if not isinstance(content, str) or not content.strip():
            continue
        snippet = content[:max_bytes]
        parts.append(f'\n--- acp: {label} ({kind}) ---\n{snippet}\n--- end ---\n')
        meta.append(
            {'index': index, 'type': kind, 'label': label, 'chars': len(snippet)}
        )
    return ''.join(parts), meta
