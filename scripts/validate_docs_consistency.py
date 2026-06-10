from __future__ import annotations

import argparse
import re
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from teaagent.llm._config import PROVIDER_CONFIGS  # noqa: E402
from teaagent.run_evidence import check_evidence_completeness  # noqa: E402
from teaagent.types import PermissionMode  # noqa: E402

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
ROADMAP_TABLE_SEPARATOR = re.compile(r'^\|[-:\s|]+\|$')
ROADMAP_EXIT_COLUMNS = ('Exit Evidence', 'Exit Criteria', 'Risk')
ROADMAP_REQUIRED_ROW_FIELDS = ('Owner', 'Status', 'Confidence', 'Next Gate')
ROADMAP_VALID_STATUS_VALUES = (
    'proposed',
    'complete',
    'in progress',
    'pending',
    'blocked',
    'on hold',
    'fixed',
    'active',
    'verify/close',
    'partially fixed',
)
ROADMAP_EMPTY_FIELD_VALUES = frozenset({'', '-', '—', 'n/a', 'na'})
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


def validate_test_quality(tests_dir: Path, mode: str = 'report') -> list[str]:
    """Validate test quality by running the audit tool and checking for severe issues.

    Args:
        tests_dir: Directory containing tests
        mode: 'report' (print findings without failing), 'strict' (fail on weak tests), 'off' (skip audit)

    Returns:
        List of error strings (empty in 'report' or 'off' mode unless audit fails)
    """
    errors = []

    if mode == 'off':
        return errors

    # Import audit tool functions
    sys.path.insert(0, str(_REPO_ROOT / 'scripts'))
    try:
        from audit_test_quality import (
            _repo_relative,
            collect_pytest_nodes,
            discover_test_files,
            scan_test_file,
        )
    except ImportError:
        errors.append('audit_test_quality.py not found or not importable')
        return errors

    # Collection is required in all modes except 'off' to catch import/collection errors
    if mode != 'off':
        try:
            collect_pytest_nodes(tests_dir)
        except RuntimeError as e:
            errors.append(f'Test quality audit failed: {e}')
            return errors

    test_files = discover_test_files(tests_dir)

    try:
        all_metrics = []
        for test_file in test_files:
            metrics = scan_test_file(test_file)
            all_metrics.append(metrics)

        # Check for severe issues
        total_tests = sum(len(m.test_functions) for m in all_metrics)
        no_assert_tests = sum(
            sum(1 for count in m.assertion_counts.values() if count == 0)
            for m in all_metrics
        )

        findings = []

        # Warn if more than 10% of tests have no assertions
        if total_tests > 0 and no_assert_tests / total_tests > 0.1:
            finding = f'Test quality: {no_assert_tests}/{total_tests} tests ({no_assert_tests / total_tests * 100:.1f}%) have no assertions. Threshold is 10%.'
            findings.append(finding)
            if mode == 'strict':
                errors.append(finding)

        # Check for new placeholder tests (tests with no assertions in security/audit paths)
        for metrics in all_metrics:
            if metrics.has_syntax_error:
                continue

            path_str = _repo_relative(metrics.path)
            if 'security' in path_str or 'audit' in path_str:
                no_assert_count = sum(
                    1 for count in metrics.assertion_counts.values() if count == 0
                )
                if no_assert_count > 0:
                    finding = f'Test quality: {path_str} has {no_assert_count} tests with no assertions in security/audit path.'
                    findings.append(finding)
                    if mode == 'strict':
                        errors.append(finding)

        # Print findings in report mode
        if mode == 'report' and findings:
            print('Test quality audit findings (report mode, not failing validation):')
            for finding in findings:
                print(f'  {finding}')

    except Exception as e:
        error_msg = f'Test quality audit failed: {e}'
        if mode == 'report':
            print(f'  {error_msg}')
        else:
            errors.append(error_msg)

    return errors


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
GUARDED_FULL_SUITE_DOCS = (
    'README.md',
    'docs/acceptance.md',
    'docs/daily-driver-current-status.md',
    'docs/roadmap-status.md',
)
GUARDED_SUITE_SUMMARY_KEYWORDS = ('passed', 'pytest', 'suite')
GUARDED_CLAIM_EXEMPT_KEYWORDS = ('historical', 'superseded', 'example')
GUARDED_STALE_FAILURE_PROSE = re.compile(
    r'\b([1-9]\d*)\s+(failed|failures)\b', re.IGNORECASE
)

