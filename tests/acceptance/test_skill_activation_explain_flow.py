"""Skill activation explain shows load reason, shadowing, and token contribution."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def _install_skill(tmp_path: Path, rel: str, name: str, body: str) -> None:
    skill_dir = tmp_path / rel / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: {name}\n---\n{body}\n',
        encoding='utf-8',
    )


def test_skill_activation_explain_flow(tmp_path: Path) -> None:
    _install_skill(tmp_path, '.config/agent/skills', 'alpha', 'Alpha ' * 80)
    _install_skill(tmp_path, '.claude/skills', 'alpha', 'Claude ' * 80)
    _install_skill(tmp_path, '.claude/skills', 'beta', 'Beta ' * 80)

    none_out = io.StringIO()
    with redirect_stdout(none_out):
        none_code = main(
            ['skill', 'explain', '--root', str(tmp_path), '--no-auto-skills']
        )
    assert none_code == 0
    none_payload = json.loads(none_out.getvalue())
    assert none_payload['activation']['selection_mode'] == 'none'
    assert none_payload['activation']['estimated_skill_tokens'] == 0

    selected_out = io.StringIO()
    with redirect_stdout(selected_out):
        selected_code = main(
            [
                'skill',
                'explain',
                '--root',
                str(tmp_path),
                '--skill',
                'alpha',
            ]
        )
    assert selected_code == 0
    selected_payload = json.loads(selected_out.getvalue())
    activation = selected_payload['activation']
    assert activation['selection_mode'] == 'selected'
    assert activation['estimated_skill_tokens'] > 0
    assert len(activation['loaded']) == 1
    assert activation['loaded'][0]['name'] == 'alpha'
    assert 'selected explicitly' in activation['loaded'][0]['reason']
    assert any(row['name'] == 'alpha' for row in activation['shadowed'])

    index_out = io.StringIO()
    with redirect_stdout(index_out):
        index_code = main(
            [
                'skill',
                'explain',
                '--root',
                str(tmp_path),
                '--skill-index-only',
            ]
        )
    assert index_code == 0
    index_payload = json.loads(index_out.getvalue())
    assert index_payload['activation']['selection_mode'] == 'index_only'
    assert index_payload['activation']['estimated_skill_tokens'] == 0
    assert index_payload['activation']['index_count'] >= 2
