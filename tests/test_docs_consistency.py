from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
_VALIDATE_SCRIPT = _SCRIPTS / 'validate_docs_consistency.py'
_TIER_SCRIPT = _SCRIPTS / 'run_acceptance_tier.py'

_VALIDATE_SPEC = spec_from_file_location('validate_docs_consistency', _VALIDATE_SCRIPT)
assert _VALIDATE_SPEC and _VALIDATE_SPEC.loader
_VALIDATE_MODULE = module_from_spec(_VALIDATE_SPEC)
_VALIDATE_SPEC.loader.exec_module(_VALIDATE_MODULE)
validate_docs_consistency = _VALIDATE_MODULE.validate_docs_consistency

_TIER_SPEC = spec_from_file_location('run_acceptance_tier', _TIER_SCRIPT)
assert _TIER_SPEC and _TIER_SPEC.loader
_TIER_MODULE = module_from_spec(_TIER_SPEC)
_TIER_SPEC.loader.exec_module(_TIER_MODULE)
render_tier_markdown = _TIER_MODULE.render_tier_markdown


def test_validate_docs_consistency_passes_when_inputs_match(tmp_path: Path) -> None:
    readme = tmp_path / 'README.md'
    acceptance = tmp_path / 'acceptance.md'
    matrix = tmp_path / 'matrix.md'
    acceptance_dir = tmp_path / 'acceptance_tests'
    acceptance_dir.mkdir()
    (acceptance_dir / 'test_a.py').write_text(
        'def test_a():\n    assert True\n', encoding='utf-8'
    )
    (acceptance_dir / 'test_b.py').write_text(
        'def test_b():\n    assert True\n', encoding='utf-8'
    )

    readme.write_text(
        '(2 providers)\nexport A_API_KEY=\nexport B_API_KEY=\n', encoding='utf-8'
    )
    tier_block = render_tier_markdown()
    acceptance.write_text(
        '`2 passed`\n'
        '<!-- ACCEPTANCE_TIERS:START -->\n\n'
        f'{tier_block}\n\n'
        '<!-- ACCEPTANCE_TIERS:END -->\n',
        encoding='utf-8',
    )
    matrix.write_text('| Use Case | Covered |\n| yes |\n', encoding='utf-8')

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
        check_providers=False,
        check_survey=False,
        check_mode_matrix=False,
        check_surface_recipes=False,
    )
    assert errors == []


def test_validate_docs_consistency_detects_mismatch(tmp_path: Path) -> None:
    readme = tmp_path / 'README.md'
    acceptance = tmp_path / 'acceptance.md'
    matrix = tmp_path / 'matrix.md'
    acceptance_dir = tmp_path / 'acceptance_tests'
    acceptance_dir.mkdir()
    (acceptance_dir / 'test_a.py').write_text(
        'def test_a():\n    assert True\n', encoding='utf-8'
    )

    readme.write_text('(3 providers)\nexport A_API_KEY=\n', encoding='utf-8')
    acceptance.write_text(
        '`2 passed`\n<!-- ACCEPTANCE_TIERS:START -->\nwrong\n<!-- ACCEPTANCE_TIERS:END -->',
        encoding='utf-8',
    )
    matrix.write_text('| x | no |', encoding='utf-8')

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
        check_providers=False,
        check_survey=False,
        check_mode_matrix=False,
        check_surface_recipes=False,
    )
    assert len(errors) == 3


def test_validate_provider_docs_consistency_passes_for_repo_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_provider_docs_consistency(
        readme_text=readme,
        architecture_text=architecture,
        usage_text=usage,
    )
    assert errors == []


def test_validate_survey_doc_passes_for_repo_survey() -> None:
    root = Path(__file__).resolve().parents[1]
    survey = (root / 'scripts' / 'refresh_agent_readme_survey.md').read_text(
        encoding='utf-8'
    )
    errors = _VALIDATE_MODULE.validate_survey_doc(survey)
    assert errors == []


def test_validate_mode_safety_matrix_passes_for_repo_usage() -> None:
    root = Path(__file__).resolve().parents[1]
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_mode_safety_matrix(usage)
    assert errors == []


def test_validate_surface_recipes_passes_for_repo_usage() -> None:
    root = Path(__file__).resolve().parents[1]
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_surface_recipes(usage)
    assert errors == []
