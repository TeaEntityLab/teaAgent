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

from teaagent.skill_candidate_artifacts import (
    REQUIRED_CANDIDATE_ARTIFACTS,
    validate_candidate_artifacts,
)
from teaagent.skill_lifecycle import (
    SkillLifecycleState,
    SkillLifecycleTracker,
    classify_governance_status,
)
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
_BUILTIN_SKILL_DIR = Path(__file__).resolve().parent / 'skills' / 'builtin'
_SKILL_FILENAME = 'SKILL.md'
_MAX_SKILL_BYTES = 32_768  # 32 KB per skill — guard against runaway includes


def _read_activated_skills(root: str | Path) -> frozenset[str]:
    config_path = Path(root) / '.teaagent' / 'activated-skills.json'
    if not config_path.is_file():
        return frozenset()
    import json

    try:
        data = json.loads(config_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    names = data.get('activated_skills', [])
    if not isinstance(names, list):
        return frozenset()
    return frozenset(str(n).strip() for n in names if str(n).strip())


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
    # Built-in skills are lowest priority (after project/user/opencode)
    if _BUILTIN_SKILL_DIR.is_dir():
        result.append(_BUILTIN_SKILL_DIR)
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
            artifact_errors = _installed_candidate_artifact_errors(entry)
            if artifact_errors:
                skipped.append(
                    SkillLoadSkipped(
                        skill_name=name,
                        skill_path=skill_file,
                        reason='installed skill provenance validation failed: '
                        + '; '.join(artifact_errors[:3]),
                    )
                )
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


def _installed_candidate_artifact_errors(skill_dir: Path) -> list[str]:
    json_artifact_names = set(REQUIRED_CANDIDATE_ARTIFACTS) - {_SKILL_FILENAME, 'REFERENCE.md'}
    present = {path.name for path in skill_dir.iterdir() if path.name in json_artifact_names}
    if not present:
        return []
    return validate_candidate_artifacts(skill_dir)


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
    governance_status: str = (
        'unknown'  # candidate_installed | direct_write | compatibility_path | unmanaged
    )
    lifecycle_state: str = 'unknown'


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
    write_targets: dict[str, str]  # skill_name -> write_target_path

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
                    'governance_status': item.governance_status,
                    'lifecycle_state': item.lifecycle_state,
                }
                for item in self.loaded
            ],
            'shadowed': [
                {
                    'name': item.name,
                    'winner_path': str(item.winner_path),
                    'shadowed_path': str(item.shadowed_path),
                    'winner_source': str(item.winner_source),
                    'shadowed_source': str(item.shadowed_source),
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
            'write_targets': self.write_targets,
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
    lifecycle_tracker: Optional[SkillLifecycleTracker] = None,
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

    if lifecycle_tracker is not None:
        for name, paths in by_name.items():
            lifecycle_tracker.set_state(
                name,
                SkillLifecycleState.DISCOVERED.value,
                source_path=str(paths[0][0]) if paths else '',
            )

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
            write_targets={},
        )

    if selected_names is not None and not selected_names:
        activated = _read_activated_skills(root)
        if activated:
            selected_names = activated
        else:
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
                write_targets={},
            )

    if selected_names is not None:
        activated = _read_activated_skills(root)
        if activated:
            selected_names = selected_names | activated
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
    root_path = Path(root).resolve()
    for skill in report.skills:
        source_dir = skill.path.parent.parent
        skill_dir = skill.path.parent
        governance_status = classify_governance_status(
            skill_dir=skill_dir,
            source_dir=source_dir,
            root=root_path,
        )
        lifecycle_state = SkillLifecycleState.ACTIVATED.value
        if lifecycle_tracker is not None:
            lifecycle_tracker.transition(
                skill.name,
                SkillLifecycleState.ACTIVATED.value,
                reason=(
                    f'selected explicitly (--skill {skill.name})'
                    if mode == 'selected'
                    else 'first match in search order (eager load)'
                ),
                source_path=str(skill.path),
            )
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
                governance_status=governance_status,
                lifecycle_state=lifecycle_state,
            )
        )
    total = estimate_skill_prompt_tokens(report.skills)
    # Compute write targets based on skill_writer logic
    root_path = Path(root).resolve()
    write_targets: dict[str, str] = {}
    for skill in report.skills:
        skill_name = skill.name
        # SkillWriter writes to .config/agent/skills
        write_target = root_path / '.config' / 'agent' / 'skills' / skill_name
        write_targets[skill_name] = str(write_target)
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
        write_targets=write_targets,
    )


