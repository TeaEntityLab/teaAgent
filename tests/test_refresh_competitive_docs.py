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
    errors = module.refresh_competitive_docs(
        acceptance_doc=root / 'docs' / 'acceptance.md',
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
