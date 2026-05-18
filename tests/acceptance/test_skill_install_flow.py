"""AC-NEW-10: Skill discovery and prompt injection flow.

As a platform engineer, I want to install skills into the workspace skill
directories and have them automatically injected into the agent system prompt,
so that domain-specific instructions reach the model without manual prompt engineering.

Acceptance criteria:
- Skills placed under the highest-priority directory are discovered.
- Skill content appears in the assembled system prompt.
- Multiple skills all appear.
- Project-level skills override user-level skills with the same name.
- Skills section is absent when no skills are installed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.prompt import assemble_agent_prompt
from teaagent.skill_loader import load_skills, skills_to_prompt_section
from teaagent.tools import ToolRegistry


def _install_skill(root: Path, name: str, content: str) -> None:
    skill_dir = root / '.config' / 'agent' / 'skills' / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if not content.startswith('---\n'):
        content = (
            f'---\nname: {name}\ndescription: acceptance skill {name}\n---\n\n{content}'
        )
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


def test_invalid_skill_is_blocked_from_prompt_injection(tmp_path):
    skill_dir = tmp_path / '.config' / 'agent' / 'skills' / 'invalid'
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        '# Invalid Skill\nNo YAML frontmatter.\n', encoding='utf-8'
    )

    with patch(
        'teaagent.skill_loader._USER_SKILL_DIRS', [tmp_path / '.missing-skills']
    ):
        skills = load_skills(tmp_path)
    assert skills == []


def test_skill_loader_searches_legacy_and_plural_project_dirs(tmp_path):
    skill_dir = tmp_path / '.opencode' / 'skills' / 'plural-dir-skill'
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: plural-dir-skill\ndescription: from plural directory\n---\n\n# Plural\nLoaded.\n',
        encoding='utf-8',
    )

    with patch(
        'teaagent.skill_loader._USER_SKILL_DIRS', [tmp_path / '.missing-skills']
    ):
        skills = load_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == 'plural-dir-skill'


def test_skill_directory_priority_agent_then_claude_then_opencode(tmp_path):
    same_name = 'shared-order'
    paths = [
        tmp_path / '.config' / 'agent' / 'skills' / same_name / 'SKILL.md',
        tmp_path / '.claude' / 'skills' / same_name / 'SKILL.md',
        tmp_path / '.opencode' / 'skill' / same_name / 'SKILL.md',
    ]
    contents = [
        '---\nname: shared-order\ndescription: agent priority\n---\n\n# Agent\nfrom agent\n',
        '---\nname: shared-order\ndescription: claude priority\n---\n\n# Claude\nfrom claude\n',
        '---\nname: shared-order\ndescription: opencode priority\n---\n\n# OpenCode\nfrom opencode\n',
    ]
    for path, content in zip(paths, contents, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    with patch(
        'teaagent.skill_loader._USER_SKILL_DIRS', [tmp_path / '.missing-skills']
    ):
        skills = load_skills(tmp_path)
    selected = [skill for skill in skills if skill.name == same_name]
    assert len(selected) == 1
    assert 'from agent' in selected[0].content


def test_skill_load_audit_records_search_dirs_and_review_failures(tmp_path):
    _install_skill(tmp_path, 'valid', '# Valid\nWorks.')
    bad_dir = tmp_path / '.config' / 'agent' / 'skills' / 'invalid'
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / 'SKILL.md').write_text('# Invalid\nNo frontmatter.\n', encoding='utf-8')

    class _AuditStubAdapter:
        provider = 'stub'

        def complete(self, request):  # type: ignore[override]
            from teaagent.llm import LLMResponse

            assert 'Works.' in (request.system or '')
            assert 'No frontmatter' not in (request.system or '')
            return LLMResponse(
                provider='stub',
                model='stub',
                content='{"type":"final","content":"ok"}',
            )

    audit = AuditLogger()
    result = run_chat_agent(
        task='check skills',
        adapter=_AuditStubAdapter(),
        config=ChatAgentConfig.from_root(tmp_path),
        audit=audit,
    )
    assert result.status == 'completed'

    load_events = [event for event in audit.events if event.event_type == 'skill_load']
    assert len(load_events) == 1
    payload = load_events[0].payload
    searched = payload['searched_dirs']
    assert any(path.endswith('/.config/agent/skills') for path in searched)
    assert len(payload['skipped']) == 1
    assert payload['skipped'][0]['reason'] == 'skill review failed'
    assert any(
        finding['severity'] == 'error' for finding in payload['skipped'][0]['findings']
    )


def test_skill_load_audit_records_truncation_warning(tmp_path):
    large_content = 'A' * 40000
    _install_skill(
        tmp_path,
        'huge',
        ('# Huge\n' + large_content),
    )

    class _TruncationAuditStubAdapter:
        provider = 'stub'

        def complete(self, request):  # type: ignore[override]
            from teaagent.llm import LLMResponse

            return LLMResponse(
                provider='stub',
                model='stub',
                content='{"type":"final","content":"ok"}',
            )

    audit = AuditLogger()
    result = run_chat_agent(
        task='check truncation',
        adapter=_TruncationAuditStubAdapter(),
        config=ChatAgentConfig.from_root(tmp_path),
        audit=audit,
    )
    assert result.status == 'completed'
    load_event = next(
        event for event in audit.events if event.event_type == 'skill_load'
    )
    assert any(
        'truncated' in warning['message'] for warning in load_event.payload['warnings']
    )


def test_run_chat_agent_uses_configured_skill_search_dirs(tmp_path):
    custom_skill = tmp_path / 'custom' / 'skills' / 'only-custom' / 'SKILL.md'
    custom_skill.parent.mkdir(parents=True, exist_ok=True)
    custom_skill.write_text(
        '---\nname: only-custom\ndescription: custom configured path\n---\n\n# Custom\ncustom skill loaded\n',
        encoding='utf-8',
    )

    class _ConfiguredPathStubAdapter:
        provider = 'stub'

        def complete(self, request):  # type: ignore[override]
            from teaagent.llm import LLMResponse

            assert 'custom skill loaded' in (request.system or '')
            return LLMResponse(
                provider='stub',
                model='stub',
                content='{"type":"final","content":"ok"}',
            )

    audit = AuditLogger()
    config = ChatAgentConfig.from_root(
        tmp_path, skill_search_dirs=['custom/skills', '.opencode/skill']
    )
    result = run_chat_agent(
        task='configured skill dirs',
        adapter=_ConfiguredPathStubAdapter(),
        config=config,
        audit=audit,
    )
    assert result.status == 'completed'
    load_event = next(
        event for event in audit.events if event.event_type == 'skill_load'
    )
    assert any(
        path.endswith('/custom/skills') for path in load_event.payload['searched_dirs']
    )


def test_run_chat_agent_custom_profile_requires_skill_search_dirs(tmp_path):
    class _NoopAdapter:
        provider = 'stub'

        def complete(self, request):  # type: ignore[override]
            from teaagent.llm import LLMResponse

            return LLMResponse(
                provider='stub',
                model='stub',
                content='{"type":"final","content":"ok"}',
            )

    try:
        run_chat_agent(
            task='custom profile missing dirs',
            adapter=_NoopAdapter(),
            config=ChatAgentConfig.from_root(tmp_path, skill_source_profile='custom'),
            audit=AuditLogger(),
        )
        raise AssertionError('expected ValueError for missing skill_search_dirs')
    except ValueError as exc:
        assert 'requires skill_search_dirs' in str(exc)
