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
class SkillIndexEntry:
    """Metadata for a discoverable skill without eager prompt injection."""

    name: str
    path: Path
    summary: str


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


def _skill_summary(skill_file: Path) -> str:
    try:
        text = skill_file.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    body = text
    if body.startswith('---'):
        end = body.find('\n---', 3)
        if end != -1:
            body = body[end + 4 :]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            return stripped[:160]
    return ''


def discover_skill_index(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    max_skills: int = 20,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> list[SkillIndexEntry]:
    """List discoverable skills without loading full SKILL.md bodies."""
    skill_dirs = discover_skill_search_dirs(
        root,
        extra_skill_dirs=extra_skill_dirs,
        preferred_dirs=preferred_dirs,
        source_profile=source_profile,
    )
    seen_names: set[str] = set()
    entries: list[SkillIndexEntry] = []
    for skill_dir in skill_dirs:
        if len(entries) >= max_skills:
            break
        try:
            children = sorted(skill_dir.iterdir())
        except OSError:
            continue
        for entry in children:
            if len(entries) >= max_skills:
                break
            if not entry.is_dir():
                continue
            skill_file = entry / _SKILL_FILENAME
            if not skill_file.is_file():
                continue
            name = entry.name
            if name in seen_names:
                continue
            review = review_skill(skill_file)
            if not review.passed:
                continue
            entries.append(
                SkillIndexEntry(
                    name=name,
                    path=skill_file,
                    summary=_skill_summary(skill_file) or '(no summary)',
                )
            )
            seen_names.add(name)
    return entries


def load_skills_with_report(
    root: str | Path,
    *,
    extra_skill_dirs: Optional[list[Path]] = None,
    max_skills: int = 20,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
    selected_names: Optional[frozenset[str]] = None,
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

    selected_names:
        When ``frozenset()`` (empty), load no skills. When a non-empty set, load
        only those skill names. When ``None``, preserve eager discovery (default).
    """
    if selected_names is not None and not selected_names:
        skill_dirs = discover_skill_search_dirs(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
        )
        return SkillLoadReport(
            skills=[], searched_dirs=skill_dirs, warnings=[], skipped=[]
        )

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
            if selected_names is not None and name not in selected_names:
                continue
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


def skill_index_to_prompt_section(entries: list[SkillIndexEntry]) -> str:
    """Render discoverable skill metadata without loading SKILL.md bodies."""
    if not entries:
        return ''
    lines = [
        'Available skills (metadata only — use --skill NAME to load full instructions):'
    ]
    for entry in entries:
        lines.append(f'- {entry.name}: {entry.summary}')
    return '\n\n'.join(lines)


def estimate_skill_prompt_tokens(skills: list[SkillContent]) -> int:
    """Rough token estimate for skills injected into the system prompt."""
    if not skills:
        return 0
    return max(1, len(skills_to_prompt_section(skills)) // 4)


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


@dataclass(frozen=True)
class SkillLoadedRecord:
    name: str
    path: Path
    source_dir: Path
    estimated_tokens: int
    reason: str


@dataclass(frozen=True)
class SkillShadowRecord:
    name: str
    winner_path: Path
    shadowed_path: Path
    winner_source: str
    shadowed_source: str


@dataclass(frozen=True)
class SkillActivationExplain:
    selection_mode: Literal['eager', 'selected', 'index_only', 'none']
    selected_names: tuple[str, ...]
    loaded: tuple[SkillLoadedRecord, ...]
    shadowed: tuple[SkillShadowRecord, ...]
    skipped: tuple[SkillLoadSkipped, ...]
    warnings: tuple[SkillLoadWarning, ...]
    searched_dirs: tuple[Path, ...]
    estimated_skill_tokens: int
    index_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            'selection_mode': self.selection_mode,
            'selected_names': list(self.selected_names),
            'loaded': [
                {
                    'name': item.name,
                    'path': str(item.path),
                    'source_dir': str(item.source_dir),
                    'estimated_tokens': item.estimated_tokens,
                    'reason': item.reason,
                }
                for item in self.loaded
            ],
            'shadowed': [
                {
                    'name': item.name,
                    'winner_path': str(item.winner_path),
                    'shadowed_path': str(item.shadowed_path),
                    'winner_source': item.winner_source,
                    'shadowed_source': item.shadowed_source,
                }
                for item in self.shadowed
            ],
            'skipped': [
                {
                    'name': item.skill_name,
                    'path': str(item.skill_path),
                    'reason': item.reason,
                }
                for item in self.skipped
            ],
            'warnings': [
                {
                    'name': item.skill_name,
                    'path': str(item.skill_path),
                    'message': item.message,
                }
                for item in self.warnings
            ],
            'searched_dirs': [str(path) for path in self.searched_dirs],
            'estimated_skill_tokens': self.estimated_skill_tokens,
            'index_count': self.index_count,
        }


def _discover_skill_name_paths(
    skill_dirs: list[Path],
) -> dict[str, list[tuple[Path, Path]]]:
    """Map skill name to all discoverable paths in search order."""
    by_name: dict[str, list[tuple[Path, Path]]] = {}
    for skill_dir in skill_dirs:
        try:
            entries = sorted(skill_dir.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            skill_file = entry / _SKILL_FILENAME
            if not skill_file.is_file():
                continue
            by_name.setdefault(entry.name, []).append((skill_file, skill_dir))
    return by_name


def _shadow_records(
    by_name: dict[str, list[tuple[Path, Path]]],
) -> tuple[SkillShadowRecord, ...]:
    rows: list[SkillShadowRecord] = []
    for name, paths in sorted(by_name.items()):
        if len(paths) < 2:
            continue
        winner_path, winner_source = paths[0]
        for shadowed_path, shadowed_source in paths[1:]:
            rows.append(
                SkillShadowRecord(
                    name=name,
                    winner_path=winner_path,
                    shadowed_path=shadowed_path,
                    winner_source=str(winner_source),
                    shadowed_source=str(shadowed_source),
                )
            )
    return tuple(rows)


def explain_skill_activation(
    root: str | Path,
    *,
    selected_names: Optional[frozenset[str]] = None,
    skill_prompt_mode: Literal['eager', 'index_only'] = 'eager',
    extra_skill_dirs: Optional[list[Path]] = None,
    preferred_dirs: Optional[list[str | Path]] = None,
    source_profile: SkillSourceProfile = 'default',
) -> SkillActivationExplain:
    """Explain which skills load, which are shadowed, and token contribution."""
    skill_dirs = discover_skill_search_dirs(
        root,
        extra_skill_dirs=extra_skill_dirs,
        preferred_dirs=preferred_dirs,
        source_profile=source_profile,
    )
    by_name = _discover_skill_name_paths(skill_dirs)
    shadowed = _shadow_records(by_name)

    if skill_prompt_mode == 'index_only':
        index = discover_skill_index(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
        )
        report = load_skills_with_report(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
            selected_names=frozenset(),
        )
        return SkillActivationExplain(
            selection_mode='index_only',
            selected_names=(),
            loaded=(),
            shadowed=shadowed,
            skipped=tuple(report.skipped),
            warnings=tuple(report.warnings),
            searched_dirs=tuple(report.searched_dirs),
            estimated_skill_tokens=0,
            index_count=len(index),
        )

    if selected_names is not None and not selected_names:
        report = load_skills_with_report(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
            selected_names=frozenset(),
        )
        return SkillActivationExplain(
            selection_mode='none',
            selected_names=(),
            loaded=(),
            shadowed=shadowed,
            skipped=tuple(report.skipped),
            warnings=tuple(report.warnings),
            searched_dirs=tuple(report.searched_dirs),
            estimated_skill_tokens=0,
            index_count=0,
        )

    if selected_names is not None:
        report = load_skills_with_report(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
            selected_names=selected_names,
        )
        mode: Literal['eager', 'selected', 'index_only', 'none'] = 'selected'
        names = tuple(sorted(selected_names))
    else:
        report = load_skills_with_report(
            root,
            extra_skill_dirs=extra_skill_dirs,
            preferred_dirs=preferred_dirs,
            source_profile=source_profile,
            selected_names=None,
        )
        mode = 'eager'
        names = ()

    loaded_rows: list[SkillLoadedRecord] = []
    for skill in report.skills:
        source_dir = skill.path.parent.parent
        loaded_rows.append(
            SkillLoadedRecord(
                name=skill.name,
                path=skill.path,
                source_dir=source_dir,
                estimated_tokens=max(1, len(skill.content) // 4),
                reason=(
                    f'selected explicitly (--skill {skill.name})'
                    if mode == 'selected'
                    else 'first match in search order (eager load)'
                ),
            )
        )
    total = estimate_skill_prompt_tokens(report.skills)
    return SkillActivationExplain(
        selection_mode=mode,
        selected_names=names,
        loaded=tuple(loaded_rows),
        shadowed=shadowed,
        skipped=tuple(report.skipped),
        warnings=tuple(report.warnings),
        searched_dirs=tuple(report.searched_dirs),
        estimated_skill_tokens=total,
        index_count=0,
    )
