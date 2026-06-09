"""Keep the A3 mutation-smoke registry in sync with the code it mutates.

scripts/run_mutation_smoke.py injects exact-substring mutations into the L3 trust
modules. If those modules are edited so a target string no longer matches, the nightly
mutant would silently SKIP instead of guarding. This test fails fast in the normal suite
when that happens, so the registry is repaired in the same change.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'run_mutation_smoke', _REPO_ROOT / 'scripts' / 'run_mutation_smoke.py'
)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _mod
_SPEC.loader.exec_module(_mod)

MUTATIONS = _mod.MUTATIONS


def test_every_mutation_target_is_present_exactly_once() -> None:
    problems: list[str] = []
    for m in MUTATIONS:
        path = _REPO_ROOT / m.file
        if not path.exists():
            problems.append(f'{m.file}: file missing')
            continue
        count = path.read_text(encoding='utf-8').count(m.old)
        if count != 1:
            problems.append(f'{m.file}: {m.old!r} found {count}x (expected 1)')
    assert not problems, 'mutation-smoke registry is stale:\n  ' + '\n  '.join(problems)


def test_every_mutation_declares_guard_tests() -> None:
    for m in MUTATIONS:
        assert m.tests, f'mutation {m.desc!r} has no guard tests declared'


def test_mutation_replacement_differs_from_original() -> None:
    for m in MUTATIONS:
        assert m.old != m.new, f'mutation {m.desc!r} is a no-op (old == new)'
