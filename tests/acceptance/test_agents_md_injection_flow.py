"""AC-NEW-11: Hierarchical agent instruction injection flow.

As a project maintainer, I want workspace instruction markdown files to be
automatically injected into the model system prompt, so that project-specific
rules are consistently enforced.

Acceptance criteria:
- Instructions are discovered across parent/child directories.
- Merge order is parent first, then child.
- Fallback filenames (CLAUDE.md, AGENT.md) are also loaded.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.prompt import load_project_instructions


def test_hierarchical_agents_md_injection_order(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    nested = repo / 'apps' / 'api'
    nested.mkdir(parents=True)
    (repo / 'AGENTS.md').write_text('repo-rule\n', encoding='utf-8')
    (repo / 'apps' / 'AGENTS.md').write_text('apps-rule\n', encoding='utf-8')
    (nested / 'AGENTS.md').write_text('api-rule\n', encoding='utf-8')

    merged = load_project_instructions(nested)

    assert 'repo-rule' in merged
    assert 'apps-rule' in merged
    assert 'api-rule' in merged
    assert (
        merged.index('repo-rule') < merged.index('apps-rule') < merged.index('api-rule')
    )


def test_fallback_instruction_files_are_loaded(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    project = repo / 'service'
    project.mkdir(parents=True)
    (repo / 'AGENT.md').write_text('root-agent-md\n', encoding='utf-8')
    (project / 'CLAUDE.md').write_text('project-claude-md\n', encoding='utf-8')

    merged = load_project_instructions(project)

    assert 'root-agent-md' in merged
    assert 'project-claude-md' in merged