# Risk register evidence patterns
_RISK_ROW_ID = re.compile(r'^\|\s*([A-Z]{2,4}-\d+)\s*\|', re.MULTILINE)
_TICKET_ROW = re.compile(
    r'^\|\s*\[?(TASK-DD2-\d+|TICKET-\d+[^]]*)\]?',
    re.MULTILINE,
)
_TEST_NAME_IN_TEXT = re.compile(r'\btest_[a-z][a-z0-9_]{3,}\b')
_COMMIT_HASH_IN_TEXT = re.compile(r'\b[0-9a-f]{7,40}\b')
# Only match project ticket/work-item IDs, not risk register IDs (SEC-*, DS-*, SC-*)
_TICKET_ID_IN_TEXT = re.compile(r'\b(?:TASK|TICKET|GOV|P[0-9]-TR)-[A-Z0-9-]+\b')
_PRIORITY_P0_P1 = re.compile(r'\bP[01]\b')
_STATUS_FIXED = re.compile(
    r'\bFIXED\b|\bFixed\b|\bVERIFY/CLOSE\b|\bDOCUMENTED\b', re.IGNORECASE
)
_STATUS_OPEN = re.compile(r'\bOPEN\b', re.IGNORECASE)


def _parse_risk_register_rows(text: str) -> dict[str, tuple[str, str, str]]:
    """Parse risk-register table rows into {id: (status_text, priority, full_row)}.

    Handles free-text Status cells (e.g. '**FIXED 2026-06-05** — test: test_foo')
    by splitting lines on '|' and dynamically mapping Status and Priority indices
    based on the number of columns (supports 8-column and 10-column formats).
    """
    rows: dict[str, tuple[str, str, str]] = {}
    for line in text.splitlines():
        if not _RISK_ROW_ID.match(line):
            continue
        parts = [p.strip() for p in line.split('|')]
        # parts[0] is empty (before first |), parts[-1] is empty (after last |)
        if len(parts) < 9:
            continue
        row_id = parts[1].strip()
        if not re.match(r'^[A-Z]{2,4}-\d+$', row_id):
            continue

        # Determine Status and Priority indices based on column count
        if len(parts) >= 11:
            # 10-column format: | ID | Category | Description | L | I | Score | Owner | Due | Status | Priority |
            status_text = parts[9].strip()
            priority = parts[10].strip() if len(parts) > 10 else ''
        else:
            # 8-column format: | ID | Category | Description | L | I | Score | Status | Priority |
            status_text = parts[7].strip()
            priority = parts[8].strip() if len(parts) > 8 else ''

        rows[row_id] = (status_text, priority, line)
    return rows


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


def _split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _is_markdown_table_separator(line: str) -> bool:
    return bool(ROADMAP_TABLE_SEPARATOR.match(line.strip()))


def _roadmap_status_is_valid(status_value: str) -> bool:
    normalized = re.sub(r'[*_`]', '', status_value).strip().lower()
    if not normalized:
        return False
    return any(
        normalized == valid or valid in normalized
        for valid in ROADMAP_VALID_STATUS_VALUES
    )


def validate_roadmap_required_fields(roadmap_text: str) -> list[str]:
    """Ensure roadmap tables keep owner/status/confidence/next gate/exit fields."""
    errors: list[str] = []
    lines = roadmap_text.splitlines()
    line_no = 0
    while line_no < len(lines):
        line = lines[line_no]
        if not line.strip().startswith('|'):
            line_no += 1
            continue

        headers = _split_markdown_table_row(line)
        if not all(field in headers for field in ROADMAP_REQUIRED_ROW_FIELDS):
            line_no += 1
            continue

        # Critical Path uses a different schema (no Confidence column guard here).
        if 'Completion %' in headers:
            line_no += 1
            continue

        exit_column = next(
            (column for column in ROADMAP_EXIT_COLUMNS if column in headers),
            None,
        )
        if exit_column is None:
            errors.append(
                f'Roadmap table at line {line_no + 1} missing one of '
                f'{ROADMAP_EXIT_COLUMNS}.'
            )
            line_no += 1
            continue

        field_indexes = {
            field: headers.index(field) for field in ROADMAP_REQUIRED_ROW_FIELDS
        }
        exit_index = headers.index(exit_column)
        line_no += 1
        if line_no < len(lines) and _is_markdown_table_separator(lines[line_no]):
            line_no += 1

        while line_no < len(lines) and lines[line_no].strip().startswith('|'):
            row_line = lines[line_no]
            if _is_markdown_table_separator(row_line):
                line_no += 1
                continue

            row_cells = _split_markdown_table_row(row_line)
            if len(row_cells) < len(headers):
                errors.append(
                    f'Roadmap row at line {line_no + 1} has too few columns '
                    f'({len(row_cells)} < {len(headers)}).'
                )
                line_no += 1
                continue

            for field, index in field_indexes.items():
                value = row_cells[index].strip().lower()
                if value in ROADMAP_EMPTY_FIELD_VALUES:
                    errors.append(
                        f'Roadmap row at line {line_no + 1} missing required '
                        f'field {field!r}.'
                    )

            exit_value = row_cells[exit_index].strip().lower()
            if exit_value in ROADMAP_EMPTY_FIELD_VALUES:
                errors.append(
                    f'Roadmap row at line {line_no + 1} missing required '
                    f'field {exit_column!r}.'
                )

            status_value = row_cells[field_indexes['Status']]
            if not _roadmap_status_is_valid(status_value):
                errors.append(
                    f'Roadmap row at line {line_no + 1} has unrecognized Status '
                    f'value {status_value!r}.'
                )

            line_no += 1

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
    errors.extend(validate_roadmap_required_fields(roadmap_text))
    errors.extend(validate_roadmap_horizon_milestone_consistency(roadmap_text))
    return errors


