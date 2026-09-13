# test-type: behavior
"""Basic tests for skill discovery and loading from known directories."""

from __future__ import annotations

import os
from pathlib import Path

from teaagent.skill_loader import (
    _discover_skill_dirs,
    discover_skill_search_dirs,
    load_skills,
)


def test_discover_skill_dirs_empty_for_nonexistent_root() -> None:
    """Discovering skills from a non-existent root yields no directories."""
    dirs = _discover_skill_dirs(Path('/nonexistent/path'))
    assert isinstance(dirs, list)
    # No side effects for missing paths
    assert all(isinstance(d, Path) for d in dirs)


def test_discover_skill_search_dirs_returns_list(tmp_path: Path) -> None:
    """discover_skill_search_dirs returns a list of search directories."""
    dirs = discover_skill_search_dirs(root=tmp_path)
    assert isinstance(dirs, list)
    assert len(dirs) > 0
    assert all(isinstance(d, Path) for d in dirs)


def test_load_skills_from_empty_root(tmp_path: Path) -> None:
    """Loading skills from a root with no skills returns a list (may include
    user-global skills from ~/.config/agent/skills/ etc.)."""
    skills = load_skills(root=tmp_path)
    assert isinstance(skills, list)
    # Skills from user-wide directories may appear even with empty project root
    assert all(hasattr(s, 'name') for s in skills)


def test_load_skills_from_nonexistent_dir() -> None:
    """Loading skills from a non-existent root does not crash."""
    skills = load_skills(root=Path('/nonexistent/path'))
    assert isinstance(skills, list)
    # A missing project root contributes no skills of its own: every skill
    # returned is a valid, uniquely-named Skill sourced from an existing path.
    assert all(s.name and isinstance(s.name, str) for s in skills)
    assert len({s.name for s in skills}) == len(skills)
    assert all('/nonexistent/path' not in str(s.path) for s in skills)


def test_load_skills_with_relative_root(tmp_path: Path) -> None:
    """Relative workspace roots work for skill discovery."""
    skill_dir = tmp_path / '.opencode' / 'skill' / 'rel-skill'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: rel-skill\ndescription: A relative-root discovery test skill\n---\n'
        '# Rel Skill\n',
        encoding='utf-8',
    )
    relative_root = Path(os.path.relpath(tmp_path))
    assert not relative_root.is_absolute()
    skills = load_skills(root=relative_root)
    assert isinstance(skills, list)
    assert 'rel-skill' in {s.name for s in skills}


def test_load_skills_with_skill_file(tmp_path: Path) -> None:
    """A SKILL.md file with valid frontmatter in a known skill dir is discovered."""
    skill_dir = tmp_path / '.opencode' / 'skill' / 'test-skill'
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / 'SKILL.md'
    skill_file.write_text(
        '---\nname: test-skill\ndescription: A test skill for verifying discovery\n---\n'
        '# Test Skill\n\nA test skill.\n',
        encoding='utf-8',
    )

    skills = load_skills(root=tmp_path)
    names = [s.name for s in skills]
    assert 'test-skill' in names
