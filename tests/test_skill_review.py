from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.skill_review import review_skill


def test_missing_skill_md() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'empty-skill'
        skill_dir.mkdir()

        result = review_skill(skill_dir)

        assert not result.passed
        assert len(result.findings) == 1
        assert result.findings[0].severity == 'error'
        assert 'missing' in result.findings[0].message


def test_missing_yaml_frontmatter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'bad-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('No frontmatter here.\n', encoding='utf-8')

        result = review_skill(skill_dir)

        assert not result.passed
        messages = [f.message for f in result.findings]
        assert any('frontmatter' in m for m in messages)


def test_missing_name_in_frontmatter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'bad-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\ndescription: No name.\n---\n\n# Bad Skill\n',
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert not result.passed
        messages = [f.message for f in result.findings]
        assert any('name' in m for m in messages)


def test_missing_description_in_frontmatter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'bad-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: no-desc\n---\n\n# Bad Skill\n',
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert not result.passed
        messages = [f.message for f in result.findings]
        assert any('description' in m for m in messages)


def test_too_many_lines_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'long-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: long\ndescription: long\n---\n' + 'line\n' * 90,
            encoding='utf-8',
        )

        result = review_skill(skill_dir, max_skill_md_lines=80)

        assert result.passed
        assert any('Progressive Disclosure' in f.message for f in result.findings)


def test_external_network_reference_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'net-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: net\ndescription: uses curl\n---\n\nRun: `curl https://example.com`\n',
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert result.passed
        assert any('network' in f.message for f in result.findings)


def test_wget_triggers_network_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'net-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: net\ndescription: uses wget\n---\n\nDownload with `wget`.\n',
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert result.passed
        assert any('network' in f.message for f in result.findings)


def test_long_skill_without_reference_md_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'long-no-ref'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: long-no-ref\ndescription: long without reference\n---\n'
            + 'line\n' * 50,
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert result.passed
        assert any('REFERENCE' in f.message for f in result.findings)


def test_short_skill_without_reference_md_is_fine() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'short-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: short\ndescription: short without reference\n---\n'
            + 'line\n' * 10,
            encoding='utf-8',
        )

        result = review_skill(skill_dir)

        assert result.passed
        assert not any('REFERENCE' in f.message for f in result.findings)


def test_review_skill_file_not_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_file = Path(tmp) / 'SKILL.md'
        skill_file.write_text(
            '---\nname: file\ndescription: file review\n---\n\n# File\n',
            encoding='utf-8',
        )

        result = review_skill(skill_file)

        assert result.passed
        assert result.skill_path == skill_file


def test_network_and_length_warnings_together() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'combo-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: combo\ndescription: combo issues\n---\n'
            + 'line\n' * 50
            + 'Install with `curl https://example.com`\n',
            encoding='utf-8',
        )

        result = review_skill(skill_dir, max_skill_md_lines=80)

        messages = [f.message for f in result.findings]
        assert any('Progressive Disclosure' in m for m in messages)
        assert any('network' in m for m in messages)


def test_ast_detects_dangerous_imports() -> None:
    """Test that AST-based scanner detects dangerous imports in Python files."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'ast-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: ast-test\ndescription: AST test\n---\n\n# Test\n',
            encoding='utf-8',
        )
        # Add a Python file with dangerous imports
        py_file = skill_dir / 'hook.py'
        py_file.write_text(
            'import requests\nimport urllib\nprint("hello")', encoding='utf-8'
        )

        result = review_skill(skill_dir)
        # Should pass (no errors) but have warnings about dangerous imports
        assert result.passed
        assert any('requests' in f.message for f in result.findings)
        assert any('urllib' in f.message for f in result.findings)


def test_ast_detects_dangerous_calls() -> None:
    """Test that AST-based scanner detects dangerous function calls."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'ast-calls'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: ast-calls\ndescription: AST calls test\n---\n\n# Test\n',
            encoding='utf-8',
        )
        # Add a Python file with dangerous function calls
        py_file = skill_dir / 'processor.py'
        py_file.write_text('eval("print(1+1)")\nexec("x=1")', encoding='utf-8')

        result = review_skill(skill_dir)
        # Should pass (no errors) but have warnings about dangerous calls
        assert result.passed
        assert any('eval' in f.message for f in result.findings)
        assert any('exec' in f.message for f in result.findings)


def test_ast_ignores_safe_python_code() -> None:
    """Test that AST-based scanner doesn't flag safe Python code."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / 'safe-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text(
            '---\nname: safe\ndescription: Safe skill\n---\n\n# Safe\n',
            encoding='utf-8',
        )
        # Add a Python file with safe code
        py_file = skill_dir / 'utils.py'
        py_file.write_text(
            'def add(a, b): return a + b\nprint("safe")', encoding='utf-8'
        )

        result = review_skill(skill_dir)
        # Should pass with no warnings about dangerous patterns
        assert result.passed
        dangerous_warnings = [
            f for f in result.findings if 'dangerous' in f.message.lower()
        ]
        assert len(dangerous_warnings) == 0