def get_skill_diagnostics(root: str | Path) -> dict:
    """Return a comprehensive diagnostics dictionary for all skill subsystems.

    Aggregates data from skill activation, candidates, long-result artifacts,
    and output validation into a single structured dict suitable for TUI panels
    and slash-command handlers.

    Parameters
    ----------
    root:
        Workspace root directory.

    Returns
    -------
    dict
        Keys: ``loaded_skills``, ``active_skill``, ``shadowed_skills``,
        ``skipped``, ``warnings``, ``searched_dirs``, ``governance_status``,
        ``candidates``, ``candidate_count``, ``long_result_artifacts``,
        ``output_verification``, ``isolation_status``.
    """
    root_path = Path(root).resolve()

    # ── isolation status (P2-A-002) ──────────────────────────────────────
    isolation_status = _build_isolation_status()

    # ── skill activation ──────────────────────────────────────────────────
    activation = explain_skill_activation(
        root_path,
        selected_names=frozenset({'__diagnostics_probe__'}),
    )

    loaded_skills: list[dict] = []
    governance_status: dict[str, str] = {}
    for rec in activation.loaded:
        loaded_skills.append(
            {
                'name': rec.name,
                'path': str(rec.path),
                'source_dir': str(rec.source_dir),
                'governance_status': rec.governance_status,
                'lifecycle_state': rec.lifecycle_state,
                'reason': rec.reason,
                'estimated_tokens': rec.estimated_tokens,
            }
        )
        governance_status[rec.name] = rec.governance_status

    # Determine "active" skill — the first loaded skill, if any.
    active_skill: dict | None = loaded_skills[0] if loaded_skills else None

    shadowed_skills: list[dict] = [
        {
            'name': s.name,
            'winner_path': str(s.winner_path),
            'shadowed_path': str(s.shadowed_path),
            'winner_source': s.winner_source,
            'shadowed_source': s.shadowed_source,
        }
        for s in activation.shadowed
    ]

    skipped: list[dict] = [
        {
            'name': s.skill_name,
            'path': str(s.skill_path),
            'reason': s.reason,
        }
        for s in activation.skipped
    ]

    warnings: list[dict] = [
        {
            'name': w.skill_name,
            'path': str(w.skill_path),
            'message': w.message,
        }
        for w in activation.warnings
    ]

    # ── skill candidates ──────────────────────────────────────────────────
    from teaagent.skill_candidates import SkillCandidateStore

    candidate_store = SkillCandidateStore(root_path, readonly=True)
    try:
        candidates_raw = candidate_store.list()
    except Exception:
        candidates_raw = []

    candidates: list[dict] = [
        {
            'candidate_id': c.candidate_id,
            'name': c.name,
            'description': c.description,
            'status': c.status,
            'source_run_id': c.source_run_id,
            'review_summary': c.review_summary,
        }
        for c in candidates_raw
    ]

    # ── long-result artifacts ─────────────────────────────────────────────
    artifact_dir = root_path / '.teaagent' / 'artifacts' / 'tool-results'
    long_result_artifacts: dict[str, dict] = {}
    if artifact_dir.is_dir():
        for run_dir in sorted(artifact_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            run_id = run_dir.name
            try:
                files = sorted(
                    f for f in run_dir.iterdir() if f.is_file()
                )
            except OSError:
                files = []
            long_result_artifacts[run_id] = {
                'run_id': run_id,
                'artifact_count': len(files),
                'artifact_paths': [
                    str(f.relative_to(root_path)) for f in files
                ],
            }

    # ── output verification ───────────────────────────────────────────────
    # Report which validators are registered, not their results on
    # inspected files (no model-call → safe to run).
    output_verification: dict = {
        'validators_available': [
            'FileExistsValidator',
            'SourceUrlValidator',
            'KnownTitleValidator',
            'CategoryValidator',
            'PromptInjectionValidator',
        ],
        'status': 'available' if bool(loaded_skills) else 'no_skills_loaded',
    }

    return {
        'loaded_skills': loaded_skills,
        'active_skill': active_skill,
        'shadowed_skills': shadowed_skills,
        'skipped': skipped,
        'warnings': warnings,
        'searched_dirs': [str(d) for d in activation.searched_dirs],
        'governance_status': governance_status,
        'candidates': candidates,
        'candidate_count': len(candidates),
        'long_result_artifacts': long_result_artifacts,
        'output_verification': output_verification,
        'isolation_status': isolation_status,
    }


def _build_isolation_status() -> dict:
    """Check WASM and Docker availability for skill isolation diagnostics.

    Returns a dict with ``available_backends``, ``warnings``, and a
    ``downgrade_label`` that the TUI can render prominently when no
    container/VM isolation is available.
    """
    wasm_ok = False
    docker_ok = False

    try:
        from teaagent.wasm_runtime import is_wasm_available

        wasm_ok = is_wasm_available()
    except ImportError:
        pass

    try:
        from teaagent.mcp_trust import is_docker_available

        docker_ok = is_docker_available()
    except ImportError:
        pass

    available = []
    if wasm_ok:
        available.append('wasm')
    if docker_ok:
        available.append('docker')

    warnings = []
    if not wasm_ok and not docker_ok:
        warnings.append(
            'Skill isolation degraded: neither WASM (wasmer) nor Docker is available. '
            'Skills will execute natively on the host with subprocess isolation only — '
            'no OS-level sandboxing is active.'
        )
    elif not wasm_ok:
        warnings.append('WASM runtime (wasmer) not installed; WASM skills will fall back to native execution.')
    elif not docker_ok:
        warnings.append('Docker not available; container-isolated skills will fall back to native execution.')

    return {
        'available_backends': available,
        'wasm_available': wasm_ok,
        'docker_available': docker_ok,
        'downgrade_label': (
            'native-execution-fallback'
            if not wasm_ok and not docker_ok
            else 'partial-isolation'
            if not (wasm_ok and docker_ok)
            else 'full-isolation'
        ),
        'warnings': warnings,
    }


def get_skill_health(root: str | Path) -> dict:
    """Return a skill ecosystem health dashboard (DSK-P2-003).

    Builds on ``get_skill_diagnostics()`` to produce structured JSON with:
    total_skills, governance_distribution, shadowed_count, candidate_summary,
    stale_candidates, failed_evals, warnings, and skipped.

    Parameters
    ----------
    root:
        Workspace root directory.

    Returns
    -------
    dict
        Keys: ``total_skills``, ``loaded_skills_count``,
        ``governance_distribution``, ``shadowed_count``,
        ``candidate_summary``, ``stale_candidates``, ``failed_evals``,
        ``warnings``, ``skipped``.
    """
    from datetime import datetime, timezone

    from teaagent.skill_candidates import SkillCandidateStore
    from teaagent.skill_eval import load_eval_report

    root_path = Path(root).resolve()

    diagnostics = get_skill_diagnostics(root_path)

    # ── governance distribution ────────────────────────────────────────
    gov_statuses: dict[str, str] = diagnostics.get('governance_status', {})
    gov_dist = {
        'direct_write': 0,
        'candidate_installed': 0,
        'compatibility_path': 0,
        'unmanaged': 0,
    }
    for status in gov_statuses.values():
        if status in gov_dist:
            gov_dist[status] += 1

    # ── total skill index count ─────────────────────────────────────────
    total_skills = len(
        discover_skill_index(root_path)
    )

    # ── candidates: summary, stale, failed evals ────────────────────────
    store = SkillCandidateStore(root_path, readonly=True)
    try:
        candidates = store.list()
    except Exception:
        candidates = []

    now = datetime.now(timezone.utc)
    stale: list[dict] = []
    failed_evals: list[dict] = []
    candidate_summary: dict[str, int] = {
        'total': len(candidates),
        'proposed': 0,
        'eval_failed': 0,
        'review_failed': 0,
        'review_passed': 0,
        'installed': 0,
    }

    for c in candidates:
        if c.status in candidate_summary:
            candidate_summary[c.status] += 1
        # Stale detection: not installed + older than 7 days
        try:
            updated = datetime.fromisoformat(c.updated_at)
        except (ValueError, TypeError):
            updated = now
        if c.status not in ('installed',) and (now - updated).days >= 7:
            stale.append(
                {
                    'name': c.name,
                    'candidate_id': c.candidate_id,
                    'status': c.status,
                    'updated_at': c.updated_at,
                }
            )
        # Failed eval detail loading
        if c.status == 'eval_failed':
            candidate_dir = store.candidate_dir(c.candidate_id)
            try:
                report = load_eval_report(candidate_dir)
            except Exception:
                report = None
            failed_evals.append(
                {
                    'name': c.name,
                    'candidate_id': c.candidate_id,
                    'failures': list(report.failures) if report and report.failures else [],
                }
            )

    return {
        'total_skills': total_skills,
        'loaded_skills_count': len(diagnostics.get('loaded_skills', [])),
        'governance_distribution': gov_dist,
        'shadowed_count': len(diagnostics.get('shadowed_skills', [])),
        'candidate_summary': candidate_summary,
        'stale_candidates': stale,
        'failed_evals': failed_evals,
        'warnings': diagnostics.get('warnings', []),
        'skipped': diagnostics.get('skipped', []),
    }
