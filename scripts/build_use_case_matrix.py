from __future__ import annotations

import argparse
import re
from pathlib import Path

_SURVEY_REVIEW_DATE = re.compile(
    r'Last reviewed:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*', re.IGNORECASE
)
_OPEN_BACKLOG_MARKER = re.compile(r'^\|\s+[^|]+\s+\|\s+P[12]\s+\|\s+Open', re.MULTILINE)

USE_CASE_META: dict[str, dict[str, str]] = {
    'Project instruction conformance': {
        'blast_radius': 'high',
        'rollback_path': 'git revert AGENTS.md',
        'audit_criticality': 'medium',
    },
    'Safe autonomous coding run': {
        'blast_radius': 'high',
        'rollback_path': 'teaagent agent undo',
        'audit_criticality': 'high',
    },
    'Destructive-action governance': {
        'blast_radius': 'critical',
        'rollback_path': 'teaagent agent undo',
        'audit_criticality': 'critical',
    },
    'Tool ecosystem extensibility': {
        'blast_radius': 'medium',
        'rollback_path': 'remove skill/MCP config',
        'audit_criticality': 'medium',
    },
    'Reliability and forensics': {
        'blast_radius': 'high',
        'rollback_path': 'N/A (read-only verification)',
        'audit_criticality': 'critical',
    },
    'Memory continuity': {
        'blast_radius': 'low',
        'rollback_path': 'clear .teaagent/memory/',
        'audit_criticality': 'low',
    },
    'IDE-assisted workflows': {
        'blast_radius': 'low',
        'rollback_path': 'restart VSCode',
        'audit_criticality': 'low',
    },
    'Product onboarding and provider readiness': {
        'blast_radius': 'low',
        'rollback_path': 're-run teaagent init',
        'audit_criticality': 'low',
    },
    'Read-only planning mode': {
        'blast_radius': 'low',
        'rollback_path': 'N/A (no mutations)',
        'audit_criticality': 'low',
    },
    'End-to-end code-change loop': {
        'blast_radius': 'high',
        'rollback_path': 'git checkout -- .',
        'audit_criticality': 'high',
    },
    'Reversible change recovery': {
        'blast_radius': 'medium',
        'rollback_path': 'teaagent agent undo',
        'audit_criticality': 'medium',
    },
    'Runtime IDE MCP smoke': {
        'blast_radius': 'low',
        'rollback_path': 'restart MCP server',
        'audit_criticality': 'medium',
    },
    'Session resume continuity': {
        'blast_radius': 'medium',
        'rollback_path': 're-run original task',
        'audit_criticality': 'high',
    },
    'External ecosystem compatibility': {
        'blast_radius': 'low',
        'rollback_path': 'fix manifest/schema',
        'audit_criticality': 'low',
    },
}

USE_CASES: dict[str, tuple[str, ...]] = {
    name: tests
    for name, tests in [
        (
            'Project instruction conformance',
            ('test_agents_md_injection_flow.py', 'test_first_run_experience_flow.py'),
        ),
        (
            'Safe autonomous coding run',
            (
                'test_daily_cli.py',
                'test_daily_tui.py',
                'test_policy_as_code_flow.py',
                'test_workspace_edit_flow.py',
            ),
        ),
        (
            'Destructive-action governance',
            (
                'test_cancel_flow.py',
                'test_daily_cli.py',
                'test_policy_as_code_flow.py',
                'test_p0_slo_flow.py',
            ),
        ),
        (
            'Tool ecosystem extensibility',
            (
                'test_skill_install_flow.py',
                'test_remote_mcp_consumption_flow.py',
                'test_mcp_client_flow.py',
            ),
        ),
        (
            'Reliability and forensics',
            (
                'test_audit_chain_integrity_flow.py',
                'test_webhook_audit_flow.py',
                'test_cost_tracking_flow.py',
            ),
        ),
        ('Memory continuity', ('test_memory_auto_curation_flow.py',)),
        ('IDE-assisted workflows', ('test_vscode_extension_mcp_boot_flow.py',)),
        (
            'Product onboarding and provider readiness',
            (
                'test_first_run_experience_flow.py',
                'test_model_smoke_gating_flow.py',
                'test_live_provider_conformance_flow.py',
                'test_provider_matrix_consistency_flow.py',
            ),
        ),
        ('Read-only planning mode', ('test_plan_mode_read_only_flow.py',)),
        (
            'End-to-end code-change loop',
            ('test_workspace_edit_flow.py', 'test_agent_fix_test_review_flow.py'),
        ),
        ('Reversible change recovery', ('test_run_undo_acceptance_flow.py',)),
        (
            'Runtime IDE MCP smoke',
            (
                'test_vscode_extension_mcp_boot_flow.py',
                'test_vscode_mcp_runtime_smoke_flow.py',
            ),
        ),
        ('Session resume continuity', ('test_session_resume_continuity_flow.py',)),
        (
            'External ecosystem compatibility',
            ('test_external_tool_manifest_compatibility_flow.py',),
        ),
    ]
}


