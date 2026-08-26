from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.skill_loader import get_skill_diagnostics
from teaagent.tui import TeaAgentTUI
from teaagent.tui._commands import _COMMAND_DISPATCH


@pytest.fixture(autouse=True)
def _isolate_user_skill_dirs(monkeypatch):
    """Keep discovery inside tmp roots — real ~/.claude etc. must not leak."""
    from teaagent import skill_loader

    monkeypatch.setattr(skill_loader, '_USER_SKILL_DIRS', [])
    monkeypatch.setattr(skill_loader, '_EXTENDED_USER_SKILL_DIRS', [])


def _install_skill(base: Path, rel_dir: str, name: str, body: str) -> None:
    skill_dir = base / rel_dir / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name} skill\n---\n{body}\n',
        encoding='utf-8',
    )


def test_diagnostics_structure() -> None:
    """Diagnostics dict must have all expected top-level keys."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        diagnostics = get_skill_diagnostics(root)
        expected_keys = {
            'loaded_skills',
            'active_skill',
            'shadowed_skills',
            'skipped',
            'warnings',
            'searched_dirs',
            'governance_status',
            'candidates',
            'candidate_count',
            'long_result_artifacts',
            'output_verification',
        }
        assert expected_keys.issubset(diagnostics.keys())

        # output_verification must include validators_available and status
        ov = diagnostics['output_verification']
        assert 'validators_available' in ov
        assert 'status' in ov
        assert isinstance(ov['validators_available'], list)
        assert 'FileExistsValidator' in ov['validators_available']


def test_diagnostics_loaded_skills() -> None:
    """Loaded skills appear in diagnostics output when a skill is present."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _install_skill(
            root,
            '.config/agent/skills',
            'test-skill',
            'Test skill body ' * 20,
        )
        # Force eager load by not passing selected_names
        diagnostics = get_skill_diagnostics(root)
        assert isinstance(diagnostics, dict)
        assert 'loaded_skills' in diagnostics
        assert 'active_skill' in diagnostics


def test_diagnostics_loaded_skills_with_patch() -> None:
    """Diagnostics reports loaded skills via patched explain_skill_activation."""
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

    from teaagent.skill_loader import (
        SkillActivationExplain,
        SkillLoadedRecord,
    )

    loaded = (
        SkillLoadedRecord(
            name='alpha',
            path=Path('/tmp/alpha/SKILL.md'),
            source_dir=Path('/tmp/.config/agent/skills'),
            estimated_tokens=200,
            reason='mock',
            governance_status='direct_write',
            lifecycle_state='activated',
        ),
    )
    fake_explain = SkillActivationExplain(
        selection_mode='index_only',
        selected_names=(),
        loaded=loaded,
        shadowed=(),
        skipped=(),
        warnings=(),
        searched_dirs=(Path('/tmp'),),
        estimated_skill_tokens=200,
        index_count=1,
        write_targets={},
    )
    with patch(
        'teaagent.skill_loader.explain_skill_activation',
        return_value=fake_explain,
    ):
        tui.handle_command('skill-diagnostics')

    json_lines = [line for line in output if line.strip().startswith('{')]
    assert len(json_lines) >= 1
    parsed = json.loads(json_lines[0])
    assert isinstance(parsed, dict)
    loaded_skills = parsed.get('loaded_skills', [])
    assert len(loaded_skills) == 1


def test_diagnostics_shadowed_skills() -> None:
    """Shadow detection works — shadowed skills reported in diagnostics."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _install_skill(root, '.config/agent/skills', 'alpha', 'Config a ' * 50)
        _install_skill(root, '.claude/skills', 'alpha', 'Claude a ' * 50)
        diagnostics = get_skill_diagnostics(root)
        shadowed = diagnostics.get('shadowed_skills', [])
        assert len(shadowed) == 1
        assert shadowed[0]['name'] == 'alpha'
        assert 'winner_path' in shadowed[0]
        assert 'shadowed_path' in shadowed[0]


def test_diagnostics_no_skills() -> None:
    """Empty directory returns empty lists, not errors."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        diagnostics = get_skill_diagnostics(root)
        assert diagnostics['loaded_skills'] == []
        assert diagnostics['active_skill'] is None
        assert diagnostics['shadowed_skills'] == []
        assert diagnostics['candidates'] == []
        assert diagnostics['candidate_count'] == 0
        assert isinstance(diagnostics['long_result_artifacts'], dict)


def test_tui_skills_command_registered() -> None:
    """skill-diagnostics command is in the dispatch table."""
    assert 'skill-diagnostics' in _COMMAND_DISPATCH
    handler = _COMMAND_DISPATCH['skill-diagnostics']
    assert callable(handler)


def test_tui_skills_command_returns_true() -> None:
    """skill-diagnostics handler returns True (keep TUI running)."""
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _prompt: 'exit', output_fn=output.append)

    from teaagent.skill_loader import SkillActivationExplain

    fake_explain = SkillActivationExplain(
        selection_mode='index_only',
        selected_names=(),
        loaded=(),
        shadowed=(),
        skipped=(),
        warnings=(),
        searched_dirs=(Path('/tmp'),),
        estimated_skill_tokens=0,
        index_count=0,
        write_targets={},
    )
    with patch(
        'teaagent.skill_loader.explain_skill_activation',
        return_value=fake_explain,
    ):
        result = tui.handle_command('skill-diagnostics')
    assert result
