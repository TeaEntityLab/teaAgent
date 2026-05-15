from __future__ import annotations

import argparse
import re
from pathlib import Path

USE_CASES: dict[str, tuple[str, ...]] = {
    'Project instruction conformance': (
        'test_agents_md_injection_flow.py',
        'test_first_run_experience_flow.py',
    ),
    'Safe autonomous coding run': (
        'test_daily_cli.py',
        'test_daily_tui.py',
        'test_policy_as_code_flow.py',
        'test_workspace_edit_flow.py',
    ),
    'Destructive-action governance': (
        'test_cancel_flow.py',
        'test_daily_cli.py',
        'test_policy_as_code_flow.py',
    ),
    'Tool ecosystem extensibility': (
        'test_skill_install_flow.py',
        'test_remote_mcp_consumption_flow.py',
        'test_mcp_client_flow.py',
    ),
    'Reliability and forensics': (
        'test_audit_chain_integrity_flow.py',
        'test_webhook_audit_flow.py',
        'test_cost_tracking_flow.py',
    ),
    'Memory continuity': ('test_memory_auto_curation_flow.py',),
    'IDE-assisted workflows': ('test_vscode_extension_mcp_boot_flow.py',),
    'Product onboarding and provider readiness': (
        'test_first_run_experience_flow.py',
        'test_model_smoke_gating_flow.py',
        'test_live_provider_conformance_flow.py',
        'test_provider_matrix_consistency_flow.py',
    ),
    'Read-only planning mode': ('test_plan_mode_read_only_flow.py',),
    'End-to-end code-change loop': (
        'test_workspace_edit_flow.py',
        'test_agent_fix_test_review_flow.py',
    ),
    'Reversible change recovery': ('test_run_undo_acceptance_flow.py',),
    'Runtime IDE MCP smoke': (
        'test_vscode_extension_mcp_boot_flow.py',
        'test_vscode_mcp_runtime_smoke_flow.py',
    ),
    'Session resume continuity': ('test_session_resume_continuity_flow.py',),
    'External ecosystem compatibility': (
        'test_external_tool_manifest_compatibility_flow.py',
    ),
}


def parse_acceptance_test_files(markdown: str) -> set[str]:
    return set(re.findall(r'`(test_[^`]+\.py)`', markdown))


def build_matrix_markdown(available_tests: set[str]) -> str:
    lines = [
        '# Use-case Coverage Matrix',
        '',
        'Generated from `docs/acceptance.md` by `scripts/build_use_case_matrix.py`.',
        '',
        '| Use Case | Covered | Required Tests | Missing Tests |',
        '|---|---|---|---|',
    ]
    for use_case, required in USE_CASES.items():
        missing = [name for name in required if name not in available_tests]
        covered = 'yes' if not missing else 'no'
        required_text = ', '.join(f'`{name}`' for name in required)
        missing_text = ', '.join(f'`{name}`' for name in missing) if missing else '-'
        lines.append(f'| {use_case} | {covered} | {required_text} | {missing_text} |')
    lines.append('')
    return '\n'.join(lines)


def build_use_case_matrix(
    *,
    acceptance_path: Path,
    output_path: Path,
) -> None:
    available = parse_acceptance_test_files(acceptance_path.read_text(encoding='utf-8'))
    output_path.write_text(build_matrix_markdown(available), encoding='utf-8')


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
    args = parser.parse_args()
    build_use_case_matrix(
        acceptance_path=Path(args.acceptance_doc), output_path=Path(args.output)
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