def parse_acceptance_test_files(markdown: str) -> set[str]:
    return set(re.findall(r'`(test_[^`]+\.py)`', markdown))


def _survey_review_date(survey_path: Path) -> str:
    if not survey_path.is_file():
        return 'unknown'
    match = _SURVEY_REVIEW_DATE.search(survey_path.read_text(encoding='utf-8'))
    return match.group(1) if match else 'unknown'


def _open_backlog_gap_count(use_cases_path: Path) -> int:
    if not use_cases_path.is_file():
        return 0
    return len(_OPEN_BACKLOG_MARKER.findall(use_cases_path.read_text(encoding='utf-8')))


def build_matrix_markdown(
    available_tests: set[str],
    *,
    survey_review_date: str = 'unknown',
    open_gap_count: int = 0,
) -> str:
    lines = [
        '# Use-case Coverage Matrix',
        '',
        'Generated from `docs/acceptance.md` by `scripts/build_use_case_matrix.py`.',
        '',
        f'Landscape survey reviewed: **{survey_review_date}** '
        f'([scripts/refresh_agent_readme_survey.md](../scripts/refresh_agent_readme_survey.md)).',
        f'Open roadmap differentiators (P1/P2): **{open_gap_count}** '
        '(see [docs/use-cases.md](use-cases.md#next-differentiators-roadmap)).',
        '',
        '| Use Case | Covered | Blast Radius | Rollback Path | Audit Criticality | Required Tests | Missing Tests |',
        '|---|---|---|---|---|---|---|',
    ]
    for use_case, required in USE_CASES.items():
        meta = USE_CASE_META.get(use_case, {})
        missing = [name for name in required if name not in available_tests]
        covered = 'yes' if not missing else 'no'
        blast = meta.get('blast_radius', '—')
        rollback = meta.get('rollback_path', '—')
        criticality = meta.get('audit_criticality', '—')
        required_text = ', '.join(f'`{name}`' for name in required)
        missing_text = ', '.join(f'`{name}`' for name in missing) if missing else '-'
        lines.append(
            f'| {use_case} | {covered} | {blast} | {rollback} | {criticality} | {required_text} | {missing_text} |'
        )
    lines.append('')
    return '\n'.join(lines)


def build_use_case_matrix(
    *,
    acceptance_path: Path,
    output_path: Path,
    survey_path: Path,
    use_cases_path: Path,
) -> None:
    available = parse_acceptance_test_files(acceptance_path.read_text(encoding='utf-8'))
    output_path.write_text(
        build_matrix_markdown(
            available,
            survey_review_date=_survey_review_date(survey_path),
            open_gap_count=_open_backlog_gap_count(use_cases_path),
        ),
        encoding='utf-8',
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate use-case coverage matrix from acceptance docs.'
    )
    parser.add_argument(
        '--acceptance-doc',
        default='docs/acceptance.md',
        help='Path to acceptance coverage markdown.',
    )
    parser.add_argument(
        '--output',
        default='docs/use-case-matrix.md',
        help='Path to generated use-case matrix markdown.',
    )
    parser.add_argument(
        '--survey-doc',
        default='scripts/refresh_agent_readme_survey.md',
        help='Landscape survey artifact for review date metadata.',
    )
    parser.add_argument(
        '--use-cases-doc',
        default='docs/use-cases.md',
        help='Use-cases doc for open differentiator gap counts.',
    )
    args = parser.parse_args()
    build_use_case_matrix(
        acceptance_path=Path(args.acceptance_doc),
        output_path=Path(args.output),
        survey_path=Path(args.survey_doc),
        use_cases_path=Path(args.use_cases_doc),
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
