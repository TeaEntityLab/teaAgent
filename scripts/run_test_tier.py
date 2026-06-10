#!/usr/bin/env python3
"""Run pytest suite tiers: smoke, acceptance, nightly."""

from __future__ import annotations

import argparse
import subprocess
import sys
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


def run_tier(tier: str) -> int:
    cmd = tier_command(tier)
    result = subprocess.run(cmd, cwd=_REPO_ROOT, check=False)
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--tier',
        choices=('smoke', 'acceptance', 'nightly'),
        required=True,
        help='smoke: fast PR gate; acceptance: user workflows; nightly: full suite',
    )
    args = parser.parse_args(argv)
    return run_tier(args.tier)


if __name__ == '__main__':
    raise SystemExit(main())
