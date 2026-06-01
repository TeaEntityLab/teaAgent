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
    assert '(see [use-cases.md](use-cases.md#partial--planned-gaps)).' in text
