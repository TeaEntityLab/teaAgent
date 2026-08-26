from __future__ import annotations

from pathlib import Path

import pytest

from teaagent import skill_loader
from teaagent.skill_loader import explain_skill_activation


@pytest.fixture(autouse=True)
def _isolate_user_skill_dirs(monkeypatch):
    """Real ~/.claude etc. must not leak into tmp-root shadow assertions."""
    monkeypatch.setattr(skill_loader, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(skill_loader, '_EXTENDED_USER_SKILL_DIRS', [])


def _install_skill(base: Path, rel_dir: str, name: str, body: str) -> None:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )


def test_explain_reports_shadowed_duplicate_skill(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Config alpha ' * 50)
    _install_skill(tmp_path, '.claude/skills', 'alpha', 'Claude alpha ' * 50)
    report = explain_skill_activation(tmp_path, selected_names=frozenset({'alpha'}))
    assert report.selection_mode == 'selected'
    assert len(report.loaded) == 1
    assert report.loaded[0].name == 'alpha'
    assert report.estimated_skill_tokens > 0
    assert len(report.shadowed) == 1
    assert report.shadowed[0].name == 'alpha'


def test_explain_no_auto_skills_zero_tokens(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.claude/skills', 'alpha', 'Alpha ' * 100)
    report = explain_skill_activation(tmp_path, selected_names=frozenset())
    assert report.selection_mode == 'none'
    assert report.estimated_skill_tokens == 0
    assert report.loaded == ()
