# test-type: behavior
"""Tests for the cross-host skill audit (AGF-001).

The audit is inventory-only: it must enumerate foreign roots and plugin
caches without loading skill bodies into the active set, mark ``loadable``
honestly, and surface same-name collisions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent import skill_loader
from teaagent.skill_loader import audit_skill_inventory


@pytest.fixture(autouse=True)
def _isolate_user_dirs(monkeypatch):
    """Real ~/.codex etc. must not leak into tmp-root assertions."""
    monkeypatch.setattr(skill_loader, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(skill_loader, '_EXTENDED_USER_SKILL_DIRS', [])
    monkeypatch.setattr(skill_loader, '_FOREIGN_AUDIT_USER_DIRS', [])
    monkeypatch.setattr(
        skill_loader, '_BUILTIN_SKILL_DIR', Path('/nonexistent-builtin')
    )


def _install_skill(base: Path, rel_dir: str, name: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / 'SKILL.md'
    skill_file.write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\nbody\n',
        encoding='utf-8',
    )
    return skill_file


def test_audit_marks_foreign_roots_not_loadable(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.claude/skills', 'alpha')
    foreign = _install_skill(tmp_path, '.codex/plugins', 'beta')

    report = audit_skill_inventory(tmp_path)

    skills = report['skills']
    assert isinstance(skills, list)
    by_name = {item['name']: item for item in skills}
    assert by_name['alpha']['loadable'] is True
    assert by_name['beta']['loadable'] is False
    assert by_name['beta']['host'] == 'codex'
    assert str(foreign) in by_name['beta']['path']


def test_audit_reports_name_collisions_across_roots(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.claude/skills', 'shared')
    _install_skill(tmp_path, '.agents/skills', 'shared')

    report = audit_skill_inventory(tmp_path)

    raw_collisions = report['collisions']
    assert isinstance(raw_collisions, list)
    collisions = {item['name'] for item in raw_collisions}
    assert 'shared' in collisions


def test_audit_does_not_load_skill_bodies(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.claude/skills', 'alpha')
    report = audit_skill_inventory(tmp_path)
    # Inventory entries carry path/host metadata only — no body content.
    skills = report['skills']
    assert isinstance(skills, list)
    assert all('body' not in item and 'content' not in item for item in skills)


def test_audit_missing_roots_are_not_errors(tmp_path: Path) -> None:
    report = audit_skill_inventory(tmp_path)
    assert report['status'] == 'ok'
    assert report['skills'] == []
    assert report['issues'] == []


def test_audit_includes_conflict_protocol(tmp_path: Path) -> None:
    report = audit_skill_inventory(tmp_path)
    assert 'Skill conflict protocol' in report['conflict_protocol']
    assert report['assessment'] == 'not_performed'
