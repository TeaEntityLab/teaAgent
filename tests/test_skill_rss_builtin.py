"""Unit tests for the built-in rss-summary skill."""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.skill_loader import load_skills_with_report

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SKILL_DIR = PROJECT_ROOT / 'teaagent' / 'skills' / 'builtin' / 'rss-summary'


def test_builtin_rss_skill_exists() -> None:
    """SKILL.md, REFERENCE.md, and examples directory exist."""
    assert (SKILL_DIR / 'SKILL.md').is_file(), (
        'SKILL.md should exist in rss-summary skill directory'
    )
    assert (SKILL_DIR / 'REFERENCE.md').is_file(), (
        'REFERENCE.md should exist in rss-summary skill directory'
    )
    examples_dir = SKILL_DIR / 'examples'
    assert examples_dir.is_dir(), (
        'examples directory should exist in rss-summary skill directory'
    )
    assert (examples_dir / 'example-input.txt').is_file(), (
        'example-input.txt should exist'
    )
    assert (examples_dir / 'example-output.md').is_file(), (
        'example-output.md should exist'
    )


def test_builtin_rss_skill_has_valid_frontmatter() -> None:
    """YAML frontmatter parses with required name and description fields."""
    skill_md = SKILL_DIR / 'SKILL.md'
    content = skill_md.read_text(encoding='utf-8')
    # Extract YAML frontmatter
    lines = content.splitlines()
    assert lines, 'SKILL.md should not be empty'
    assert lines[0] == '---', 'SKILL.md must start with YAML frontmatter delimiter'
    # Find closing ---
    end = None
    for i in range(1, len(lines)):
        if lines[i] == '---':
            end = i
            break
    assert end is not None, 'SKILL.md must have closing YAML frontmatter delimiter'
    frontmatter_text = '\n'.join(lines[1:end])
    data: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            data[key.strip()] = val.strip()
    assert data, 'Frontmatter must parse as a YAML mapping'
    assert 'name' in data, "Frontmatter must contain 'name'"
    assert data['name'] == 'rss-summary'
    assert 'description' in data, "Frontmatter must contain 'description'"
    assert len(data['description']) > 0, 'Description must be non-empty'


def test_builtin_rss_skill_reference_has_limitations() -> None:
    """REFERENCE.md contains limitation/caveat language."""
    reference_md = SKILL_DIR / 'REFERENCE.md'
    content = reference_md.read_text(encoding='utf-8')
    lower = content.lower()
    has_limitation = 'limitation' in lower or 'caveat' in lower
    has_known_failure = 'known failure' in lower or 'failure mode' in lower
    assert has_limitation or has_known_failure, (
        'REFERENCE.md should document limitations or known failure modes'
    )


def test_builtin_rss_skill_discovered_by_loader() -> None:
    """SkillLoader discovers the built-in rss-summary skill."""
    with tempfile.TemporaryDirectory() as tmp:
        report = load_skills_with_report(
            root=tmp,
            selected_names=frozenset(['rss-summary']),
        )
        skill_names = [s.name for s in report.skills]
        assert 'rss-summary' in skill_names, (
            f'Built-in rss-summary skill should be discovered. Found: {skill_names}'
        )
        # Verify the builtin directory is in the searched dirs
        searched_strs = [str(d) for d in report.searched_dirs]
        assert any('teaagent/skills/builtin' in s for s in searched_strs), (
            f'Builtin skills directory should be in searched paths. Got: {searched_strs}'
        )
