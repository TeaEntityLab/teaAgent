from __future__ import annotations

import argparse
import re
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

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
COMPARISON_MATRIX_PROVIDER = re.compile(
    r'Multi-provider LLM\s*\|\s*✅\s*(\d+)\s*providers', re.IGNORECASE
)
ARCHITECTURE_LLM_ADAPTER_COUNT = re.compile(
    r'(\d+)\s+LLM\s+(?:adapters|providers)\b', re.IGNORECASE
)
USE_CASES_SURVEY_REVIEWED = re.compile(
    r'Landscape survey \(reviewed (\d{4}-\d{2}-\d{2})\)', re.IGNORECASE
)
USE_CASES_DIFFERENTIATOR_SURVEY = re.compile(
    r'from the (\d{4}-\d{2}-\d{2}) landscape survey', re.IGNORECASE
)
ARCHITECTURE_SURVEY_REFRESHED = re.compile(
    r'last refreshed (\d{4}-\d{2}-\d{2})', re.IGNORECASE
)
MATRIX_OPEN_GAP_COUNT = re.compile(
    r'Open partial/planned gaps \(P1/P2\):\s*\*\*(\d+)\*\*', re.IGNORECASE
)
MATRIX_SURVEY_DATE = re.compile(
    r'Landscape survey reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*', re.IGNORECASE
)
ARCHITECTURE_STALE_AT_COUNT = re.compile(r'10[0-4]\+\s*AT|104\+\s*AT', re.IGNORECASE)
ROADMAP_H0_ROW = re.compile(
    r'\|\s*H0\s*\|\s*Claim and risk hygiene\s*\|', re.IGNORECASE
)
ROADMAP_DOCUMENTATION_TRUTH = re.compile(r'documentation-current-truth', re.IGNORECASE)
ROADMAP_DOC_VS_HEAD = re.compile(r'doc-vs-head', re.IGNORECASE)
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
COVERAGE_OMIT_HEADER_COLUMNS = (
    'Omit Pattern',
    'Owner',
    'Reason',
    'Risk',
    'Expected Return Milestone',
    'Smoke-Test Candidate',
)
COVERAGE_OMIT_ROW = re.compile(r'^\|\s*`([^`]+)`\s*\|', re.MULTILINE)
COVERAGE_OMIT_BLOCK = re.compile(
    r'\[tool\.coverage\.run\].*?omit\s*=\s*\[(.*?)\]',
    re.DOTALL,
)
DEPENDENCY_AUDIT_POLICY_SECTIONS = (
    'Base Install Audit',
    'Lockfile and Dev Environment Audit',
    'Optional-Extra Runtime Audit',
)
DEPENDENCY_AUDIT_HIGH_RISK_EXTRAS = (
    'managed-google-adk',
    'managed-vertex',
    'playwright',
    'telemetry',
    'oauth',
    'wasm',
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
    # Use sys.executable -m pytest
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', str(acceptance_dir), '--collect-only', '-q'],
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

    comparison_match = COMPARISON_MATRIX_PROVIDER.search(architecture_text)
    if comparison_match:
        matrix_count = int(comparison_match.group(1))
        if matrix_count != runtime_count:
            errors.append(
                'architecture.md comparison matrix provider count mismatch: '
                f'(matrix={matrix_count}, runtime={runtime_count}).'
            )

    for match in ARCHITECTURE_LLM_ADAPTER_COUNT.finditer(architecture_text):
        mentioned = int(match.group(1))
        if mentioned != runtime_count:
            errors.append(
                'architecture.md provider count mismatch: '
                f"found '{match.group(0)}' but runtime has {runtime_count} providers."
            )

    return errors


def validate_date_coherence(
    *,
    survey_text: str,
    matrix_text: str,
    catalog_text: str,
    use_cases_text: str = '',
    architecture_text: str = '',
) -> list[str]:
    """Validate that all review dates reference the same value."""
    errors: list[str] = []
    dates: dict[str, str] = {}

    survey_match = SURVEY_REVIEW_DATE.search(survey_text)
    if survey_match:
        dates['survey'] = survey_match.group(1)
    else:
        errors.append('Survey doc missing review date.')

    matrix_match = MATRIX_SURVEY_DATE.search(matrix_text)
    if matrix_match:
        dates['use-case-matrix'] = matrix_match.group(1)
    else:
        errors.append('Use-case matrix missing review date.')

    catalog_match = CATALOG_REVIEW_DATE.search(catalog_text)
    if catalog_match:
        dates['plugin-skill-catalog'] = catalog_match.group(1)
    else:
        errors.append('Plugin-skill catalog missing review date.')

    if use_cases_text:
        reviewed = USE_CASES_SURVEY_REVIEWED.search(use_cases_text)
        if reviewed:
            dates['use-cases-header'] = reviewed.group(1)
        else:
            errors.append(
                'use-cases.md missing landscape survey date '
                '(Landscape survey (reviewed YYYY-MM-DD)).'
            )
        differentiator = USE_CASES_DIFFERENTIATOR_SURVEY.search(use_cases_text)
        if differentiator:
            dates['use-cases-differentiators'] = differentiator.group(1)
        else:
            errors.append(
                'use-cases.md missing differentiator survey date '
                '(from the YYYY-MM-DD landscape survey).'
            )

    if architecture_text:
        refreshed = ARCHITECTURE_SURVEY_REFRESHED.search(architecture_text)
        if refreshed:
            dates['architecture-comparison'] = refreshed.group(1)
        else:
            errors.append(
                'architecture.md comparison section missing survey refresh date '
                '(last refreshed YYYY-MM-DD).'
            )

    if len(set(dates.values())) > 1:
        errors.append(
            f'Date drift detected: {dates}. '
            f'All review dates should reference the last survey refresh date.'
        )

    return errors


def validate_matrix_open_gap_count(
    *,
    matrix_text: str,
    use_cases_path: Path,
) -> list[str]:
    errors: list[str] = []
    if not use_cases_path.is_file():
        return errors
    build_matrix = _load_build_use_case_matrix_module()
    expected = build_matrix._open_backlog_gap_count(use_cases_path)
    match = MATRIX_OPEN_GAP_COUNT.search(matrix_text)
    if not match:
        errors.append(
            'use-case-matrix.md missing open gap count marker '
            "'Open partial/planned gaps (P1/P2): **N**'."
        )
        return errors
    actual = int(match.group(1))
    if actual != expected:
        errors.append(
            'use-case-matrix.md open gap count mismatch: '
            f'(matrix={actual}, use-cases={expected}). '
            'Run: python3 scripts/refresh_competitive_docs.py'
        )
    return errors


def validate_roadmap_status(roadmap_text: str) -> list[str]:
    errors: list[str] = []
    if not ROADMAP_H0_ROW.search(roadmap_text):
        errors.append('Roadmap status missing H0 claim and risk hygiene row.')
    if not ROADMAP_DOCUMENTATION_TRUTH.search(roadmap_text):
        errors.append(
            'Roadmap status missing documentation-current-truth work reference.'
        )
    if not ROADMAP_DOC_VS_HEAD.search(roadmap_text):
        errors.append('Roadmap status missing doc-vs-HEAD guard reference.')
    return errors


def _extract_coverage_omit_patterns(pyproject_text: str) -> set[str]:
    match = COVERAGE_OMIT_BLOCK.search(pyproject_text)
    if not match:
        raise ValueError('pyproject.toml missing [tool.coverage.run] omit block.')
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def validate_coverage_omit_ledger(
    *, pyproject_text: str, ledger_text: str
) -> list[str]:
    errors: list[str] = []
    try:
        expected = _extract_coverage_omit_patterns(pyproject_text)
    except ValueError as exc:
        errors.append(str(exc))
        expected = set()

    for column in COVERAGE_OMIT_HEADER_COLUMNS:
        if column not in ledger_text:
            errors.append(f'Coverage omit ledger missing column: {column!r}.')

    actual = set(COVERAGE_OMIT_ROW.findall(ledger_text))
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append(
            'Coverage omit ledger missing pyproject omit patterns: '
            + ', '.join(missing)
        )
    if extra:
        errors.append(
            'Coverage omit ledger contains patterns not in pyproject.toml: '
            + ', '.join(extra)
        )
    if 'TBD' in ledger_text or 'TODO' in ledger_text:
        errors.append('Coverage omit ledger contains TBD/TODO placeholders.')
    return errors


def validate_dependency_audit_policy(
    *, policy_text: str, security_workflow_text: str
) -> list[str]:
    errors: list[str] = []
    for section in DEPENDENCY_AUDIT_POLICY_SECTIONS:
        if section not in policy_text:
            errors.append(f'Dependency audit policy missing section: {section!r}.')
    for extra in DEPENDENCY_AUDIT_HIGH_RISK_EXTRAS:
        if extra not in policy_text:
            errors.append(
                f'Dependency audit policy missing high-risk extra: {extra!r}.'
            )

    if '--no-dev --no-emit-project' not in security_workflow_text:
        errors.append(
            'Security workflow base lockfile audit must use '
            '`uv export --no-dev --no-emit-project`.'
        )
    if 'optional-extra-pip-audit' not in security_workflow_text:
        errors.append('Security workflow missing optional-extra pip-audit job.')
    if '--extra ${{ matrix.extra }}' not in security_workflow_text:
        errors.append('Security workflow optional-extra job missing matrix export.')
    if 'continue-on-error: true' not in security_workflow_text:
        errors.append(
            'Security workflow optional-extra audit must be non-blocking outside release.'
        )
    if 'pip-audit --skip-editable' in security_workflow_text:
        errors.append(
            'Security workflow must not run unscoped `pip-audit --skip-editable`; '
            'audit exported requirement surfaces instead.'
        )
    return errors


def _load_build_use_case_matrix_module() -> ModuleType:
    script = Path(__file__).with_name('build_use_case_matrix.py')
    spec = spec_from_file_location('build_use_case_matrix', script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {script}')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    if len(source_urls) < 8:
        errors.append(
            f'Survey needs at least eight source URLs (found {len(source_urls)}).'
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
    use_cases_path: Path | None = None,
    roadmap_status_path: Path | None = None,
    pyproject_path: Path | None = None,
    coverage_omit_ledger_path: Path | None = None,
    dependency_audit_policy_path: Path | None = None,
    security_workflow_path: Path | None = None,
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
    use_cases_doc_path = use_cases_path or (_REPO_ROOT / 'docs' / 'use-cases.md')
    roadmap_status_doc_path = roadmap_status_path or (
        _REPO_ROOT / 'docs' / 'roadmap-status.md'
    )
    pyproject_doc_path = pyproject_path or (_REPO_ROOT / 'pyproject.toml')
    coverage_omit_ledger_doc_path = coverage_omit_ledger_path or (
        _REPO_ROOT / 'docs' / 'governance' / 'coverage-omit-ledger.md'
    )
    dependency_audit_policy_doc_path = dependency_audit_policy_path or (
        _REPO_ROOT / 'docs' / 'security' / 'dependency-audit-policy.md'
    )
    security_workflow_doc_path = security_workflow_path or (
        _REPO_ROOT / '.github' / 'workflows' / 'security.yml'
    )
    architecture_text = (
        architecture_path.read_text(encoding='utf-8')
        if architecture_path.is_file()
        else ''
    )
    use_cases_text = (
        use_cases_doc_path.read_text(encoding='utf-8')
        if use_cases_doc_path.is_file()
        else ''
    )
    roadmap_status_text = (
        roadmap_status_doc_path.read_text(encoding='utf-8')
        if roadmap_status_doc_path.is_file()
        else ''
    )

    if check_providers:
        if architecture_path.is_file() and usage_doc_path.is_file():
            errors.extend(
                validate_provider_docs_consistency(
                    readme_text=readme_text,
                    architecture_text=architecture_text,
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
            catalog_text = catalog_doc_path.read_text(encoding='utf-8')
            errors.extend(validate_plugin_skill_catalog(catalog_text))
        else:
            errors.append(f'Plugin/skill catalog not found: {catalog_doc_path}')

    if roadmap_status_doc_path.is_file():
        errors.extend(validate_roadmap_status(roadmap_status_text))
    else:
        errors.append(f'Roadmap status doc not found: {roadmap_status_doc_path}')

    if pyproject_doc_path.is_file() and coverage_omit_ledger_doc_path.is_file():
        errors.extend(
            validate_coverage_omit_ledger(
                pyproject_text=pyproject_doc_path.read_text(encoding='utf-8'),
                ledger_text=coverage_omit_ledger_doc_path.read_text(
                    encoding='utf-8'
                ),
            )
        )
    else:
        if not pyproject_doc_path.is_file():
            errors.append(f'pyproject.toml not found: {pyproject_doc_path}')
        if not coverage_omit_ledger_doc_path.is_file():
            errors.append(
                f'Coverage omit ledger not found: {coverage_omit_ledger_doc_path}'
            )

    if dependency_audit_policy_doc_path.is_file() and security_workflow_doc_path.is_file():
        errors.extend(
            validate_dependency_audit_policy(
                policy_text=dependency_audit_policy_doc_path.read_text(
                    encoding='utf-8'
                ),
                security_workflow_text=security_workflow_doc_path.read_text(
                    encoding='utf-8'
                ),
            )
        )
    else:
        if not dependency_audit_policy_doc_path.is_file():
            errors.append(
                f'Dependency audit policy not found: {dependency_audit_policy_doc_path}'
            )
        if not security_workflow_doc_path.is_file():
            errors.append(f'Security workflow not found: {security_workflow_doc_path}')

    if check_survey:
        errors.extend(
            validate_date_coherence(
                survey_text=survey_path.read_text(encoding='utf-8')
                if survey_path.is_file()
                else '',
                matrix_text=matrix_text,
                catalog_text=catalog_doc_path.read_text(encoding='utf-8')
                if catalog_doc_path.is_file()
                else '',
                use_cases_text=use_cases_text,
                architecture_text=architecture_text,
            )
        )

    if check_survey and use_cases_doc_path.is_file():
        errors.extend(
            validate_matrix_open_gap_count(
                matrix_text=matrix_text,
                use_cases_path=use_cases_doc_path,
            )
        )

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

    if ARCHITECTURE_STALE_AT_COUNT.search(architecture_text):
        errors.append(
            'docs/architecture.md contains a stale hard-coded acceptance count '
            '(for example 104+ AT). Reference docs/acceptance.md or pytest-collected counts.'
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
    parser.add_argument('--roadmap-status', default='docs/roadmap-status.md')
    parser.add_argument('--pyproject', default='pyproject.toml')
    parser.add_argument(
        '--coverage-omit-ledger',
        default='docs/governance/coverage-omit-ledger.md',
    )
    parser.add_argument(
        '--dependency-audit-policy',
        default='docs/security/dependency-audit-policy.md',
    )
    parser.add_argument(
        '--security-workflow',
        default='.github/workflows/security.yml',
    )
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
        roadmap_status_path=Path(args.roadmap_status),
        pyproject_path=Path(args.pyproject),
        coverage_omit_ledger_path=Path(args.coverage_omit_ledger),
        dependency_audit_policy_path=Path(args.dependency_audit_policy),
        security_workflow_path=Path(args.security_workflow),
    )
    if errors:
        for err in errors:
            print(f'ERROR: {err}')
        return 1
    print('Docs consistency check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
