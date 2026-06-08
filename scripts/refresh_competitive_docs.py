from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(script_name: str):
    path = _REPO_ROOT / 'scripts' / script_name
    spec = spec_from_file_location(script_name.replace('.py', ''), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {path}')
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def refresh_competitive_docs(
    *,
    acceptance_doc: Path,
    acceptance_tests_dir: Path,
    matrix_output: Path,
    dashboard_output: Path,
    survey_doc: Path,
    use_cases_doc: Path,
    acceptance_source: str,
) -> list[str]:
    errors: list[str] = []
    build_acceptance_status = _load_module('build_acceptance_status.py')
    build_use_case_matrix = _load_module('build_use_case_matrix.py')

    count = build_acceptance_status.build_acceptance_status(
        acceptance_doc=acceptance_doc,
        passed_count=None,
        source=acceptance_source,
        acceptance_tests_dir=acceptance_tests_dir,
    )
    print(f'acceptance status: {count} passed')

    build_use_case_matrix.build_use_case_matrix(
        acceptance_path=acceptance_doc,
        output_path=matrix_output,
        survey_path=survey_doc,
        use_cases_path=use_cases_doc,
    )
    print(f'wrote {matrix_output}')

    render = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / 'scripts' / 'render_use_case_dashboard.py'),
            '--matrix',
            str(matrix_output),
            '--output',
            str(dashboard_output),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if render.returncode != 0:
        errors.append(
            'render_use_case_dashboard failed:\n'
            f'{render.stdout}\n{render.stderr}'.strip()
        )
    else:
        print(f'wrote {dashboard_output}')

    validate_docs = _load_module('validate_docs_consistency.py')
    aging_module = _load_module('report_docs_aging.py')
    aging_module.write_docs_aging_dashboard()
    inventory_module = _load_module('generate_docs_inventory.py')
    inventory_module.write_docs_inventory()

    errors.extend(
        validate_docs.validate_docs_consistency(
            readme_path=_REPO_ROOT / 'README.md',
            acceptance_doc_path=acceptance_doc,
            use_case_matrix_path=matrix_output,
            acceptance_tests_dir=acceptance_tests_dir,
            usage_path=_REPO_ROOT / 'docs' / 'USAGE.md',
            architecture_path=_REPO_ROOT / 'docs' / 'architecture.md',
            survey_path=survey_doc,
            catalog_path=_REPO_ROOT / 'docs' / 'plugin-skill-catalog.md',
        )
    )
    return errors


def _compare_generated_file(*, expected: Path, actual: Path) -> list[str]:
    if not expected.is_file():
        return [f'Generated docs check target missing: {expected}']
    if not actual.is_file():
        return [f'Generated docs check output missing: {actual}']
    expected_text = expected.read_text(encoding='utf-8')
    actual_text = actual.read_text(encoding='utf-8')
    if expected_text == actual_text:
        return []
    rel = (
        expected.relative_to(_REPO_ROOT)
        if expected.is_relative_to(_REPO_ROOT)
        else expected
    )
    return [f'{rel} is out of date; run: python3 scripts/refresh_competitive_docs.py']


def check_ergonomics_kpi(repo_root: Path) -> list[str]:
    kpi_path = repo_root / 'docs' / 'ergonomics-kpi.json'
    if not kpi_path.is_file():
        return [
            'docs/ergonomics-kpi.json missing; run: '
            'python3 scripts/measure_time_to_first_run.py --write docs/ergonomics-kpi.json'
        ]
    try:
        data = json.loads(kpi_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return [f'docs/ergonomics-kpi.json invalid: {exc}']
    if not isinstance(data.get('seconds'), (int, float)):
        return ['docs/ergonomics-kpi.json must include numeric "seconds"']
    return []


def check_competitive_docs(
    *,
    acceptance_doc: Path,
    acceptance_tests_dir: Path,
    matrix_output: Path,
    dashboard_output: Path,
    survey_doc: Path,
    use_cases_doc: Path,
    acceptance_source: str,
) -> list[str]:
    """Generate docs in a tempdir and compare without mutating tracked files."""
    with tempfile.TemporaryDirectory(prefix='teaagent-competitive-docs-') as raw_tmp:
        tmp = Path(raw_tmp)
        tmp_acceptance = tmp / acceptance_doc.name
        tmp_matrix = tmp / matrix_output.name
        tmp_dashboard = tmp / dashboard_output.name
        shutil.copy2(acceptance_doc, tmp_acceptance)

        errors = refresh_competitive_docs(
            acceptance_doc=tmp_acceptance,
            acceptance_tests_dir=acceptance_tests_dir,
            matrix_output=tmp_matrix,
            dashboard_output=tmp_dashboard,
            survey_doc=survey_doc,
            use_cases_doc=use_cases_doc,
            acceptance_source=acceptance_source,
        )
        errors.extend(
            _compare_generated_file(expected=acceptance_doc, actual=tmp_acceptance)
        )
        errors.extend(
            _compare_generated_file(expected=matrix_output, actual=tmp_matrix)
        )
        errors.extend(
            _compare_generated_file(expected=dashboard_output, actual=tmp_dashboard)
        )
        errors.extend(check_ergonomics_kpi(_REPO_ROOT))
        return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Run competitive-docs refresh steps from docs/release-checklist.md.'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Generate into a temporary directory and fail if tracked docs are stale.',
    )
    parser.add_argument('--acceptance-doc', default='docs/acceptance.md')
    parser.add_argument('--acceptance-tests-dir', default='tests/acceptance')
    parser.add_argument('--matrix-output', default='docs/use-case-matrix.md')
    parser.add_argument('--dashboard-output', default='docs/use-case-matrix.html')
    parser.add_argument(
        '--survey-doc', default='scripts/refresh_agent_readme_survey.md'
    )
    parser.add_argument('--use-cases-doc', default='docs/use-cases.md')
    parser.add_argument(
        '--acceptance-source',
        choices=('collect', 'pytest'),
        default='collect',
        help='How to count acceptance tests for docs/acceptance.md status.',
    )
    args = parser.parse_args(argv)

    inputs = {
        'acceptance_doc': _REPO_ROOT / args.acceptance_doc,
        'acceptance_tests_dir': _REPO_ROOT / args.acceptance_tests_dir,
        'matrix_output': _REPO_ROOT / args.matrix_output,
        'dashboard_output': _REPO_ROOT / args.dashboard_output,
        'survey_doc': _REPO_ROOT / args.survey_doc,
        'use_cases_doc': _REPO_ROOT / args.use_cases_doc,
        'acceptance_source': args.acceptance_source,
    }
    errors = (
        check_competitive_docs(**inputs)
        if args.check
        else refresh_competitive_docs(**inputs)
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        'Competitive docs check passed.'
        if args.check
        else 'Competitive docs refresh passed.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
