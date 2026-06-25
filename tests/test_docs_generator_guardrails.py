from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_use_case_matrix import build_use_case_matrix


def test_build_use_case_matrix_requires_survey_review_date(tmp_path: Path) -> None:
    acceptance = tmp_path / 'acceptance.md'
    acceptance.write_text('# Acceptance\n\n', encoding='utf-8')
    output = tmp_path / 'use-case-matrix.md'
    survey = tmp_path / 'survey.md'
    survey.write_text('# Survey\n\n(no date)\n', encoding='utf-8')
    use_cases = tmp_path / 'use-cases.md'
    use_cases.write_text('# Use Cases\n', encoding='utf-8')

    with pytest.raises(ValueError, match='Last reviewed: \\*\\*YYYY-MM-DD\\*\\*'):
        build_use_case_matrix(
            acceptance_path=acceptance,
            output_path=output,
            survey_path=survey,
            use_cases_path=use_cases,
            repo_root=tmp_path,
        )


def test_build_use_case_matrix_includes_canonical_markers(tmp_path: Path) -> None:
    acceptance = tmp_path / 'acceptance.md'
    acceptance.write_text(
        '# Acceptance\n\n- `test_example_flow.py`\n',
        encoding='utf-8',
    )
    output = tmp_path / 'use-case-matrix.md'
    survey = tmp_path / 'survey.md'
    survey.write_text('Last reviewed: **2026-05-31**\n', encoding='utf-8')
    use_cases = tmp_path / 'use-cases.md'
    use_cases.write_text('## Partial / Planned Gaps\n\n', encoding='utf-8')

    build_use_case_matrix(
        acceptance_path=acceptance,
        output_path=output,
        survey_path=survey,
        use_cases_path=use_cases,
        repo_root=tmp_path,
    )

    text = output.read_text(encoding='utf-8')
    assert 'Landscape survey reviewed: **2026-05-31**' in text
    assert 'Open partial/planned gaps (P1/P2): **' in text
    assert (
        'Generated from `docs/acceptance.md` by `scripts/build_use_case_matrix.py`.'
        in text
    )
    assert (
        '([../scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md)).'
        in text
    )
    assert (
        '(see [use-cases.md](use-cases.md#partial--planned-gaps-docs--packaging)).'
        in text
    )


def test_release_docs_evidence_check_allows_clean_meta_commit_lag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    import subprocess

    from scripts import build_release_docs_evidence_bundle as mod

    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init'], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test'],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / 'README.md').write_text('# test\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'README.md'], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'init'],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    first_commit = mod._git_field(repo, 'rev-parse', 'HEAD')
    bundle = {
        'ok': True,
        'created_at': '2026-01-01T00:00:00+00:00',
        'repo_root': str(repo),
        'git': {'branch': 'main', 'commit': first_commit, 'dirty': False},
        'commands': [],
        'docs_freshness': {
            'scanned': 0,
            'needs_attention': 0,
            'by_owner': {},
            'stale_threshold_days': 90,
        },
        'roadmap_excerpt': {'horizons': [], 'milestones': []},
        'open_risks': [],
        'okf_catalogs': [],
        'regenerate_commands': [
            'python3 scripts/build_release_docs_evidence_bundle.py'
        ],
    }
    md_path = repo / 'docs' / 'generated' / 'release-docs-evidence.md'
    json_path = repo / 'docs' / 'generated' / 'release-docs-evidence.json'
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        mod.format_release_docs_evidence_markdown(bundle), encoding='utf-8'
    )
    json_path.write_text(json.dumps(bundle), encoding='utf-8')

    (repo / 'docs' / 'note.md').write_text('meta\n', encoding='utf-8')
    subprocess.run(
        ['git', 'add', 'docs/note.md'], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'docs: meta'],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    def fake_build(*, repo_root: Path, run_gates: bool = True) -> dict:
        del run_gates
        assert repo_root.resolve() == repo.resolve()
        advanced = dict(bundle)
        advanced['git'] = {
            'branch': 'main',
            'commit': mod._git_field(repo, 'rev-parse', 'HEAD'),
            'dirty': False,
        }
        return advanced

    monkeypatch.setattr(mod, 'build_release_docs_evidence_bundle', fake_build)

    assert (
        mod.check_release_docs_evidence_bundle(
            repo_root=repo,
            markdown_path=md_path,
            json_path=json_path,
        )
        == []
    )