def _normalize_roadmap_status(value: str) -> str:
    return re.sub(r'[*_`]', '', value).strip().lower()


def _roadmap_status_maps(roadmap_text: str) -> tuple[dict[str, str], dict[str, str]]:
    horizon_status: dict[str, str] = {}
    milestone_status: dict[str, str] = {}
    section: str | None = None
    status_index: int | None = None

    for line in roadmap_text.splitlines():
        if line.strip() == '## Roadmap Horizons':
            section = 'horizon'
            status_index = None
            continue
        if line.strip() == '## Milestones':
            section = 'milestone'
            status_index = None
            continue
        if not line.strip().startswith('|'):
            continue
        if _is_markdown_table_separator(line):
            continue

        cells = _split_markdown_table_row(line)
        if 'Status' in cells and 'Owner' in cells:
            status_index = cells.index('Status')
            continue
        if status_index is None or len(cells) <= status_index:
            continue

        key = cells[0].strip()
        if section == 'horizon' and key.upper().startswith('H') and key[1:].isdigit():
            horizon_status[key[1:]] = _normalize_roadmap_status(cells[status_index])
        if section == 'milestone' and key.upper().startswith('M') and key[1:].isdigit():
            milestone_status[key[1:]] = _normalize_roadmap_status(cells[status_index])

    return horizon_status, milestone_status


def validate_roadmap_horizon_milestone_consistency(roadmap_text: str) -> list[str]:
    """Flag horizon Hn Pending while milestone Mn is Complete."""
    errors: list[str] = []
    horizon_status, milestone_status = _roadmap_status_maps(roadmap_text)

    for index in sorted(set(horizon_status) & set(milestone_status), key=int):
        horizon = horizon_status[index]
        milestone = milestone_status[index]
        if 'complete' not in milestone:
            continue
        if horizon == 'pending':
            errors.append(
                f'Roadmap contradiction: H{index} is Pending while M{index} is Complete.'
            )
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


