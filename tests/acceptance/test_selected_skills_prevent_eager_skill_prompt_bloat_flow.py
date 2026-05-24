"""AC-NEW: Selected-skill loading prevents eager skill prompt bloat."""

from __future__ import annotations

from pathlib import Path

from teaagent.skill_loader import estimate_skill_prompt_tokens, load_skills_with_report


def _install_skill(tmp_path: Path, name: str, body: str) -> None:
    skill_dir = tmp_path / '.claude' / 'skills' / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: test skill\n---\n{body}\n',
        encoding='utf-8',
    )


def test_no_auto_skills_keeps_prompt_ledger_at_zero_tokens(tmp_path: Path) -> None:
    _install_skill(tmp_path, 'alpha', 'Alpha ' * 200)
    _install_skill(tmp_path, 'beta', 'Beta ' * 200)
    eager = load_skills_with_report(tmp_path)
    assert estimate_skill_prompt_tokens(eager.skills) > 0

    selected_empty = load_skills_with_report(tmp_path, selected_names=frozenset())
    assert selected_empty.skills == []
    assert estimate_skill_prompt_tokens(selected_empty.skills) == 0

    one_skill = load_skills_with_report(tmp_path, selected_names=frozenset({'alpha'}))
    assert len(one_skill.skills) == 1
    assert one_skill.skills[0].name == 'alpha'
    assert estimate_skill_prompt_tokens(
        one_skill.skills
    ) < estimate_skill_prompt_tokens(eager.skills)
