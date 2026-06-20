"""G-P2-5: Skill review installed-skill strictness tests.

Ensures that an oversized ``SKILL.md`` is an ERROR for installed
(candidate-provenance) skills but only a warning during development.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.skill_review import review_skill


def _make_long_skill(tmp: str, name: str, lines: int = 90) -> Path:
    skill_dir = Path(tmp) / name
    skill_dir.mkdir()
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: long\ndescription: long\n---\n' + 'line\n' * lines,
        encoding='utf-8',
    )
    return skill_dir


def test_installed_skill_oversize_is_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = _make_long_skill(tmp, 'installed-long')
        result = review_skill(skill_dir, max_skill_md_lines=80, installed=True)
        assert not result.passed
        line_findings = [
            f for f in result.findings if f.message.startswith('SKILL.md has')
        ]
        assert len(line_findings) == 1
        assert line_findings[0].severity == 'error'


def test_development_skill_oversize_is_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = _make_long_skill(tmp, 'dev-long')
        result = review_skill(skill_dir, max_skill_md_lines=80, installed=False)
        assert result.passed
        line_findings = [
            f for f in result.findings if f.message.startswith('SKILL.md has')
        ]
        assert len(line_findings) == 1
        assert line_findings[0].severity == 'warning'


def test_default_installed_is_false_warning() -> None:
    """The default (no installed kwarg) keeps the development warning behavior."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = _make_long_skill(tmp, 'default-long')
        result = review_skill(skill_dir, max_skill_md_lines=80)
        assert result.passed
        line_findings = [
            f for f in result.findings if f.message.startswith('SKILL.md has')
        ]
        assert len(line_findings) == 1
        assert line_findings[0].severity == 'warning'


def test_installed_skill_within_limit_has_no_line_finding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'installed-short'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: short\ndescription: short\n---\n' + 'line\n' * 10,
            encoding='utf-8',
        )
        result = review_skill(skill_dir, max_skill_md_lines=80, installed=True)
        assert result.passed
        assert not any(f.message.startswith('SKILL.md has') for f in result.findings)


def test_installed_skill_file_not_directory_oversize_is_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_file = Path(tmp) / 'SKILL.md'
        skill_file.write_text(
            '---\nname: file\ndescription: file\n---\n' + 'line\n' * 90,
            encoding='utf-8',
        )
        result = review_skill(skill_file, max_skill_md_lines=80, installed=True)
        assert not result.passed
        assert any(
            f.severity == 'error' and f.message.startswith('SKILL.md has')
            for f in result.findings
        )
