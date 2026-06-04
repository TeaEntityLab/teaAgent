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
    roadmap = tmp_path / 'roadmap-status.md'
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
    roadmap.write_text(
        '# Roadmap Status\n\n'
        '| H0 | Claim and risk hygiene | documentation-current-truth |\n'
        'doc-vs-HEAD guard\n',
        encoding='utf-8',
    )

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
        roadmap_status_path=roadmap,
        check_providers=False,
        check_survey=False,
        check_mode_matrix=False,
        check_surface_recipes=False,
        check_catalog=False,
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
    assert len(errors) == 3  # status, tier sync, uncovered matrix row


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


def test_validate_plugin_skill_catalog_passes_for_repo_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = (root / 'docs' / 'plugin-skill-catalog.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_plugin_skill_catalog(catalog, repo_root=root)
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


def test_validate_roadmap_status_passes_for_repo_roadmap() -> None:
    root = Path(__file__).resolve().parents[1]
    roadmap = (root / 'docs' / 'roadmap-status.md').read_text(encoding='utf-8')
    errors = _VALIDATE_MODULE.validate_roadmap_status(roadmap)
    assert errors == []


def test_validate_roadmap_status_detects_missing_h0_truth_links() -> None:
    roadmap = (
        '# Roadmap Status\n\n'
        '| H0 | Claim and risk hygiene | Public claims are owned |\n'
    )
    errors = _VALIDATE_MODULE.validate_roadmap_status(roadmap)
    assert (
        'Roadmap status missing documentation-current-truth work reference.' in errors
    )
    assert 'Roadmap status missing doc-vs-HEAD guard reference.' in errors


def test_validate_provider_docs_detects_stale_llm_adapter_count() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    usage = (root / 'docs' / 'USAGE.md').read_text(encoding='utf-8')
    stale = architecture.replace('14 providers', '15 providers', 1)
    stale = stale.replace(
        'across 14 registered providers', 'across 15 registered providers', 1
    )
    stale = stale.replace('14 LLM providers', '15 LLM providers', 1)
    errors = _VALIDATE_MODULE.validate_provider_docs_consistency(
        readme_text=readme,
        architecture_text=stale,
        usage_text=usage,
    )
    assert any('mismatch' in err for err in errors)


def test_validate_date_coherence_detects_use_cases_survey_drift() -> None:
    root = Path(__file__).resolve().parents[1]
    survey = (root / 'scripts' / 'refresh_agent_readme_survey.md').read_text(
        encoding='utf-8'
    )
    matrix = (root / 'docs' / 'use-case-matrix.md').read_text(encoding='utf-8')
    catalog = (root / 'docs' / 'plugin-skill-catalog.md').read_text(encoding='utf-8')
    use_cases = (root / 'docs' / 'use-cases.md').read_text(encoding='utf-8')
    architecture = (root / 'docs' / 'architecture.md').read_text(encoding='utf-8')
    stale = use_cases.replace(
        '2026-05-24 landscape survey', '2026-05-22 landscape survey', 1
    )
    errors = _VALIDATE_MODULE.validate_date_coherence(
        survey_text=survey,
        matrix_text=matrix,
        catalog_text=catalog,
        use_cases_text=stale,
        architecture_text=architecture,
    )
    assert any('Date drift detected' in err for err in errors)


def test_validate_matrix_open_gap_count_detects_stale_matrix() -> None:
    root = Path(__file__).resolve().parents[1]
    matrix = (root / 'docs' / 'use-case-matrix.md').read_text(encoding='utf-8')
    stale = matrix.replace(
        'Open partial/planned gaps (P1/P2): **3**',
        'Open partial/planned gaps (P1/P2): **0**',
        1,
    )
    errors = _VALIDATE_MODULE.validate_matrix_open_gap_count(
        matrix_text=stale,
        use_cases_path=root / 'docs' / 'use-cases.md',
    )
    assert any('open gap count mismatch' in err for err in errors)


def test_open_partial_planned_gap_count_matches_use_cases_section() -> None:
    root = Path(__file__).resolve().parents[1]
    build_matrix = _VALIDATE_MODULE._load_build_use_case_matrix_module()
    count = build_matrix._open_backlog_gap_count(root / 'docs' / 'use-cases.md')
    assert count == 3
