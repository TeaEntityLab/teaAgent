"""AC-NEW-10: Skill discovery and prompt injection flow.

As a platform engineer, I want to install skills into the workspace .opencode/skill/
directory and have them automatically injected into the agent system prompt,
so that domain-specific instructions reach the model without manual prompt engineering.

Acceptance criteria:
- Skills placed under ``.opencode/skill/<name>/SKILL.md`` are discovered.
- Skill content appears in the assembled system prompt.
- Multiple skills all appear.
- Project-level skills override user-level skills with the same name.
- Skills section is absent when no skills are installed.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.prompt import assemble_agent_prompt
from teaagent.skill_loader import load_skills, skills_to_prompt_section
from teaagent.tools import ToolRegistry


def _install_skill(root: Path, name: str, content: str) -> None:
    skill_dir = root / '.opencode' / 'skill' / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(content, encoding='utf-8')


def test_skill_discovered_and_injected(tmp_path):
    _install_skill(
        tmp_path, 'docgen', '# DocGen\nAlways write Google-style docstrings.'
    )

    skills = load_skills(tmp_path)
    registry = ToolRegistry()
    bundle = assemble_agent_prompt(
        task='write a function',
        context={'task': 'write a function', 'observations': []},
        registry=registry,
        skills=skills,
    )
    assert 'Google-style docstrings' in bundle.system


def test_multiple_skills_all_appear(tmp_path):
    _install_skill(tmp_path, 'testing', '# Testing\nWrite pytest unit tests.')
    _install_skill(tmp_path, 'security', '# Security\nScan for OWASP top 10.')

    skills = load_skills(tmp_path)
    section = skills_to_prompt_section(skills)
    assert 'pytest unit tests' in section
    assert 'OWASP top 10' in section


def test_no_skills_section_absent(tmp_path):
    registry = ToolRegistry()
    bundle = assemble_agent_prompt(
        task='hello',
        context={'task': 'hello', 'observations': []},
        registry=registry,
        skills=[],
    )
    assert 'Skills:' not in bundle.system


def test_project_skill_overrides_user_skill(tmp_path):
    _install_skill(tmp_path, 'shared', '# PROJECT version\nUse tabs for indentation.')
    user_dir = tmp_path / 'user_skills_dir'
    user_skill = user_dir / 'shared'
    user_skill.mkdir(parents=True)
    (user_skill / 'SKILL.md').write_text(
        '# USER version\nUse spaces.', encoding='utf-8'
    )

    skills = load_skills(tmp_path, extra_skill_dirs=[user_dir])
    shared = [s for s in skills if s.name == 'shared']
    assert len(shared) == 1
    assert 'tabs for indentation' in shared[0].content


class _StubAdapter:
    provider = 'stub'

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        # Verify skill content reached the system prompt
        assert 'Always write Google-style docstrings' in (request.system or '')
        return LLMResponse(
            provider='stub',
            model='stub',
            content='{"type":"final","content":"skill received"}',
        )


def test_skill_reaches_model_system_prompt(tmp_path):
    _install_skill(
        tmp_path, 'docgen', '# DocGen\nAlways write Google-style docstrings.'
    )
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    result = run_chat_agent(task='write code', adapter=adapter, config=config)
    assert result.status == 'completed'
    assert result.final_answer is not None
    assert result.final_answer.content == 'skill received'
