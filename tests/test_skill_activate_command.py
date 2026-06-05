from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from teaagent.cli._handlers._skill import skill_activate_command
from teaagent.skill_loader import _read_activated_skills, explain_skill_activation


def _install_skill(base: Path, rel_dir: str, name: str) -> Path:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n# {name}\n',
        encoding='utf-8',
    )
    return skill_dir


def test_skill_activate_unknown_skill_returns_error(tmp_path: Path) -> None:
    args = argparse.Namespace(name=['nonexistent-skill'], root=str(tmp_path))
    result = skill_activate_command(args)
    assert result == 1


def test_skill_activate_writes_activation_file(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha')

    args = argparse.Namespace(name=['alpha'], root=str(tmp_path))
    result = skill_activate_command(args)
    assert result == 0

    config_path = tmp_path / '.teaagent' / 'activated-skills.json'
    assert config_path.is_file()
    data = json.loads(config_path.read_text(encoding='utf-8'))
    assert data == {'activated_skills': ['alpha']}


def test_skill_activate_records_audit_event(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha')

    with patch(
        'teaagent.cli._handlers._skill.SkillLifecycleTracker',
        autospec=True,
    ) as mock_tracker_cls:
        mock_tracker = mock_tracker_cls.return_value

        args = argparse.Namespace(name=['alpha'], root=str(tmp_path))
        result = skill_activate_command(args)
        assert result == 0

        mock_tracker_cls.assert_called_once_with(run_id='cli_activate')
        mock_tracker.transition.assert_called_once_with(
            'alpha',
            'activated',
            reason='explicitly activated via CLI (activate_skill)',
        )


def test_skill_activate_multiple_names(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha')
    _install_skill(tmp_path, '.config/agent/skills', 'beta')

    args = argparse.Namespace(name=['alpha', 'beta'], root=str(tmp_path))
    result = skill_activate_command(args)
    assert result == 0

    config_path = tmp_path / '.teaagent' / 'activated-skills.json'
    data = json.loads(config_path.read_text(encoding='utf-8'))
    assert 'alpha' in data['activated_skills']
    assert 'beta' in data['activated_skills']


def test_activated_skill_included_in_load_report(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha')

    dot_teaagent = tmp_path / '.teaagent'
    dot_teaagent.mkdir(parents=True, exist_ok=True)
    config_path = dot_teaagent / 'activated-skills.json'
    config_path.write_text(
        json.dumps({'activated_skills': ['alpha']}), encoding='utf-8'
    )

    report = explain_skill_activation(
        tmp_path,
        selected_names=frozenset(),
    )
    assert len(report.loaded) == 1
    assert report.loaded[0].name == 'alpha'


def test_activated_skills_persisted_across_calls(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha')
    _install_skill(tmp_path, '.config/agent/skills', 'beta')

    args = argparse.Namespace(name=['alpha'], root=str(tmp_path))
    skill_activate_command(args)

    args = argparse.Namespace(name=['beta'], root=str(tmp_path))
    skill_activate_command(args)

    activated = _read_activated_skills(str(tmp_path))
    assert activated == frozenset({'alpha', 'beta'})
