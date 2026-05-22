from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_refresh_module():
    script = (
        Path(__file__).resolve().parents[1] / 'scripts' / 'refresh_competitive_docs.py'
    )
    spec = spec_from_file_location('refresh_competitive_docs', script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_refresh_competitive_docs_passes_for_repo(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_refresh_module()
    acceptance_copy = tmp_path / 'acceptance.md'
    acceptance_copy.write_text(
        (root / 'docs' / 'acceptance.md').read_text(encoding='utf-8'),
        encoding='utf-8',
    )
    errors = module.refresh_competitive_docs(
        acceptance_doc=acceptance_copy,
        acceptance_tests_dir=root / 'tests' / 'acceptance',
        matrix_output=tmp_path / 'matrix.md',
        dashboard_output=tmp_path / 'matrix.html',
        survey_doc=root / 'scripts' / 'refresh_agent_readme_survey.md',
        use_cases_doc=root / 'docs' / 'use-cases.md',
        acceptance_source='collect',
    )
    assert errors == []
    assert (tmp_path / 'matrix.md').is_file()
    assert 'Subagent lineage and isolation' in (tmp_path / 'matrix.md').read_text(
        encoding='utf-8'
    )
    assert (tmp_path / 'matrix.html').is_file()


def test_check_competitive_docs_passes_without_mutating_tracked_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_refresh_module()
    tracked_paths = [
        root / 'docs' / 'acceptance.md',
        root / 'docs' / 'use-case-matrix.md',
        root / 'docs' / 'use-case-matrix.html',
    ]
    before = {path: path.read_text(encoding='utf-8') for path in tracked_paths}

    errors = module.check_competitive_docs(
        acceptance_doc=root / 'docs' / 'acceptance.md',
        acceptance_tests_dir=root / 'tests' / 'acceptance',
        matrix_output=root / 'docs' / 'use-case-matrix.md',
        dashboard_output=root / 'docs' / 'use-case-matrix.html',
        survey_doc=root / 'scripts' / 'refresh_agent_readme_survey.md',
        use_cases_doc=root / 'docs' / 'use-cases.md',
        acceptance_source='collect',
    )

    assert errors == []
    after = {path: path.read_text(encoding='utf-8') for path in tracked_paths}
    assert after == before


def test_check_competitive_docs_reports_stale_generated_file(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    module = _load_refresh_module()
    acceptance_copy = tmp_path / 'acceptance.md'
    matrix = tmp_path / 'matrix.md'
    dashboard = tmp_path / 'matrix.html'
    acceptance_copy.write_text(
        (root / 'docs' / 'acceptance.md').read_text(encoding='utf-8'),
        encoding='utf-8',
    )
    assert (
        module.refresh_competitive_docs(
            acceptance_doc=acceptance_copy,
            acceptance_tests_dir=root / 'tests' / 'acceptance',
            matrix_output=matrix,
            dashboard_output=dashboard,
            survey_doc=root / 'scripts' / 'refresh_agent_readme_survey.md',
            use_cases_doc=root / 'docs' / 'use-cases.md',
            acceptance_source='collect',
        )
        == []
    )
    matrix.write_text(
        matrix.read_text(encoding='utf-8') + '\nSTALE\n', encoding='utf-8'
    )

    errors = module.check_competitive_docs(
        acceptance_doc=acceptance_copy,
        acceptance_tests_dir=root / 'tests' / 'acceptance',
        matrix_output=matrix,
        dashboard_output=dashboard,
        survey_doc=root / 'scripts' / 'refresh_agent_readme_survey.md',
        use_cases_doc=root / 'docs' / 'use-cases.md',
        acceptance_source='collect',
    )

    assert any('is out of date' in error for error in errors)


def test_main_check_mode_accepts_argv() -> None:
    module = _load_refresh_module()
    assert module.main(['--check']) == 0
