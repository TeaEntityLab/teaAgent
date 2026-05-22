from __future__ import annotations

from pathlib import Path


def whats_new_banner(root: str | Path = '.') -> str | None:
    from teaagent import __version__

    marker = Path(root).resolve() / '.teaagent' / 'seen_version'
    current = __version__
    if marker.is_file() and marker.read_text(encoding='utf-8').strip() == current:
        return None
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(current, encoding='utf-8')
    return f'TeaAgent {current} — see docs/USAGE.md for daily workflows (`teaagent daily`, `teaagent init`).'
