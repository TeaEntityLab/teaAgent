from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / 'scripts' / 'validate_docs_consistency.py'
)
_SPEC = spec_from_file_location('validate_docs_consistency', _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
validate_docs_consistency = _MODULE.validate_docs_consistency


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
    acceptance.write_text(
        '`2 passed`\n'
        '<!-- ACCEPTANCE_TIERS:START -->\n\n'
        '## Acceptance Tiers (P0/P1/P2)\n\n'
        'Use these tiers to control regression scope and release risk:\n\n'
        '| Tier | Purpose | Representative acceptance flows |\n'
        '|---|---|---|\n'
        '| P0 | Safe first-run, policy boundaries, and core coding loop | `test_first_run_experience_flow.py`, `test_daily_cli.py`, `test_p0_slo_flow.py`, `test_plan_mode_read_only_flow.py`, `test_workspace_edit_flow.py`, `test_agent_fix_test_review_flow.py`, `test_policy_as_code_flow.py` |\n'
        '| P1 | Recovery, continuity, and IDE/runtime surface reliability | `test_run_undo_acceptance_flow.py`, `test_session_resume_continuity_flow.py`, `test_vscode_mcp_runtime_smoke_flow.py`, `test_mcp_client_flow.py` |\n'
        '| P2 | Ecosystem compatibility and extended operations | `test_backend_adapter_flow.py`, `test_external_tool_manifest_compatibility_flow.py`, `test_remote_mcp_consumption_flow.py`, `test_ultrawork_flow.py`, `test_webhook_audit_flow.py` |\n\n'
        'Recommended execution cadence:\n\n'
        '1. Every PR: run all P0.\n'
        '2. Before merge to `main`: run P0 + P1.\n'
        '3. Before release: run full acceptance (P0 + P1 + P2).\n\n'
        '<!-- ACCEPTANCE_TIERS:END -->\n',
        encoding='utf-8',
    )
    matrix.write_text('| Use Case | Covered |\n| yes |\n', encoding='utf-8')

    errors = validate_docs_consistency(
        readme_path=readme,
        acceptance_doc_path=acceptance,
        use_case_matrix_path=matrix,
        acceptance_tests_dir=acceptance_dir,
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
    )
    assert len(errors) == 4
