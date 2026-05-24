"""AC-NEW: --skill-index-only injects metadata without SKILL.md bodies."""

from __future__ import annotations

from pathlib import Path

from teaagent.prompt import assemble_agent_prompt
from teaagent.skill_loader import (
    discover_skill_index,
    load_skills_with_report,
    skill_index_to_prompt_section,
)
from teaagent.tools import ToolRegistry


def _install_skill(tmp_path: Path) -> None:
    skill_dir = tmp_path / '.claude' / 'skills' / 'alpha'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: alpha\ndescription: alpha skill\n---\n'
        'Visible summary line for index.\n' + ('SECRET_INSTRUCTION ' * 100) + '\n',
        encoding='utf-8',
    )


def test_skill_index_only_prompt_excludes_skill_bodies(tmp_path: Path) -> None:
    _install_skill(tmp_path)
    index = discover_skill_index(tmp_path)
    eager = load_skills_with_report(tmp_path)
    index_only = load_skills_with_report(tmp_path, selected_names=frozenset())

    assert eager.skills
    assert index_only.skills == []
    assert 'SECRET_INSTRUCTION' in (eager.skills[0].content if eager.skills else '')

    bundle = assemble_agent_prompt(
        task='Do work',
        context={},
        registry=ToolRegistry(),
        skill_index=index,
        skills=index_only.skills,
    )
    assert 'Available skills (metadata only' in bundle.system
    assert 'alpha: Visible summary line for index.' in bundle.system
    assert 'SECRET_INSTRUCTION' not in bundle.system
    assert skill_index_to_prompt_section(index)
