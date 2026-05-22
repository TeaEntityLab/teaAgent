from __future__ import annotations

import argparse
import re
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from teaagent.llm._config import PROVIDER_CONFIGS  # noqa: E402
from teaagent.policy import PermissionMode  # noqa: E402

TIER_START = '<!-- ACCEPTANCE_TIERS:START -->'
TIER_END = '<!-- ACCEPTANCE_TIERS:END -->'
SURVEY_REVIEW_DATE = re.compile(
    r'Last reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*', re.IGNORECASE
)
SURVEY_SOURCE_URL = re.compile(r'https://[^\s|)]+')
SURVEY_BACKLOG_ACTION = re.compile(r'\bP[0-2](?:-[a-z0-9]+)?\b', re.IGNORECASE)
MODE_MATRIX_START = '<!-- MODE_SAFETY_MATRIX:START -->'
MODE_MATRIX_END = '<!-- MODE_SAFETY_MATRIX:END -->'
MODE_MATRIX_REQUIRED_TOPICS = (
    'Plan Mode',
    'Auto Mode',
    'Code Mode',
    'shell mutate',
    'Approvals',
    'Audit',
    'Rollback',
    'Subagent',
    'Preflight',
)
SURFACE_RECIPES_START = '<!-- SURFACE_RECIPES:START -->'
SURFACE_RECIPES_END = '<!-- SURFACE_RECIPES:END -->'
SURFACE_RECIPES_REQUIRED = (
    'CLI',
    'TUI',
    'VS Code',
    'MCP',
    'ACP',
    'A2A',
    'ANP',
    'Managed runtime',
)
SURFACE_SMOKE_COMMANDS = (
    'teaagent model providers',
    'teaagent agent card',
    'teaagent workspace tools',
    'teaagent agent preflight',
)
CATALOG_REVIEW_DATE = re.compile(
    r'Last reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*', re.IGNORECASE
)
CATALOG_REQUIRED_SECTIONS = (
    'Skill discovery paths',
    'Plugin discovery paths',
    'Hook events',
    'MCP tool metadata assumptions',
    'Subagent delegation and isolation',
    'Preflight context pack',
    'Fixture examples',
    'Known non-goals',
)
CATALOG_REQUIRED_FIXTURES = (
    'tests/fixtures/plugin_skill_catalog/sample_skill/SKILL.md',
    'tests/fixtures/plugin_skill_catalog/sample_plugin/plugin.json',
    'tests/fixtures/plugin_skill_catalog/external_mcp_tools.json',
)


