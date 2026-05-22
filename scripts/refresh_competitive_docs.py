from __future__ import annotations

import argparse
import subprocess
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Run competitive-docs refresh steps from docs/release-checklist.md.'
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
    args = parser.parse_args()

    errors = refresh_competitive_docs(
        acceptance_doc=_REPO_ROOT / args.acceptance_doc,
        acceptance_tests_dir=_REPO_ROOT / args.acceptance_tests_dir,
        matrix_output=_REPO_ROOT / args.matrix_output,
        dashboard_output=_REPO_ROOT / args.dashboard_output,
        survey_doc=_REPO_ROOT / args.survey_doc,
        use_cases_doc=_REPO_ROOT / args.use_cases_doc,
        acceptance_source=args.acceptance_source,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print('Competitive docs refresh passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
