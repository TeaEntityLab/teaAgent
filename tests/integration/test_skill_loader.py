"""IT-5: Skill loader discovers SKILL.md files and injects them into prompts.

Covers: project-level skills, user-level skills, deduplication (project wins),
max_skills cap, and prompt section rendering.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.skill_loader import (
    load_skills,
    skills_to_prompt_section,
)


def _write_skill(parent: Path, name: str, content: str) -> Path:
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'SKILL.md'
    skill_file.write_text(content, encoding='utf-8')
    return skill_file


def test_load_skills_from_opencode_dir(tmp_path):
    skill_dir = tmp_path / '.opencode' / 'skill'
    _write_skill(skill_dir, 'code-review', '# Code Review Skill\nDo thorough reviews.')
    _write_skill(skill_dir, 'testing', '# Testing Skill\nWrite unit tests.')

    skills = load_skills(tmp_path)
    names = {s.name for s in skills}
    assert 'code-review' in names
    assert 'testing' in names


def test_load_skills_content_matches_file(tmp_path):
    skill_dir = tmp_path / '.opencode' / 'skill'
    _write_skill(skill_dir, 'my-skill', '# My Skill\nSpecial instructions here.')

    skills = load_skills(tmp_path)
    my_skill = next((s for s in skills if s.name == 'my-skill'), None)
    assert my_skill is not None, 'my-skill not found in discovered skills'
    assert 'Special instructions here.' in my_skill.content


def test_load_skills_deduplication_project_wins(tmp_path, monkeypatch):
    """When the same skill name exists at project AND user level, project wins."""
    project_skill_dir = tmp_path / '.opencode' / 'skill'
    _write_skill(project_skill_dir, 'shared-skill', '# PROJECT version')

    user_skill_dir = tmp_path / 'user_skills'  # pretend this is the user dir
    _write_skill(user_skill_dir, 'shared-skill', '# USER version')

    skills = load_skills(tmp_path, extra_skill_dirs=[user_skill_dir])
    shared = [s for s in skills if s.name == 'shared-skill']
    assert len(shared) == 1
    assert 'PROJECT version' in shared[0].content


def test_load_skills_max_skills_cap(tmp_path):
    skill_dir = tmp_path / '.opencode' / 'skill'
    for i in range(10):
        _write_skill(skill_dir, f'skill-{i:02d}', f'# Skill {i}')

    skills = load_skills(tmp_path, max_skills=3)
    assert len(skills) == 3


def test_load_skills_empty_when_no_project_dir(tmp_path, monkeypatch):
    """When neither project skill dir exists nor user skill dir, result is empty."""
    # Monkeypatch the user-level skill dir to a non-existent path so user skills don't interfere
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIR', tmp_path / 'nonexistent_user_skills')
    skills = load_skills(tmp_path)
    assert skills == []


def test_load_skills_skips_dirs_without_skill_md(tmp_path, monkeypatch):
    """Dirs without SKILL.md are skipped; user skills don't interfere."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIR', tmp_path / 'nonexistent_user_skills')

    skill_dir = tmp_path / '.opencode' / 'skill'
    (skill_dir / 'no-skill-md').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'no-skill-md' / 'README.md').write_text('not a skill')

    skills = load_skills(tmp_path)
    assert skills == [], f'Expected no skills, got {[s.name for s in skills]}'


def test_skills_to_prompt_section_empty():
    assert skills_to_prompt_section([]) == ''


def test_skills_to_prompt_section_renders_all(tmp_path):
    skill_dir = tmp_path / '.opencode' / 'skill'
    _write_skill(skill_dir, 'alpha', '# Alpha\nAlpha content.')
    _write_skill(skill_dir, 'beta', '# Beta\nBeta content.')

    skills = load_skills(tmp_path)
    section = skills_to_prompt_section(skills)
    assert 'Skills:' in section
    assert '--- skill: alpha ---' in section
    assert 'Alpha content.' in section
    assert '--- skill: beta ---' in section


def test_skills_injected_into_prompt_system(tmp_path):
    """Skills appear in the assembled system prompt."""
    from teaagent.prompt import assemble_agent_prompt
    from teaagent.tools import ToolRegistry

    skill_dir = tmp_path / '.opencode' / 'skill'
    _write_skill(skill_dir, 'docgen', '# DocGen\nAlways generate docstrings.')

    skills = load_skills(tmp_path)
    registry = ToolRegistry()
    bundle = assemble_agent_prompt(
        task='write code',
        context={'task': 'write code', 'observations': []},
        registry=registry,
        skills=skills,
    )
    assert 'Always generate docstrings.' in bundle.system