def _render_tier_markdown() -> str:
    script = Path(__file__).with_name('run_acceptance_tier.py')
    spec = spec_from_file_location('run_acceptance_tier', script)
    if not spec or not spec.loader:
        raise RuntimeError('Unable to load run_acceptance_tier.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_tier_markdown()


def _extract_provider_count(readme_text: str) -> int:
    match = re.search(r'\((\d+)\s+providers\)', readme_text)
    if not match:
        raise ValueError("README provider count marker '(N providers)' not found.")
    return int(match.group(1))


def _extract_readme_credential_env_vars(readme_text: str) -> set[str]:
    return set(re.findall(r'export\s+([A-Z0-9_]+)=', readme_text))


def _expected_provider_credential_env_vars() -> set[str]:
    return {cfg.api_key_env for cfg in PROVIDER_CONFIGS.values()}


def _extract_architecture_provider_count(architecture_text: str) -> int | None:
    match = re.search(
        r'across\s+(\d+)\s+registered\s+providers', architecture_text, re.IGNORECASE
    )
    if not match:
        return None
    return int(match.group(1))


def _extract_usage_provider_count(usage_text: str) -> int | None:
    match = re.search(r'supports\s+(\d+)\s+LLM providers', usage_text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_acceptance_status_count(acceptance_text: str) -> int:
    match = re.search(r'`(\d+)\s+passed`', acceptance_text)
    if not match:
        raise ValueError("Acceptance status marker '`N passed`' not found.")
    return int(match.group(1))


def _collect_acceptance_test_files(acceptance_dir: Path) -> set[str]:
    return {path.name for path in acceptance_dir.glob('test_*.py')}


def _collect_acceptance_test_count(acceptance_dir: Path) -> int:
    result = subprocess.run(
        ['python3', '-m', 'pytest', str(acceptance_dir), '--collect-only', '-q'],
        capture_output=True,
        text=True,
        check=False,
    )
    output = f'{result.stdout}\n{result.stderr}'
    if result.returncode != 0:
        raise RuntimeError(f'Acceptance pytest collection failed.\n{output}')
    match = re.search(r'(\d+)\s+tests?\s+collected', output)
    if not match:
        raise ValueError('Could not parse collected test count from pytest output.')
    return int(match.group(1))


def _matrix_has_missing_use_cases(matrix_text: str) -> bool:
    return '| no |' in matrix_text


def _extract_marked_block(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end)
    if left == -1 or right == -1 or right < left:
        raise ValueError(f'Marker block not found: {start} ... {end}')
    body = text[left + len(start) : right]
    return body.strip()


def validate_provider_docs_consistency(
    *,
    readme_text: str,
    architecture_text: str,
    usage_text: str,
) -> list[str]:
    errors: list[str] = []
    runtime_count = len(PROVIDER_CONFIGS)
    expected_env_vars = _expected_provider_credential_env_vars()
    readme_env_vars = _extract_readme_credential_env_vars(readme_text)

    try:
        readme_provider_count = _extract_provider_count(readme_text)
    except ValueError as exc:
        errors.append(str(exc))
        readme_provider_count = 0
    if readme_provider_count and readme_provider_count != runtime_count:
        errors.append(
            'README provider count mismatch: '
            f'(readme={readme_provider_count}, runtime={runtime_count}).'
        )

    missing_env_vars = sorted(expected_env_vars - readme_env_vars)
    if missing_env_vars:
        errors.append(
            'README missing provider credential env vars: '
            + ', '.join(missing_env_vars)
        )

    architecture_count = _extract_architecture_provider_count(architecture_text)
    if architecture_count is None:
        errors.append(
            'architecture.md missing provider count marker '
            "'across N registered providers'."
        )
    elif architecture_count != runtime_count:
        errors.append(
            'architecture.md provider count mismatch: '
            f'(architecture={architecture_count}, runtime={runtime_count}).'
        )

    usage_count = _extract_usage_provider_count(usage_text)
    if usage_count is None:
        errors.append(
            "USAGE.md missing provider count marker 'supports N LLM providers'."
        )
    elif usage_count != runtime_count:
        errors.append(
            'USAGE.md provider count mismatch: '
            f'(usage={usage_count}, runtime={runtime_count}).'
        )

    return errors


def validate_surface_recipes(usage_text: str) -> list[str]:
    errors: list[str] = []
    try:
        block = _extract_marked_block(
            usage_text, SURFACE_RECIPES_START, SURFACE_RECIPES_END
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    for surface in SURFACE_RECIPES_REQUIRED:
        if surface not in block:
            errors.append(f'Surface recipes missing required surface: {surface!r}.')

    for command in SURFACE_SMOKE_COMMANDS:
        if command not in usage_text:
            errors.append(f'Surface recipes missing smoke-check command: {command!r}.')

    return errors


def validate_mode_safety_matrix(usage_text: str) -> list[str]:
    errors: list[str] = []
    try:
        matrix_block = _extract_marked_block(
            usage_text, MODE_MATRIX_START, MODE_MATRIX_END
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    lowered = matrix_block.lower()
    for topic in MODE_MATRIX_REQUIRED_TOPICS:
        if topic.lower() not in lowered:
            errors.append(f'Mode/safety matrix missing required topic: {topic!r}.')

    for mode in PermissionMode:
        if f'`{mode.value}`' not in matrix_block:
            errors.append(
                f'Mode/safety matrix missing PermissionMode value: {mode.value!r}.'
            )

    return errors


def validate_plugin_skill_catalog(
    catalog_text: str, *, repo_root: Path = _REPO_ROOT
) -> list[str]:
    errors: list[str] = []
    if not CATALOG_REVIEW_DATE.search(catalog_text):
        errors.append(
            'Plugin/skill catalog missing review date: Last reviewed: **YYYY-MM-DD**.'
        )
    for section in CATALOG_REQUIRED_SECTIONS:
        if section not in catalog_text:
            errors.append(f'Plugin/skill catalog missing section: {section!r}.')
    for rel_path in CATALOG_REQUIRED_FIXTURES:
        if not (repo_root / rel_path).is_file():
            errors.append(f'Plugin/skill catalog fixture missing: {rel_path}')
    return errors


def validate_survey_doc(survey_text: str) -> list[str]:
    errors: list[str] = []
    if not SURVEY_REVIEW_DATE.search(survey_text):
        errors.append(
            'Survey missing review date marker: Last reviewed: **YYYY-MM-DD**.'
        )
    source_urls = SURVEY_SOURCE_URL.findall(survey_text)
    if len(source_urls) < 5:
        errors.append(
            f'Survey needs at least five source URLs (found {len(source_urls)}).'
        )
    if not SURVEY_BACKLOG_ACTION.search(survey_text):
        errors.append(
            'Survey needs at least one mapped backlog action (P0/P1/P2 item).'
        )
    return errors


def validate_docs_consistency(
    *,
    readme_path: Path,
    acceptance_doc_path: Path,
    use_case_matrix_path: Path,
    acceptance_tests_dir: Path,
    architecture_path: Path | None = None,
    usage_path: Path | None = None,
    survey_path: Path | None = None,
    catalog_path: Path | None = None,
    check_providers: bool = True,
    check_survey: bool = True,
    check_catalog: bool = True,
    check_mode_matrix: bool = True,
    check_surface_recipes: bool = True,
) -> list[str]:
    errors: list[str] = []

    readme_text = readme_path.read_text(encoding='utf-8')
    acceptance_text = acceptance_doc_path.read_text(encoding='utf-8')
    matrix_text = use_case_matrix_path.read_text(encoding='utf-8')
    acceptance_tests = _collect_acceptance_test_files(acceptance_tests_dir)

    architecture_path = architecture_path or (_REPO_ROOT / 'docs' / 'architecture.md')
    usage_doc_path = usage_path or (_REPO_ROOT / 'docs' / 'USAGE.md')
    survey_path = survey_path or (
        _REPO_ROOT / 'scripts' / 'refresh_agent_readme_survey.md'
    )
    catalog_doc_path = catalog_path or (_REPO_ROOT / 'docs' / 'plugin-skill-catalog.md')

    if check_providers:
        if architecture_path.is_file() and usage_doc_path.is_file():
            errors.extend(
                validate_provider_docs_consistency(
                    readme_text=readme_text,
                    architecture_text=architecture_path.read_text(encoding='utf-8'),
                    usage_text=usage_doc_path.read_text(encoding='utf-8'),
                )
            )
        else:
            if not architecture_path.is_file():
                errors.append(f'architecture doc not found: {architecture_path}')
            if not usage_doc_path.is_file():
                errors.append(f'USAGE doc not found: {usage_doc_path}')

    if check_mode_matrix or check_surface_recipes:
        if usage_doc_path.is_file():
            usage_text = usage_doc_path.read_text(encoding='utf-8')
            if check_mode_matrix:
                errors.extend(validate_mode_safety_matrix(usage_text))
            if check_surface_recipes:
                errors.extend(validate_surface_recipes(usage_text))
        else:
            errors.append(f'USAGE doc not found: {usage_doc_path}')

    if check_survey:
        if survey_path.is_file():
            errors.extend(validate_survey_doc(survey_path.read_text(encoding='utf-8')))
        else:
            errors.append(f'Survey doc not found: {survey_path}')

    if check_catalog:
        if catalog_doc_path.is_file():
            errors.extend(
                validate_plugin_skill_catalog(
                    catalog_doc_path.read_text(encoding='utf-8')
                )
            )
        else:
            errors.append(f'Plugin/skill catalog not found: {catalog_doc_path}')

    try:
        status_count = _extract_acceptance_status_count(acceptance_text)
    except ValueError as exc:
        errors.append(str(exc))
        status_count = 0
    collected_count = _collect_acceptance_test_count(acceptance_tests_dir)
    if status_count and status_count != collected_count:
        errors.append(
            'Acceptance status mismatch: '
            f'docs/acceptance.md says {status_count} passed, '
            f'but pytest collect reports {collected_count} acceptance tests.'
        )

    if not acceptance_tests:
        errors.append('No acceptance test files found under tests/acceptance.')

    if _matrix_has_missing_use_cases(matrix_text):
        errors.append("Use-case matrix contains uncovered rows ('Covered = no').")

    try:
        current_tier_block = _extract_marked_block(
            acceptance_text, TIER_START, TIER_END
        )
    except ValueError as exc:
        errors.append(str(exc))
    else:
        expected_tier_block = _render_tier_markdown().strip()
        if current_tier_block != expected_tier_block:
            errors.append(
                'Acceptance tier section is out of sync with scripts/run_acceptance_tier.py. '
                'Run: python3 scripts/sync_acceptance_tiers_doc.py'
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate README / acceptance / use-case docs consistency.'
    )
    parser.add_argument('--readme', default='README.md')
    parser.add_argument('--acceptance-doc', default='docs/acceptance.md')
    parser.add_argument('--use-case-matrix', default='docs/use-case-matrix.md')
    parser.add_argument('--acceptance-tests-dir', default='tests/acceptance')
    parser.add_argument('--architecture-doc', default='docs/architecture.md')
    parser.add_argument('--usage-doc', default='docs/USAGE.md')
    parser.add_argument(
        '--survey-doc', default='scripts/refresh_agent_readme_survey.md'
    )
    parser.add_argument('--catalog-doc', default='docs/plugin-skill-catalog.md')
    args = parser.parse_args()

    errors = validate_docs_consistency(
        readme_path=Path(args.readme),
        acceptance_doc_path=Path(args.acceptance_doc),
        use_case_matrix_path=Path(args.use_case_matrix),
        acceptance_tests_dir=Path(args.acceptance_tests_dir),
        architecture_path=Path(args.architecture_doc),
        usage_path=Path(args.usage_doc),
        survey_path=Path(args.survey_doc),
        catalog_path=Path(args.catalog_doc),
    )
    if errors:
        for err in errors:
            print(f'ERROR: {err}')
        return 1
    print('Docs consistency check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
