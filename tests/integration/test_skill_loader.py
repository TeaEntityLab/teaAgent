"""IT-5: Skill loader discovers SKILL.md files and injects them into prompts.

Covers: project-level skills, user-level skills, deduplication (project wins),
max_skills cap, and prompt section rendering.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.skill_loader import (
    discover_skill_search_dirs,
    load_skills,
    skills_to_prompt_section,
)


def _write_skill(parent: Path, name: str, content: str) -> Path:
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'SKILL.md'
    if not content.startswith('---\n'):
        content = f'---\nname: {name}\ndescription: test skill {name}\n---\n\n{content}'
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

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [tmp_path / 'nonexistent_user_skills'])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')
    skills = load_skills(tmp_path)
    assert skills == []


def test_load_skills_skips_dirs_without_skill_md(tmp_path, monkeypatch):
    """Dirs without SKILL.md are skipped; user skills don't interfere."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [tmp_path / 'nonexistent_user_skills'])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')

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
    from teaagent.types import ToolRegistry

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


def test_discover_skill_search_dirs_priority_order(tmp_path, monkeypatch):
    import teaagent.skill_loader as sl

    agent_dir = tmp_path / '.config' / 'agent' / 'skills'
    claude_dir = tmp_path / '.claude' / 'skills'
    opencode_dir = tmp_path / '.opencode' / 'skill'
    for path in (agent_dir, claude_dir, opencode_dir):
        path.mkdir(parents=True, exist_ok=True)
    user_dir = tmp_path / 'user_skills'
    user_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [user_dir])

    dirs = discover_skill_search_dirs(tmp_path)
    assert dirs[:3] == [agent_dir, claude_dir, opencode_dir]


def test_preferred_dirs_override_default_discovery_order(tmp_path):
    opencode_dir = tmp_path / '.opencode' / 'skill'
    opencode_dir.mkdir(parents=True, exist_ok=True)
    _write_skill(opencode_dir, 'shared', '# OpenCode\nfrom opencode')
    custom_dir = tmp_path / 'custom-skills'
    custom_dir.mkdir(parents=True, exist_ok=True)
    _write_skill(custom_dir, 'shared', '# Custom\nfrom custom')

    skills = load_skills(tmp_path, preferred_dirs=['custom-skills', '.opencode/skill'])
    shared = [s for s in skills if s.name == 'shared']
    assert len(shared) == 1
    assert 'from custom' in shared[0].content


def test_get_skill_diagnostics_includes_isolation_status(tmp_path, monkeypatch):
    """P2-A-002: skill diagnostics must report isolation status."""
    from teaagent.skill_loader import get_skill_diagnostics

    monkeypatch.setattr(
        'teaagent.skill_loader._build_isolation_status',
        lambda: {
            'available_backends': ['docker'],
            'wasm_available': False,
            'docker_available': True,
            'downgrade_label': 'partial-isolation',
            'warnings': ['WASM runtime not installed'],
        },
    )
    diagnostics = get_skill_diagnostics(tmp_path)
    iso = diagnostics.get('isolation_status', {})
    assert 'available_backends' in iso
    assert 'downgrade_label' in iso
    assert 'warnings' in iso


def test_isolation_status_native_fallback_warning(tmp_path, monkeypatch):
    """P2-A-002: when neither WASM nor Docker is available, warn prominently."""
    from teaagent.skill_loader import get_skill_diagnostics

    monkeypatch.setattr(
        'teaagent.skill_loader._build_isolation_status',
        lambda: {
            'available_backends': [],
            'wasm_available': False,
            'docker_available': False,
            'downgrade_label': 'native-execution-fallback',
            'warnings': [
                'Skill isolation degraded: neither WASM (wasmer) nor Docker is available.'
            ],
        },
    )
    diagnostics = get_skill_diagnostics(tmp_path)
    iso = diagnostics['isolation_status']
    assert iso['downgrade_label'] == 'native-execution-fallback'
    assert len(iso['warnings']) == 1
    assert 'degraded' in iso['warnings'][0]


def test_isolation_status_full_isolation(tmp_path, monkeypatch):
    """P2-A-002: full-isolation when both WASM and Docker available."""
    from teaagent.skill_loader import get_skill_diagnostics

    monkeypatch.setattr(
        'teaagent.skill_loader._build_isolation_status',
        lambda: {
            'available_backends': ['wasm', 'docker'],
            'wasm_available': True,
            'docker_available': True,
            'downgrade_label': 'full-isolation',
            'warnings': [],
        },
    )
    diagnostics = get_skill_diagnostics(tmp_path)
    iso = diagnostics['isolation_status']
    assert iso['downgrade_label'] == 'full-isolation'
    assert iso['wasm_available'] is True
    assert iso['docker_available'] is True
    assert iso['warnings'] == []


def test_extended_profile_discovers_codex_dir(tmp_path, monkeypatch):
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(sl, '_EXTENDED_USER_SKILL_DIRS', [])
    codex_dir = tmp_path / '.codex' / 'skills'
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_skill(codex_dir, 'codex-skill', '# Codex\nfrom codex')

    skills = load_skills(tmp_path, source_profile='extended')
    found = [s for s in skills if s.name == 'codex-skill']
    assert len(found) == 1
    assert 'from codex' in found[0].content


# Negative test cases for malformed SKILL.md files
def test_malformed_skill_missing_frontmatter(tmp_path, monkeypatch):
    """Skill without frontmatter should be skipped or handled gracefully."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')

    skill_dir = tmp_path / '.opencode' / 'skill'
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'malformed' / 'SKILL.md'
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    # Write skill without frontmatter
    skill_file.write_text('# Just a header\nNo frontmatter here', encoding='utf-8')

    skills = load_skills(tmp_path)
    # Should either skip or handle gracefully
    assert isinstance(skills, list)


def test_malformed_skill_invalid_yaml_frontmatter(tmp_path, monkeypatch):
    """Skill with invalid YAML frontmatter should be handled gracefully."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')

    skill_dir = tmp_path / '.opencode' / 'skill'
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'invalid_yaml' / 'SKILL.md'
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    # Write skill with invalid YAML
    skill_file.write_text(
        '---\nname: test\ninvalid: yaml: content: [unclosed\n---\n\nContent',
        encoding='utf-8',
    )

    skills = load_skills(tmp_path)
    # Should handle gracefully without crashing
    assert isinstance(skills, list)


def test_malformed_skill_empty_file(tmp_path, monkeypatch):
    """Empty SKILL.md file should be handled gracefully."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')

    skill_dir = tmp_path / '.opencode' / 'skill'
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'empty' / 'SKILL.md'
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text('', encoding='utf-8')

    skills = load_skills(tmp_path)
    # Should handle gracefully
    assert isinstance(skills, list)


def test_malformed_skill_missing_name(tmp_path, monkeypatch):
    """Skill frontmatter without name field should be handled gracefully."""
    import teaagent.skill_loader as sl

    monkeypatch.setattr(sl, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(sl, '_BUILTIN_SKILL_DIR', tmp_path / 'nonexistent_builtin')

    skill_dir = tmp_path / '.opencode' / 'skill'
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / 'no_name' / 'SKILL.md'
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    # Write skill without name in frontmatter
    skill_file.write_text('---\ndescription: test\n---\n\nContent', encoding='utf-8')

    skills = load_skills(tmp_path)
    # Should handle gracefully
    assert isinstance(skills, list)
