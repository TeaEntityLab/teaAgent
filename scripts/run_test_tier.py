#!/usr/bin/env python3
"""Run pytest suite tiers: smoke, acceptance, nightly."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TESTS = _REPO_ROOT / 'tests'
_ACCEPTANCE = _TESTS / 'acceptance'
_INTEGRATION = _TESTS / 'integration'

NIGHTLY_NODE_FRAGMENTS: tuple[str, ...] = (
    'tests/integration/',
    'test_audit_benchmark.py',
    'test_cli_fuzz_parsers.py',
    'test_mutation_smoke_registry.py',
    'test_governance_adversarial_runtime.py',
    'test_property_invariants.py',
    'integration/test_benchmark.py',
)

SMOKE_TARGETS: tuple[str, ...] = (
    str(_TESTS / 'test_p0_harness.py'),
    str(_TESTS / 'test_surface_auth_hardening.py'),
    str(_TESTS / 'test_policy.py'),
    str(_TESTS / 'test_phase5_context_bus.py'),
    str(_TESTS / 'test_governance_hardening.py'),
    str(_TESTS / 'test_validate_wiring.py'),
    str(_TESTS / 'test_h4_shadow_wiring.py'),
    str(_TESTS / 'test_release_eval_gate.py'),
    str(_TESTS / 'test_claim_commit_gate.py'),
    str(_TESTS / 'test_update_platform_proof.py'),
    str(_TESTS / 'test_remote_approval_backend.py'),
    str(_TESTS / 'test_signed_approval_queue.py'),
    str(_TESTS / 'test_conversation_ux.py'),
    str(_TESTS / 'test_ws2_verification_gaps.py'),
    str(_TESTS / 'test_root_module_count.py'),
    str(_TESTS / 'test_import_compat_wdf002.py'),
    str(_TESTS / 'test_terminology_lint.py'),
    str(_TESTS / 'test_suite_summary_freshness.py'),
    str(_TESTS / 'regression'),
)


def tier_command(tier: str) -> list[str]:
    base = [sys.executable, '-m', 'pytest', '-q']
    if tier == 'smoke':
        return [*base, *SMOKE_TARGETS]
    if tier == 'acceptance':
        return [*base, str(_ACCEPTANCE)]
    if tier == 'nightly':
        return [*base, str(_TESTS)]
    raise ValueError(f'Unknown tier: {tier}')


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=_REPO_ROOT,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 'unknown'


def _parse_pytest_summary(output: str) -> dict[str, int | float | None]:
    passed = failed = 0
    duration: float | None = None
    for line in output.splitlines():
        if m := re.search(r'(\d+)\s+passed', line):
            passed = int(m.group(1))
        if m := re.search(r'(\d+)\s+failed', line):
            failed = int(m.group(1))
        if m := re.search(r'in\s+([\d.]+)s', line):
            duration = float(m.group(1))
    return {
        'passed': passed,
        'failed': failed,
        'total': passed + failed,
        'duration_seconds': duration,
    }


def emit_suite_summary(
    *,
    tier: str,
    exit_code: int,
    output: str,
    started_at: float,
) -> dict[str, object]:
    stats = _parse_pytest_summary(output)
    return {
        'tier': tier,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'commit': _git_head(),
        'exit_code': exit_code,
        'duration_seconds': stats['duration_seconds']
        if stats['duration_seconds'] is not None
        else round(time.time() - started_at, 3),
        'passed': stats['passed'],
        'failed': stats['failed'],
        'total': stats['total'],
    }


def write_suite_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


def run_tier(tier: str, *, summary_path: Path | None = None) -> int:
    cmd = tier_command(tier)
    started = time.time()
    result = subprocess.run(
        cmd,
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or '') + (result.stderr or '')
    if output:
        print(output, end='')
    if summary_path is not None:
        write_suite_summary(
            summary_path,
            emit_suite_summary(
                tier=tier,
                exit_code=int(result.returncode),
                output=output,
                started_at=started,
            ),
        )
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--tier',
        choices=('smoke', 'acceptance', 'nightly'),
        required=True,
        help='smoke: fast PR gate; acceptance: user workflows; nightly: full suite',
    )
    parser.add_argument(
        '--emit-summary',
        default=None,
        help='Write machine-readable suite summary JSON (WDG-003)',
    )
    args = parser.parse_args(argv)
    summary = Path(args.emit_summary) if args.emit_summary else None
    return run_tier(args.tier, summary_path=summary)


if __name__ == '__main__':
    raise SystemExit(main())
