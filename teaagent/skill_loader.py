"""Skill loader — discovers and injects SKILL.md content into agent prompts.

The loader searches a priority-ordered list of directories for skill packages.
A skill package is any subdirectory that contains a ``SKILL.md`` file.

Default search order (first match wins per skill name):

1. ``<workspace_root>/.opencode/skill/``  — project-level skills
2. ``~/.config/opencode/skills/``         — user-level skills

Usage in ``assemble_agent_prompt``::

    from teaagent.skill_loader import load_skills

    active_skills = load_skills(root=workspace_root)
    # active_skills is a list of SkillContent(name, path, content)

The caller is responsible for injecting the content into the prompt;
``assemble_agent_prompt`` accepts a ``skills`` keyword argument that appends
each skill block under a "Skills:" section in the system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DEFAULT_SKILL_DIRS = [
    '.opencode/skill',
]
_USER_SKILL_DIR = Path.home() / '.config' / 'opencode' / 'skills'
_SKILL_FILENAME = 'SKILL.md'
_MAX_SKILL_BYTES = 32_768  # 32 KB per skill — guard against runaway includes


@dataclass(frozen=True)
class SkillContent:
    """A loaded skill ready for prompt injection."""

    name: str
    path: Path
    content: str


def _discover_skill_dirs(root: Path) -> list[Path]:
    """Return an ordered list of skill search directories that exist."""
    candidates: list[Path] = []
    for rel in _DEFAULT_SKILL_DIRS:
        p = root / rel
        if p.is_dir():
            candidates.append(p)
    if _USER_SKILL_DIR.is_dir():
        candidates.append(_USER_SKILL_DIR)
    return candidates


def load_skills(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    max_skills: int = 20,
) -> list[SkillContent]:
    """Discover and load all SKILL.md files reachable from *root*.

    Parameters
    ----------
    root:
        Workspace root directory.  Used to resolve ``.opencode/skill/``.
    extra_skill_dirs:
        Additional directories to search after the defaults.
    max_skills:
        Hard cap on the number of skills loaded (prevents prompt bloat).

    Returns
    -------
    list[SkillContent]
        Loaded skills, deduplicated by name (first occurrence wins).
    """
    root_path = Path(root).resolve()
    skill_dirs = _discover_skill_dirs(root_path)
    if extra_skill_dirs:
        skill_dirs.extend(extra_skill_dirs)

    seen_names: set[str] = set()
    results: list[SkillContent] = []

    for skill_dir in skill_dirs:
        if len(results) >= max_skills:
            break
        try:
            entries = sorted(skill_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            if len(results) >= max_skills:
                break
            if not entry.is_dir():
                continue
            skill_file = entry / _SKILL_FILENAME
            if not skill_file.is_file():
                continue
            name = entry.name
            if name in seen_names:
                continue  # first occurrence (project > user) wins
            try:
                raw = skill_file.read_bytes()
                if len(raw) > _MAX_SKILL_BYTES:
                    raw = raw[:_MAX_SKILL_BYTES]
                content = raw.decode('utf-8', errors='replace')
            except OSError:
                continue
            results.append(SkillContent(name=name, path=skill_file, content=content))
            seen_names.add(name)

    return results


def skills_to_prompt_section(skills: list[SkillContent]) -> str:
    """Render loaded skills as a prompt section string.

    Returns an empty string when no skills are provided.
    """
    if not skills:
        return ''
    parts = ['Skills:']
    for skill in skills:
        parts.append(f'--- skill: {skill.name} ---')
        parts.append(skill.content.strip())
    return '\n\n'.join(parts)
