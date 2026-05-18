"""Skill loader — discovers and injects SKILL.md content into agent prompts.

The loader searches a priority-ordered list of directories for skill packages.
A skill package is any subdirectory that contains a ``SKILL.md`` file.

Default search order (first match wins per skill name):

1. ``<workspace_root>/.config/agent/skills/``  — project agent config
2. ``<workspace_root>/.claude/skills/``        — project Claude-compatible
3. ``<workspace_root>/.opencode/skill/``       — project OpenCode
4. ``<workspace_root>/.opencode/skills/``      — project OpenCode alias
5. ``~/.config/agent/skills/``                 — user agent config
6. ``~/.claude/skills/``                       — user Claude-compatible
7. ``~/.config/opencode/skills/``              — user OpenCode

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
from typing import Literal, Optional

from teaagent.skill_review import SkillReviewResult, review_skill

_PROJECT_SKILL_DIRS = [
    '.config/agent/skills',
    '.claude/skills',
    '.opencode/skill',
    '.opencode/skills',
]
_USER_SKILL_DIRS = [
    Path.home() / '.config' / 'agent' / 'skills',
    Path.home() / '.claude' / 'skills',
    Path.home() / '.config' / 'opencode' / 'skills',
]
_EXTENDED_PROJECT_SKILL_DIRS = [
    '.codex/skills',
    '.gemini/skills',
    '.hermes/skills',
]
_EXTENDED_USER_SKILL_DIRS = [
    Path.home() / '.codex' / 'skills',
    Path.home() / '.gemini' / 'skills',
    Path.home() / '.hermes' / 'skills',
]
_SKILL_FILENAME = 'SKILL.md'
_MAX_SKILL_BYTES = 32_768  # 32 KB per skill — guard against runaway includes


@dataclass(frozen=True)
class SkillContent:
    """A loaded skill ready for prompt injection."""

    name: str
    path: Path
    content: str


@dataclass(frozen=True)
class SkillLoadWarning:
    skill_name: str
    skill_path: Path
    message: str


@dataclass(frozen=True)
class SkillLoadSkipped:
    skill_name: str
    skill_path: Path
    reason: str
    review: Optional[SkillReviewResult] = None


@dataclass(frozen=True)
class SkillLoadReport:
    skills: list[SkillContent]
    searched_dirs: list[Path]
    warnings: list[SkillLoadWarning]
    skipped: list[SkillLoadSkipped]


SkillSourceProfile = Literal['default', 'extended', 'custom']


def _dirs_for_profile(profile: SkillSourceProfile) -> tuple[list[str], list[Path]]:
    if profile == 'extended':
        return (
            _PROJECT_SKILL_DIRS + _EXTENDED_PROJECT_SKILL_DIRS,
            _USER_SKILL_DIRS + _EXTENDED_USER_SKILL_DIRS,
        )
    return (_PROJECT_SKILL_DIRS, _USER_SKILL_DIRS)


def _discover_skill_dirs(
    root: Path,
    *,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> list[Path]:
    """Return an ordered list of skill search directories that exist."""
    if preferred_dirs is not None:
        candidates: list[Path] = []
        for raw_path in preferred_dirs:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = root / candidate
            if candidate.is_dir():
                candidates.append(candidate.resolve())
        return candidates

    project_dirs, user_dirs = _dirs_for_profile(source_profile)
    result: list[Path] = []
    for rel in project_dirs:
        p = root / rel
        if p.is_dir():
            result.append(p)
    for user_dir in user_dirs:
        if user_dir.is_dir():
            result.append(user_dir)
    return result


def discover_skill_search_dirs(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> list[Path]:
    """Return the ordered list of skill directories used for discovery."""
    root_path = Path(root).resolve()
    skill_dirs = _discover_skill_dirs(
        root_path, preferred_dirs=preferred_dirs, source_profile=source_profile
    )
    if extra_skill_dirs:
        skill_dirs.extend(extra_skill_dirs)
    return skill_dirs


def load_skills(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    max_skills: int = 20,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> list[SkillContent]:
    return load_skills_with_report(
        root,
        extra_skill_dirs=extra_skill_dirs,
        max_skills=max_skills,
        preferred_dirs=preferred_dirs,
        source_profile=source_profile,
    ).skills


def load_skills_with_report(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    max_skills: int = 20,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> SkillLoadReport:
    """Discover and load all SKILL.md files reachable from *root*.

    Parameters
    ----------
    root:
        Workspace root directory. Used to resolve project-local skill directories.
    extra_skill_dirs:
        Additional directories to search after the defaults.
    max_skills:
        Hard cap on the number of skills loaded (prevents prompt bloat).

    Returns
    -------
    list[SkillContent]
        Loaded skills, deduplicated by name (first occurrence wins).
    """
    skill_dirs = discover_skill_search_dirs(
        root,
        extra_skill_dirs=extra_skill_dirs,
        preferred_dirs=preferred_dirs,
        source_profile=source_profile,
    )

    seen_names: set[str] = set()
    results: list[SkillContent] = []
    warnings: list[SkillLoadWarning] = []
    skipped: list[SkillLoadSkipped] = []

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
            review = review_skill(skill_file)
            if not review.passed:
                skipped.append(
                    SkillLoadSkipped(
                        skill_name=name,
                        skill_path=skill_file,
                        reason='skill review failed',
                        review=review,
                    )
                )
                continue
            for finding in review.findings:
                if finding.severity == 'warning':
                    warnings.append(
                        SkillLoadWarning(
                            skill_name=name,
                            skill_path=skill_file,
                            message=finding.message,
                        )
                    )
            try:
                raw = skill_file.read_bytes()
                if len(raw) > _MAX_SKILL_BYTES:
                    raw = raw[:_MAX_SKILL_BYTES]
                    warnings.append(
                        SkillLoadWarning(
                            skill_name=name,
                            skill_path=skill_file,
                            message=f'SKILL.md exceeded {_MAX_SKILL_BYTES} bytes and was truncated',
                        )
                    )
                content = raw.decode('utf-8', errors='replace')
            except OSError:
                continue
            results.append(SkillContent(name=name, path=skill_file, content=content))
            seen_names.add(name)

    return SkillLoadReport(
        skills=results, searched_dirs=skill_dirs, warnings=warnings, skipped=skipped
    )


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
