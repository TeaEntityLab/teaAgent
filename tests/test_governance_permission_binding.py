"""Roadmap A2: structural CV-8 enforcement for L3 trust modules.

Makes "every module that can grant/escalate a permission has a spec-linked permission
boundary" a test, not prose (governance/AGENT_RULES.md, governance/plans/ADOPTION-ROADMAP.md A2).

Two guarantees:
  1. Each registered L3 trust module has a governance spec that declares Forbidden +
     Requires-Human-Review and references the module path.
  2. Every guard test a governance spec cites (``tests/...py::test_name``) actually exists —
     so specs cannot drift into citing tests that were renamed or removed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Registry of L3 trust modules -> their permission-binding spec. Adding a module that can
# grant or escalate a permission without a spec here should be a deliberate, reviewed act.
L3_TRUST_MODULES: dict[str, str] = {
    'teaagent/integration/resume_preparation.py': 'governance/specs/SURF-010-resume-parity.md',
    'teaagent/ergonomics/_approval_state.py': (
        'governance/specs/approval-store-permission-binding.md'
    ),
}

_REQUIRED_SECTIONS = ('Forbidden', 'Requires Human Review')
# Matches references like ``tests/foo/bar.py::test_name``.
_GUARD_REF = re.compile(r'(tests/[\w./-]+\.py)::([A-Za-z_][\w]*)')


@pytest.mark.parametrize(('module', 'spec'), sorted(L3_TRUST_MODULES.items()))
def test_l3_trust_module_has_permission_binding_spec(module: str, spec: str) -> None:
    module_path = REPO_ROOT / module
    spec_path = REPO_ROOT / spec
    assert module_path.exists(), f'L3 trust module missing: {module}'
    assert spec_path.exists(), f'permission-binding spec missing for {module}: {spec}'

    text = spec_path.read_text(encoding='utf-8')
    for section in _REQUIRED_SECTIONS:
        assert section in text, f'{spec} must declare a "{section}" section (CV-8)'
    assert module in text, f'{spec} must reference its module path {module}'


@pytest.mark.parametrize('spec', sorted(set(L3_TRUST_MODULES.values())))
def test_spec_cited_guard_tests_exist(spec: str) -> None:
    """Every ``tests/...::test_*`` cited in a spec must resolve to a real test function."""
    text = (REPO_ROOT / spec).read_text(encoding='utf-8')
    refs = set(_GUARD_REF.findall(text))
    assert refs, f'{spec} should cite at least one guard test for its Forbidden rules'
    missing: list[str] = []
    for rel_file, test_name in sorted(refs):
        test_file = REPO_ROOT / rel_file
        if not test_file.exists():
            missing.append(f'{rel_file} (file not found)')
            continue
        if f'def {test_name}(' not in test_file.read_text(encoding='utf-8'):
            missing.append(f'{rel_file}::{test_name} (function not found)')
    assert not missing, f'{spec} cites guard tests that do not exist: {missing}'
