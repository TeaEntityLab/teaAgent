from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

STATUS_PATTERN = re.compile(r'`(\d+)\s+passed`')


def parse_passed_count(pytest_output: str) -> int:
    match = re.search(r'(\d+)\s+passed', pytest_output)
    if not match:
        raise ValueError('Could not parse passed test count from pytest output.')
    return int(match.group(1))


def run_acceptance_pytest() -> int:
    result = subprocess.run(
        ['python3', '-m', 'pytest', 'tests/acceptance', '-q'],
        capture_output=True,
        text=True,
        check=False,
    )
    output = f'{result.stdout}\n{result.stderr}'
    if result.returncode != 0:
        raise RuntimeError(f'Acceptance pytest failed.\n{output}')
    return parse_passed_count(output)


def collect_acceptance_test_count(acceptance_tests_dir: Path) -> int:
    result = subprocess.run(
        ['python3', '-m', 'pytest', str(acceptance_tests_dir), '--collect-only', '-q'],
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


def update_acceptance_status(markdown: str, passed_count: int) -> str:
    replacement = f'`{passed_count} passed`'
    if STATUS_PATTERN.search(markdown):
        return STATUS_PATTERN.sub(replacement, markdown, count=1)
    raise ValueError('Could not find acceptance status marker in docs/acceptance.md.')


def build_acceptance_status(
    *,
    acceptance_doc: Path,
    passed_count: int | None,
    source: str,
    acceptance_tests_dir: Path,
) -> int:
    if passed_count is not None:
        count = passed_count
    elif source == 'pytest':
        count = run_acceptance_pytest()
    else:
        count = collect_acceptance_test_count(acceptance_tests_dir)
    original = acceptance_doc.read_text(encoding='utf-8')
    updated = update_acceptance_status(original, count)
    acceptance_doc.write_text(updated, encoding='utf-8')
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Refresh docs/acceptance.md current status from acceptance pytest results.'
    )
    parser.add_argument(
        '--acceptance-doc',
        default='docs/acceptance.md',
        help='Path to acceptance coverage markdown.',
    )
    parser.add_argument(
        '--passed-count',
        type=int,
        default=None,
        help='Optional override for passed count (used for deterministic checks).',
    )
    parser.add_argument(
        '--source',
        choices=('collect', 'pytest'),
        default='collect',
        help='Source of truth for acceptance count.',
    )
    parser.add_argument(
        '--acceptance-tests-dir',
        default='tests/acceptance',
        help='Acceptance tests directory for file-count source.',
    )
    args = parser.parse_args()
    count = build_acceptance_status(
        acceptance_doc=Path(args.acceptance_doc),
        passed_count=args.passed_count,
        source=args.source,
        acceptance_tests_dir=Path(args.acceptance_tests_dir),
    )
    print(f'Updated acceptance status to: {count} passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