def _load_generate_docs_inventory_module() -> ModuleType:
    script = Path(__file__).with_name('generate_docs_inventory.py')
    spec = spec_from_file_location('generate_docs_inventory', script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {script}')
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_report_docs_aging_module() -> ModuleType:
    script = Path(__file__).with_name('report_docs_aging.py')
    spec = spec_from_file_location('report_docs_aging', script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {script}')
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_generate_command_snippet_inventory_module() -> ModuleType:
    script = Path(__file__).with_name('generate_command_snippet_inventory.py')
    spec = spec_from_file_location('generate_command_snippet_inventory', script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {script}')
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WORK_LOG_CANONICAL_STATES = frozenset(
    {
        'proposed',
        'active',
        'partially fixed',
        'verify/close',
        'fixed',
        'superseded',
        'archived',
    }
)
WORK_LOG_LEGACY_STATE_LABELS = frozenset(
    {
        'done',
        'complete',
        'closed',
        'open',
        'partial',
        'pending',
        'in progress',
    }
)
_CJK_CHAR = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]')


def validate_work_log_canonical_states(
    work_log_text: str,
    *,
    path_label: str,
) -> list[str]:
    """Ensure active work-item ledgers use canonical State labels."""
    errors: list[str] = []
    lines = work_log_text.splitlines()
    state_index: int | None = None
    for line_no, line in enumerate(lines, start=1):
        if not line.strip().startswith('|'):
            continue
        headers = _split_markdown_table_row(line)
        if 'State' in headers:
            state_index = headers.index('State')
            continue
        if state_index is None or _is_markdown_table_separator(line):
            continue
        cells = _split_markdown_table_row(line)
        if len(cells) <= state_index:
            continue
        state = cells[state_index].strip()
        if not state or state.lower() == 'state':
            continue
        normalized = state.lower()
        if normalized in WORK_LOG_CANONICAL_STATES:
            continue
        if normalized in WORK_LOG_LEGACY_STATE_LABELS:
            errors.append(
                f'{path_label} line {line_no}: legacy State label {state!r} — '
                'map to canonical vocabulary in document-state-model.md.'
            )
            continue
        errors.append(
            f'{path_label} line {line_no}: unrecognized State label {state!r}.'
        )
    return errors


def validate_index_status_vocabulary(index_text: str) -> list[str]:
    errors: list[str] = []
    if 'document-state-model.md' not in index_text:
        errors.append(
            'docs/INDEX.md must link document-state-model.md for status vocabulary.'
        )
    if (
        'Status vocabulary' not in index_text
        and 'status vocabulary' not in index_text.lower()
    ):
        errors.append(
            'docs/INDEX.md must include a Status vocabulary section mapping legacy labels.'
        )
    return errors


def validate_durable_docs_language(
    paths: list[Path],
    *,
    repo_root: Path = _REPO_ROOT,
) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        for line_no, line in enumerate(
            path.read_text(encoding='utf-8').splitlines(),
            start=1,
        ):
            if _CJK_CHAR.search(line):
                rel = path.relative_to(repo_root).as_posix()
                errors.append(
                    f'{rel} line {line_no}: durable governance doc contains '
                    'non-English characters; translate or mark as localization-only.'
                )
                break
    return errors


def validate_documentation_audit_cadence(
    *,
    cadence_path: Path,
    release_checklist_path: Path,
    verify_docs_path: Path,
) -> list[str]:
    errors: list[str] = []
    if not cadence_path.is_file():
        errors.append(f'Missing documentation audit cadence doc: {cadence_path}')
    if release_checklist_path.is_file():
        text = release_checklist_path.read_text(encoding='utf-8')
        if 'documentation-audit-cadence' not in text:
            errors.append(
                'docs/release-checklist.md must link documentation-audit-cadence doc.'
            )
    else:
        errors.append(f'Missing release checklist: {release_checklist_path}')
    if verify_docs_path.is_file():
        text = verify_docs_path.read_text(encoding='utf-8')
        if 'generate_command_snippet_inventory.py' not in text:
            errors.append(
                'scripts/verify_docs.sh must run generate_command_snippet_inventory.py --check.'
            )
    else:
        errors.append(f'Missing verify_docs.sh: {verify_docs_path}')
    return errors


def _load_control_loop_freshness_module() -> ModuleType:
    script = Path(__file__).with_name('validate_control_loop_freshness.py')
    spec = spec_from_file_location('validate_control_loop_freshness', script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load {script}')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_validate_wiring_module() -> ModuleType:
    script = Path(__file__).with_name('validate_wiring.py')
    spec = spec_from_file_location('validate_wiring', script)
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


def validate_guarded_claims(
    *, registry_text: str, repo_root: Path = _REPO_ROOT
) -> list[str]:
    """Fail when a guarded current-truth doc keeps stale full-suite failure prose.

    Generalizes the documentation guards (DOW-012): a current-truth front door
    must not assert a non-zero full-suite failure count. Historical numbers belong
    in dated evidence docs, which are exempt by keyword.
    """
    errors: list[str] = []

    for doc in GUARDED_FULL_SUITE_DOCS:
        if doc not in registry_text:
            errors.append(
                f'Guarded-claims registry missing guarded document entry: {doc!r}.'
            )

    for doc in GUARDED_FULL_SUITE_DOCS:
        path = repo_root / doc
        if not path.is_file():
            continue
        for lineno, line in enumerate(
            path.read_text(encoding='utf-8').splitlines(), start=1
        ):
            lowered = line.lower()
            if not any(key in lowered for key in GUARDED_SUITE_SUMMARY_KEYWORDS):
                continue
            if any(key in lowered for key in GUARDED_CLAIM_EXEMPT_KEYWORDS):
                continue
            match = GUARDED_STALE_FAILURE_PROSE.search(line)
            if match:
                errors.append(
                    f'Guarded claim drift in {doc}:{lineno}: stale full-suite '
                    f'failure prose {match.group(0)!r}. Current-truth docs must '
                    'report 0 failed or move the dated claim to evidence docs '
                    '(see docs/governance/guarded-claims-registry.md).'
                )
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
    guarded_claims_registry_path: Path | None = None,
    check_providers: bool = True,
    check_survey: bool = True,
    check_catalog: bool = True,
    check_mode_matrix: bool = True,
    check_surface_recipes: bool = True,
    check_repo_governance: bool = True,
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
    guarded_claims_registry_doc_path = guarded_claims_registry_path or (
        _REPO_ROOT / 'docs' / 'governance' / 'guarded-claims-registry.md'
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

    if guarded_claims_registry_doc_path.is_file():
        errors.extend(
            validate_guarded_claims(
                registry_text=guarded_claims_registry_doc_path.read_text(
                    encoding='utf-8'
                ),
                repo_root=_REPO_ROOT,
            )
        )
    else:
        errors.append(
            f'Guarded-claims registry not found: {guarded_claims_registry_doc_path}'
        )

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
        try:
            control_loop_module = _load_control_loop_freshness_module()
            errors.extend(control_loop_module.validate_roadmap(roadmap_status_doc_path))
        except RuntimeError:
            errors.append(
                'Cannot load validate_control_loop_freshness; '
                'control-loop freshness check skipped.'
            )
    else:
        errors.append(f'Roadmap status doc not found: {roadmap_status_doc_path}')

    if pyproject_doc_path.is_file() and coverage_omit_ledger_doc_path.is_file():
        errors.extend(
            validate_coverage_omit_ledger(
                pyproject_text=pyproject_doc_path.read_text(encoding='utf-8'),
                ledger_text=coverage_omit_ledger_doc_path.read_text(encoding='utf-8'),
            )
        )
    else:
        if not pyproject_doc_path.is_file():
            errors.append(f'pyproject.toml not found: {pyproject_doc_path}')
        if not coverage_omit_ledger_doc_path.is_file():
            errors.append(
                f'Coverage omit ledger not found: {coverage_omit_ledger_doc_path}'
            )

    if (
        dependency_audit_policy_doc_path.is_file()
        and security_workflow_doc_path.is_file()
    ):
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

    errors.extend(validate_doc_cross_references(repo_root=_REPO_ROOT))

    if check_repo_governance:
        try:
            inventory_module = _load_generate_docs_inventory_module()
            errors.extend(inventory_module.check_docs_inventory())
        except RuntimeError:
            errors.append(
                'Cannot load generate_docs_inventory; docs inventory check skipped.'
            )

        try:
            aging_module = _load_report_docs_aging_module()
            errors.extend(aging_module.check_docs_aging_dashboard())
        except RuntimeError:
            errors.append(
                'Cannot load report_docs_aging; docs aging dashboard check skipped.'
            )

        try:
            snippet_module = _load_generate_command_snippet_inventory_module()
            errors.extend(snippet_module.check_command_snippet_inventory())
        except RuntimeError:
            errors.append(
                'Cannot load generate_command_snippet_inventory; '
                'command snippet inventory check skipped.'
            )

        work_log_path = (
            _REPO_ROOT
            / 'docs'
            / 'work-log'
            / ('documentation-optimization-work-items-2026-06-04.md')
        )
        if work_log_path.is_file():
            errors.extend(
                validate_work_log_canonical_states(
                    work_log_path.read_text(encoding='utf-8'),
                    path_label=str(work_log_path.relative_to(_REPO_ROOT)),
                )
            )

        index_path = _REPO_ROOT / 'docs' / 'INDEX.md'
        if index_path.is_file():
            errors.extend(
                validate_index_status_vocabulary(index_path.read_text(encoding='utf-8'))
            )

        errors.extend(
            validate_durable_docs_language(
                [
                    _REPO_ROOT / 'docs' / 'INDEX.md',
                    _REPO_ROOT
                    / 'docs'
                    / 'governance'
                    / 'documentation-operating-model-2026-06-04.md',
                    _REPO_ROOT
                    / 'docs'
                    / 'governance'
                    / 'documentation-audit-cadence-2026-06-06.md',
                    _REPO_ROOT / 'docs' / 'governance' / 'command-snippet-registry.md',
                ]
            )
        )

        errors.extend(
            validate_documentation_audit_cadence(
                cadence_path=_REPO_ROOT
                / 'docs'
                / 'governance'
                / 'documentation-audit-cadence-2026-06-06.md',
                release_checklist_path=_REPO_ROOT / 'docs' / 'release-checklist.md',
                verify_docs_path=_REPO_ROOT / 'scripts' / 'verify_docs.sh',
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


def _collect_markdown_link_targets(
    *,
    doc_path: Path,
    repo_root: Path,
) -> list[tuple[str, str, Path]]:
    """Return (label, raw_target, resolved_path) for each internal markdown link."""
    text = doc_path.read_text(encoding='utf-8')
    doc_dir = doc_path.parent
    targets: list[tuple[str, str, Path]] = []

    for match in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', text):
        label = match.group(1)
        target = match.group(2)

        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        if target.startswith('#'):
            continue

        path_part = target.split('#', 1)[0]
        if not path_part:
            continue

        if not path_part.endswith('.md'):
            continue

        resolved = (doc_dir / path_part).resolve()
        try:
            resolved.relative_to(repo_root)
        except ValueError:
            continue

        targets.append((label, target, resolved))

    return targets


def _scan_doc_links(
    *,
    doc_path: Path,
    repo_root: Path,
) -> list[str]:
    rel = doc_path.relative_to(repo_root)
    broken: list[str] = []
    for label, target, resolved in _collect_markdown_link_targets(
        doc_path=doc_path,
        repo_root=repo_root,
    ):
        if resolved.is_file():
            continue
        broken.append(
            f'Broken cross-reference in {rel}: '
            f'[{label}]({target}) → '
            f'{resolved.relative_to(repo_root)} (not found)'
        )
    return broken


CURRENT_TRUTH_DOC_PATHS = (
    'README.md',
    'docs/INDEX.md',
    'docs/USAGE.md',
    'docs/cli.md',
    'docs/acceptance.md',
    'docs/roadmap-status.md',
    'docs/daily-driver-current-status.md',
    'docs/release-checklist.md',
    'docs/backlog-priority.md',
    'docs/maturity-matrix.md',
    'docs/terminology.md',
    'docs/architecture.md',
    'docs/tui-daily-driver-guide.md',
    'docs/permission-and-approval-playbook.md',
    'docs/governance/README.md',
    'docs/plans/ticket-plans/index.md',
    'docs/analysis/active-findings-status-ledger-2026-06-06.md',
)

HISTORICAL_DOC_DIRS = (
    'docs/analysis',
    'docs/reviews',
    'docs/work-log',
    'docs/plans',
)


def validate_doc_cross_references(
    repo_root: Path = _REPO_ROOT,
    *,
    emit_historical_warnings: bool = True,
) -> list[str]:
    """Check internal markdown links.

    Current-truth docs: broken `.md` links fail validation.
    Historical evidence dirs: broken links are warnings only (printed).
    """
    errors: list[str] = []
    warnings: list[str] = []

    current_truth_paths = {repo_root / rel for rel in CURRENT_TRUTH_DOC_PATHS}

    for doc_path in sorted(current_truth_paths):
        if not doc_path.is_file():
            continue
        errors.extend(_scan_doc_links(doc_path=doc_path, repo_root=repo_root))

    for rel_dir in HISTORICAL_DOC_DIRS:
        directory = repo_root / rel_dir
        if not directory.is_dir():
            continue
        for doc_path in sorted(directory.rglob('*.md')):
            if doc_path in current_truth_paths:
                continue
            warnings.extend(_scan_doc_links(doc_path=doc_path, repo_root=repo_root))

    if emit_historical_warnings and warnings:
        print(
            f'Historical doc link warnings ({len(warnings)}; non-blocking):',
            file=sys.stderr,
        )
        preview = warnings[:25]
        for warning in preview:
            print(f'  WARNING: {warning}', file=sys.stderr)
        if len(warnings) > len(preview):
            print(
                f'  WARNING: ... and {len(warnings) - len(preview)} more',
                file=sys.stderr,
            )

    return errors


def validate_risk_register_evidence(
    risk_register_text: str,
    *,
    repo_root: Path = _REPO_ROOT,
) -> list[str]:
    """Validate that risk register rows have evidence for FIXED/P0/P1 claims.

    Rules:
    - Any row with status containing "FIXED" must cite a test name or commit hash
      somewhere in the document's "Fix Status" section or the row itself.
    - Any OPEN row with P0 or P1 priority must cite a test name, commit hash,
      or a linked ticket ID in the same document.
    - Rows where the table status disagrees with a "FIXED" note in the Fix Status
      section are flagged as inconsistencies.

    Exit-1 condition: any P0/P1 row fails its evidence requirement.
    """
    errors: list[str] = []
    p0p1_errors: list[str] = []

    # Extract the Fix Status block if present (provides evidence for fixed items).
    fix_status_block = ''
    fix_start = risk_register_text.find('### Fix Status')
    if fix_start != -1:
        fix_status_block = risk_register_text[fix_start:]

    # Collect IDs claimed fixed in the Fix Status section.
    # Only collect from subsections headed by **Fixed** (or **Fixed (date)**),
    # stopping at **Still Open** subsections so those items are not included.
    _FIXED_HEADER = re.compile(r'^\*\*Fixed', re.IGNORECASE)
    _STILL_OPEN_HEADER = re.compile(r'^\*\*Still Open', re.IGNORECASE)
    fixed_in_fix_status: set[str] = set()
    in_fixed_subsection = False
    for line in fix_status_block.splitlines():
        if _FIXED_HEADER.match(line.strip()):
            in_fixed_subsection = True
            continue
        if _STILL_OPEN_HEADER.match(line.strip()):
            in_fixed_subsection = False
            continue
        if not in_fixed_subsection:
            continue
        m = re.match(r'[-*]\s*\*\*([A-Z]{2,4}-\d+)\*\*:', line)
        if m:
            fixed_in_fix_status.add(m.group(1))

    # Pre-index all lines for context lookup.
    all_lines = risk_register_text.splitlines()
    row_line_index: dict[str, int] = {}
    for lineno, line in enumerate(all_lines):
        m = re.match(r'^\|\s*([A-Z]{2,4}-\d+)\s*\|', line)
        if m:
            row_line_index.setdefault(m.group(1), lineno)

    # id -> (status_text, priority, full_row_line)
    parsed_rows = _parse_risk_register_rows(risk_register_text)

    # Coverage counters
    total = len(parsed_rows)
    verified = 0
    uncovered_p0p1: list[str] = []

    for row_id, (status_text, priority, _row_line) in parsed_rows.items():
        is_fixed = bool(_STATUS_FIXED.search(status_text))
        is_open = bool(_STATUS_OPEN.search(status_text))
        is_p0p1 = bool(_PRIORITY_P0_P1.search(priority))

        # Evidence search scoping:
        # - For FIXED rows: search only in the Fix Status block (where test names live).
        # - For OPEN rows: search only the row's own status cell text (not neighboring
        #   table rows, which would give false positives via adjacent risk IDs).
        if is_fixed:
            search_corpus = fix_status_block
        else:
            # Use only the status_text cell for OPEN rows
            search_corpus = status_text

        has_test = bool(_TEST_NAME_IN_TEXT.search(search_corpus))
        has_commit = bool(_COMMIT_HASH_IN_TEXT.search(search_corpus))
        # Cross-reference must be a *different* item ID, not the row's own.
        cross_ref_corpus = search_corpus.replace(row_id, '')
        has_cross_ref = bool(_TICKET_ID_IN_TEXT.search(cross_ref_corpus))
        has_strong_evidence = has_test or has_commit
        has_evidence = has_strong_evidence or has_cross_ref

        if has_strong_evidence or has_cross_ref:
            verified += 1

        # Table says OPEN but Fix Status says it's fixed → inconsistency
        if is_open and row_id in fixed_in_fix_status:
            errors.append(
                f'Risk register inconsistency: {row_id} table row says OPEN but '
                f'Fix Status section marks it FIXED. Update the table row status.'
            )

        if is_fixed and not has_strong_evidence:
            errors.append(
                f'Risk register FIXED claim without test/commit evidence: {row_id} '
                f'(status={status_text[:60]!r}). Add a test function name or commit hash.'
            )

        if is_open and is_p0p1 and not has_evidence:
            msg = (
                f'Risk register P0/P1 OPEN row has no linked evidence: {row_id} '
                f'(priority={priority!r}). Add a ticket ID, test name, or code reference.'
            )
            p0p1_errors.append(msg)
            uncovered_p0p1.append(row_id)

    errors.extend(p0p1_errors)

    # Print coverage summary
    pct = int(100 * verified / total) if total else 0
    print(f'Risk register evidence coverage: {verified}/{total} rows verified ({pct}%)')
    if uncovered_p0p1:
        print(f'  High-risk uncovered P0/P1 rows: {", ".join(uncovered_p0p1)}')

    return errors


def validate_ticket_index_evidence(
    ticket_index_text: str,
    *,
    repo_root: Path = _REPO_ROOT,
) -> list[str]:
    """Validate that ticket index rows claiming Fixed have a code or test reference.

    Rules:
    - Every row with "Fixed" in the Summary column must contain a file path
      or be traceable to a known test name.
    - "Partially addressed" rows are flagged with a warning if the plan file
      is not cited or no ACs are listed.
    """
    errors: list[str] = []

    total = 0
    verified = 0

    for line in ticket_index_text.splitlines():
        m = re.match(r'^\|\s*\[?(TASK-DD2-\d+|TICKET-\d+[^\]]*)\]?[^|]*\|', line)
        if not m:
            continue
        total += 1
        ticket_id = m.group(1).strip()

        # Check for "Fixed" claim
        if 'Fixed' not in line and 'fixed' not in line:
            verified += 1  # non-Fixed rows are not subject to this rule
            continue

        # Check for "partially" qualifier
        if 'partially' in line.lower():
            # Must cite a plan file or have explicit AC list
            if 'plan.md' not in line and 'plan file' not in line:
                errors.append(
                    f'Ticket {ticket_id} claims partially Fixed but cites no plan file '
                    f'for the incomplete ACs. Add a link to the plan or list the open ACs.'
                )
            verified += 1
            continue

        # Full "Fixed" claim: require a file path or test name in the row
        has_file = bool(re.search(r'`[a-z][a-z0-9_/]+\.[a-z]+`', line))
        has_test = bool(_TEST_NAME_IN_TEXT.search(line))
        if has_file or has_test:
            verified += 1
        else:
            # Softer: only warn, not error, since file refs may be in separate plan files
            errors.append(
                f'Ticket {ticket_id} claims Fixed but the index row cites no file path '
                f'or test name. Add a code ref or cross-link to the plan file.'
            )

    pct = int(100 * verified / total) if total else 0
    print(f'Ticket index evidence coverage: {verified}/{total} rows verified ({pct}%)')

    return errors


def validate_audit_evidence_completeness(
    run_store_root: Path,
    *,
    repo_root: Path = _REPO_ROOT,
) -> list[str]:
    """Check audit evidence completeness across stored runs.

    Reads all runs from the run store, builds evidence bundles, and
    verifies each bundle against the completeness checklist for its
    final status.  Missing critical audit events are surfaced.

    Exit-1 condition: any run with status "success" or "failure" has
    missing required evidence fields or events.
    """
    errors: list[str] = []

    from teaagent.run_evidence import build_run_evidence_bundle
    from teaagent.run_store import RunStore

    try:
        store = RunStore(run_store_root)
        runs = store.list_runs()
    except Exception as exc:
        errors.append(f'Unable to list runs from {run_store_root}: {exc}')
        return errors

    if not runs:
        return errors

    critical_statuses = {'success', 'failure'}
    total_runs = 0
    verified = 0

    for run_id in runs:
        total_runs += 1
        try:
            events = store.show_run(run_id)
        except Exception:
            continue

        bundle = build_run_evidence_bundle(run_store_root, run_id)
        status = _derive_run_status(events)

        if status in critical_statuses:
            missing = check_evidence_completeness(bundle, events, status)
            if missing:
                errors.append(
                    f'Run {run_id} ({status}) incomplete evidence: '
                    + ', '.join(missing)
                )
            else:
                verified += 1

    pct = int(100 * verified / total_runs) if total_runs > 0 else 0
    print(
        f'Audit evidence completeness: {verified}/{total_runs} '
        f'critical runs verified ({pct}%)'
    )
    return errors


def _derive_run_status(events: list[dict[str, Any]]) -> str:
    """Derive terminal run status from audit events."""
    for event in reversed(events):
        event_type = str(event.get('event_type', ''))
        if event_type == 'run_completed':
            return 'success'
        if event_type == 'run_failed':
            return 'failure'
        if event_type == 'run_cancelled':
            return 'cancelled'
        if event_type == 'run_paused':
            return 'pending_approval'
    return 'unknown'


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
    parser.add_argument(
        '--guarded-claims-registry',
        default='docs/governance/guarded-claims-registry.md',
    )
    parser.add_argument(
        '--risk-register',
        default='docs/security/risk-register-and-threat-model-2026-06-02.md',
        help='Risk register markdown file to audit for evidence completeness.',
    )
    parser.add_argument(
        '--ticket-index',
        default='docs/plans/ticket-plans/index.md',
        help='Ticket index markdown file to audit for Fixed claim evidence.',
    )
    parser.add_argument(
        '--skip-risk-register',
        action='store_true',
        help='Skip risk register evidence audit.',
    )
    parser.add_argument(
        '--skip-ticket-index',
        action='store_true',
        help='Skip ticket index evidence audit.',
    )
    parser.add_argument(
        '--audit-evidence-root',
        default=None,
        help='Root directory for audit evidence completeness check '
        '(disabled when omitted).',
    )
    parser.add_argument(
        '--test-quality-mode',
        choices=['report', 'strict', 'off'],
        default='report',
        help=(
            'Test quality audit mode. '
            'report: print findings without failing (default, compatible with rollout). '
            'strict: fail validation on weak tests (future CI enforcement). '
            'off: disable audit (local/debug only, not a normal CI path). '
            'Rationale: Baseline weak tests are known historical debt; report mode keeps docs consistency compatible during rollout.'
        ),
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
        guarded_claims_registry_path=Path(args.guarded_claims_registry),
    )
    risk_register_path = Path(args.risk_register)
    if not args.skip_risk_register:
        if risk_register_path.is_file():
            errors.extend(
                validate_risk_register_evidence(
                    risk_register_path.read_text(encoding='utf-8'),
                )
            )
        else:
            errors.append(f'Risk register not found: {risk_register_path}')

    ticket_index_path = Path(args.ticket_index)
    if not args.skip_ticket_index:
        if ticket_index_path.is_file():
            errors.extend(
                validate_ticket_index_evidence(
                    ticket_index_path.read_text(encoding='utf-8'),
                )
            )
        else:
            errors.append(f'Ticket index not found: {ticket_index_path}')

    # Test quality audit integration
    test_quality_errors = validate_test_quality(
        tests_dir=Path(args.acceptance_tests_dir).parent,
        mode=args.test_quality_mode,
    )
    errors.extend(test_quality_errors)

    wiring_module = _load_validate_wiring_module()
    errors.extend(wiring_module.validate_wiring())

    if args.audit_evidence_root:
        errors.extend(
            validate_audit_evidence_completeness(
                run_store_root=Path(args.audit_evidence_root),
            )
        )

    if errors:
        for err in errors:
            print(f'ERROR: {err}')
        return 1
    print('Docs consistency check passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
