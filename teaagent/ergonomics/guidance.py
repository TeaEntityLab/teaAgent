from __future__ import annotations

from pathlib import Path
from typing import Any

GUIDANCE_FILENAMES = (
    'AGENTS.md',
    'GEMINI.md',
    '.openhands_instructions',
    '.teaagent/guide.md',
)


def collect_workspace_guidance(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    files: list[dict[str, Any]] = []
    for name in GUIDANCE_FILENAMES:
        path = root_path / name
        if path.is_file():
            files.append(
                {'path': str(path.relative_to(root_path)), 'bytes': path.stat().st_size}
            )
    subdirs = []
    for child in sorted(root_path.iterdir()):
        if not child.is_dir() or child.name.startswith('.'):
            continue
        agents = child / 'AGENTS.md'
        if agents.is_file():
            subdirs.append(str(agents.relative_to(root_path)))
    return {
        'convention': 'Place AGENTS.md at repo root; optional per-subdir AGENTS.md overrides.',
        'files': files,
        'subdir_overrides': subdirs,
    }
