from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

TIERS: dict[str, tuple[str, ...]] = {
    'p0': (
        'test_first_run_experience_flow.py',
        'test_daily_cli.py',
        'test_p0_slo_flow.py',
        'test_plan_mode_read_only_flow.py',
        'test_workspace_edit_flow.py',
        'test_agent_fix_test_review_flow.py',
        'test_policy_as_code_flow.py',
    ),
    'p1': (
        'test_run_undo_acceptance_flow.py',
        'test_session_resume_continuity_flow.py',
        'test_vscode_mcp_runtime_smoke_flow.py',
        'test_mcp_client_flow.py',
    ),
}

TIER_PURPOSE: dict[str, str] = {
    'p0': 'Safe first-run, policy boundaries, and core coding loop',
    'p1': 'Recovery, continuity, and IDE/runtime surface reliability',
    'p2': 'Ecosystem compatibility and extended operations',
}

TIER_DOC_TESTS: dict[str, tuple[str, ...]] = {
    'p0': TIERS['p0'],
    'p1': TIERS['p1'],
    'p2': (
        'test_backend_adapter_flow.py',
        'test_external_tool_manifest_compatibility_flow.py',
        'test_remote_mcp_consumption_flow.py',
        'test_ultrawork_flow.py',
        'test_webhook_audit_flow.py',
    ),
}


def tier_paths(tier: str, *, acceptance_dir: Path) -> list[str]:
    if tier == 'all':
        return [str(acceptance_dir)]
    try:
        names = TIERS[tier]
    except KeyError as exc:
        raise ValueError(f'Unknown tier: {tier}') from exc
    return [str(acceptance_dir / name) for name in names]


def run_tier(tier: str, *, acceptance_dir: Path) -> int:
    targets = tier_paths(tier, acceptance_dir=acceptance_dir)
    cmd = ['python3', '-m', 'pytest', '-q', *targets]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def render_tier_markdown() -> str:
    lines = [
        '## Acceptance Tiers (P0/P1/P2)',
        '',
        'Use these tiers to control regression scope and release risk:',
        '',
        '| Tier | Purpose | Representative acceptance flows |',
        '|---|---|---|',
    ]
    for tier in ('p0', 'p1', 'p2'):
        tests = ', '.join(f'`{name}`' for name in TIER_DOC_TESTS[tier])
        lines.append(f'| {tier.upper()} | {TIER_PURPOSE[tier]} | {tests} |')
    lines.extend(
        [
            '',
            'Recommended execution cadence:',
            '',
            '1. Every PR: run all P0.',
            '2. Before merge to `main`: run P0 + P1.',
            '3. Before release: run full acceptance (P0 + P1 + P2).',
            '',
        ]
    )
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Run acceptance tests by tier.')
    parser.add_argument('--tier', choices=('p0', 'p1', 'all'))
    parser.add_argument(
        '--print-tier-markdown',
        action='store_true',
        help='Print canonical acceptance-tier markdown block.',
    )
    parser.add_argument('--acceptance-dir', default='tests/acceptance')
    args = parser.parse_args()
    if args.print_tier_markdown:
        print(render_tier_markdown(), end='')
        return 0
    if not args.tier:
        raise SystemExit('--tier is required unless --print-tier-markdown is set')
    return run_tier(args.tier, acceptance_dir=Path(args.acceptance_dir))


if __name__ == '__main__':
    raise SystemExit(main())
