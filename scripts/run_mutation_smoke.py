#!/usr/bin/env python3
"""A3 governance gate: deterministic mutation smoke test for L3 trust modules.

Roadmap A3 (governance/plans/ADOPTION-ROADMAP.md): verify the *tests themselves* catch
regressions on the permission/approval/resume boundary. Instead of a full mutmut sweep
(slow, equivalent-mutant noise), this injects a curated set of dangerous logic mutations
and asserts the targeted P0 tests KILL each one. A surviving mutant = a test gap.

For each mutation: apply it, run its guard tests, and require them to FAIL (mutant killed),
then restore the file unconditionally. A mutant that leaves the guard tests GREEN is a
governance failure (exit 1).

Safety:
  - Refuses to run if any target file has uncommitted changes (avoids clobbering concurrent
    edits and guarantees a clean restore baseline).
  - Restores original file bytes in a finally block even on KeyboardInterrupt / test crash.

Usage:
  python3 scripts/run_mutation_smoke.py
  python3 scripts/run_mutation_smoke.py --list
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutation:
    file: str  # repo-relative
    old: str  # exact unique substring to replace
    new: str  # replacement (the injected fault)
    tests: list[str] = field(default_factory=list)  # guard tests expected to fail
    desc: str = ''


# Curated dangerous mutations on the L3 trust boundary. Each MUST be killed by its tests.
MUTATIONS: list[Mutation] = [
    Mutation(
        file='teaagent/integration/resume_preparation.py',
        old='if call_id in approve_call_ids:',
        new='if call_id not in approve_call_ids:',
        tests=[
            'tests/test_resume_preparation.py::test_pre_approved_call_id_is_skipped_not_re_granted'
        ],
        desc='invert pre-approval skip -> would auto-grant an explicitly pre-approved call',
    ),
    Mutation(
        file='teaagent/integration/resume_preparation.py',
        old='if not digest:',
        new='if digest:',
        tests=[
            'tests/test_resume_preparation.py::test_legacy_record_without_digest_warns_and_does_not_auto_grant'
        ],
        desc='invert legacy-record guard -> would auto-grant a digestless legacy record',
    ),
    Mutation(
        file='teaagent/integration/resume_preparation.py',
        old='if auto_approve_pending and not existing_warning:',
        new='if auto_approve_pending or existing_warning:',
        tests=[
            'tests/test_resume_preparation.py::test_auto_approve_pending_false_warns_without_granting'
        ],
        desc='invert auto_approve_pending knob -> TUI would auto-grant instead of warn',
    ),
    Mutation(
        file='teaagent/integration/resume_preparation.py',
        old='auto_approve_pending and not existing_warning',
        new='auto_approve_pending',
        tests=[
            'tests/test_resume_preparation.py::test_unmatched_effect_warning_blocks_auto_grant'
        ],
        desc='drop OUTCOME_UNKNOWN warning guard -> resume would auto-grant a scoped approval while a non-idempotent effect is unconfirmed (blind-redispatch hazard)',
    ),
    Mutation(
        file='teaagent/ergonomics/_approval_state.py',
        old='and record.argument_digest == argument_digest',
        new='and record.argument_digest != argument_digest',
        tests=[
            'tests/test_resume_preparation.py::test_auto_grant_is_bound_to_exact_digest'
        ],
        desc='flip scoped-approval digest match -> grant would bind the wrong arguments',
    ),
]


def _run_tests(selectors: list[str]) -> bool:
    """Return True if the tests PASS (mutant survived), False if they FAIL (killed)."""
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', *selectors, '-q'],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _target_files() -> set[str]:
    return {m.file for m in MUTATIONS}


def _assert_clean_worktree() -> None:
    files = sorted(_target_files())
    proc = subprocess.run(['git', 'diff', '--quiet', '--', *files], cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise SystemExit(
            'Refusing to run: target trust-module files have uncommitted changes.\n'
            'Commit or stash them first so mutations restore to a known baseline:\n  '
            + '\n  '.join(files)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--list', action='store_true', help='list mutations without running them'
    )
    args = parser.parse_args(argv)

    if args.list:
        for m in MUTATIONS:
            print(f'- {m.file}: {m.desc}')
            print(f'    {m.old!r} -> {m.new!r}  (killed by: {", ".join(m.tests)})')
        return 0

    _assert_clean_worktree()

    survived: list[Mutation] = []
    missing: list[Mutation] = []
    for i, m in enumerate(MUTATIONS, 1):
        path = REPO_ROOT / m.file
        original = path.read_text(encoding='utf-8')
        if original.count(m.old) != 1:
            print(
                f'[{i}/{len(MUTATIONS)}] SKIP (stale registry): {m.file} '
                f'does not contain exactly one occurrence of {m.old!r}',
                file=sys.stderr,
            )
            missing.append(m)
            continue
        path.write_text(original.replace(m.old, m.new, 1), encoding='utf-8')
        try:
            tests_passed = _run_tests(m.tests)
        finally:
            path.write_text(original, encoding='utf-8')
        if tests_passed:
            survived.append(m)
            print(f'[{i}/{len(MUTATIONS)}] ❌ SURVIVED: {m.desc}', file=sys.stderr)
        else:
            print(f'[{i}/{len(MUTATIONS)}] ✅ killed: {m.desc}')

    if missing:
        print(
            f'\n{len(missing)} mutation(s) had a stale target string — update '
            f'scripts/run_mutation_smoke.py to match the current code.',
            file=sys.stderr,
        )
    if survived:
        print(
            f'\n{len(survived)} mutant(s) SURVIVED — the guard tests do not catch a '
            f'dangerous change on the trust boundary. This is a test gap (Roadmap A3).',
            file=sys.stderr,
        )
    if survived or missing:
        return 1
    print(f'\nAll {len(MUTATIONS)} trust-boundary mutants killed by their guard tests.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
