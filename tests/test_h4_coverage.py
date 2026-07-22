# test-type: contract
"""Tests for ADR-0031 H4 coverage-completeness evidence.

Companion to docs/specs/rbac-shadow-to-enforce-promotion-spec-2026-07-11.md
section 3.1 criterion 2. The checker prepares evidence only: it inventories
enabled policies and RBAC roles, verifies allow/deny test declarations exist,
and reports gaps. It does not run tests, judge test semantics, or flip H4 modes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from teaagent.governance.h4_coverage import (
    H4_COVERAGE_SECTION,
    build_h4_coverage_report,
    inventory_h4_coverage_items,
    load_h4_coverage_declarations,
)
from teaagent.governance.policy_engine import (
    Policy,
    PolicyCondition,
    PolicyEffect,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)
from teaagent.governance.rbac import Permission, Role, RoleStore

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / 'scripts' / 'check_h4_coverage.py'


def _write_test_file(root: Path, rel: str = 'tests/test_h4_policy_matrix.py') -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('def test_placeholder():\n    assert True\n', encoding='utf-8')
    return rel


def _write_matrix(
    root: Path,
    *,
    policies: str = '',
    roles: str = '',
    path: str = 'docs/architecture/claim-to-test-traceability.yaml',
) -> Path:
    matrix = root / path
    matrix.parent.mkdir(parents=True, exist_ok=True)
    matrix.write_text(
        f"""version: "1"
claims: []
{H4_COVERAGE_SECTION}:
  policies:
{policies or '    []'}
  roles:
{roles or '    []'}
""",
        encoding='utf-8',
    )
    return matrix


def _save_policy(root: Path, policy_id: str = 'deny-shell') -> None:
    PolicyStore(root).save(
        Policy(
            policy_id=policy_id,
            policy_type=PolicyType.APPROVAL,
            effect=PolicyEffect.DENY,
            conditions=[PolicyCondition('tool_name', 'equals', 'shell')],
            precedence=PolicyPrecedence.HIGH,
            description='deny shell',
        )
    )


def _save_role(root: Path, role_id: str = 'reviewer') -> None:
    RoleStore(root).save_role(
        Role(
            role_id=role_id,
            name='Reviewer',
            permissions={Permission.READ_FILE},
            description='read-only reviewer',
        )
    )


def test_empty_workspace_and_empty_matrix_is_complete(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)
    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is True
    assert report.policies == []
    assert report.roles == []
    assert report.gaps == []
    assert 'does not run tests' in report.to_dict()['note']


def test_inventory_reads_enabled_policies_and_roles(tmp_path: Path) -> None:
    _save_policy(tmp_path)
    PolicyStore(tmp_path).save(
        Policy(
            policy_id='disabled',
            policy_type=PolicyType.APPROVAL,
            effect=PolicyEffect.ALLOW,
            enabled=False,
        )
    )
    _save_role(tmp_path)

    policies, roles = inventory_h4_coverage_items(tmp_path)

    assert [policy.item_id for policy in policies] == ['deny-shell']
    assert policies[0].metadata['effect'] == 'deny'
    assert [role.item_id for role in roles] == ['reviewer']
    assert roles[0].metadata['permissions'] == ['read_file']


def test_missing_policy_declaration_is_a_gap(tmp_path: Path) -> None:
    _save_policy(tmp_path)
    matrix = _write_matrix(tmp_path)

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is False
    assert [gap.issue for gap in report.gaps] == ['missing_declaration']
    assert report.gaps[0].kind == 'policy'
    assert report.gaps[0].item_id == 'deny-shell'


def test_missing_role_declaration_is_a_gap(tmp_path: Path) -> None:
    _save_role(tmp_path)
    matrix = _write_matrix(tmp_path)

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is False
    assert [gap.issue for gap in report.gaps] == ['missing_declaration']
    assert report.gaps[0].kind == 'role'
    assert report.gaps[0].item_id == 'reviewer'


def test_declaration_requires_allow_and_deny_tests(tmp_path: Path) -> None:
    _save_policy(tmp_path)
    test_ref = _write_test_file(tmp_path)
    matrix = _write_matrix(
        tmp_path,
        policies=f"""    - policy_id: deny-shell
      allow_tests:
        - {test_ref}::test_allow
      deny_tests: []
""",
    )

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is False
    assert [gap.issue for gap in report.gaps] == ['missing_deny_tests']


def test_missing_test_reference_is_a_gap(tmp_path: Path) -> None:
    _save_role(tmp_path)
    existing = _write_test_file(tmp_path)
    matrix = _write_matrix(
        tmp_path,
        roles=f"""    - role_id: reviewer
      allow_tests:
        - {existing}::test_allow
      deny_tests:
        - tests/missing_h4_role.py::test_deny
""",
    )

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is False
    assert [gap.issue for gap in report.gaps] == ['missing_test_file']
    assert 'tests/missing_h4_role.py::test_deny' in report.gaps[0].detail


def test_stale_declaration_is_a_gap(tmp_path: Path) -> None:
    test_ref = _write_test_file(tmp_path)
    matrix = _write_matrix(
        tmp_path,
        policies=f"""    - policy_id: stale-policy
      allow_tests:
        - {test_ref}::test_allow
      deny_tests:
        - {test_ref}::test_deny
""",
    )

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)

    assert report.ok is False
    assert [gap.issue for gap in report.gaps] == ['stale_declaration']


def test_complete_policy_and_role_declarations_pass(tmp_path: Path) -> None:
    _save_policy(tmp_path)
    _save_role(tmp_path)
    test_ref = _write_test_file(tmp_path)
    matrix = _write_matrix(
        tmp_path,
        policies=f"""    - policy_id: deny-shell
      allow_tests:
        - {test_ref}::test_policy_allow
      deny_tests:
        - {test_ref}::test_policy_deny
""",
        roles=f"""    - role_id: reviewer
      allow_tests:
        - {test_ref}::test_role_allow
      deny_tests:
        - {test_ref}::test_role_deny
""",
    )

    report = build_h4_coverage_report(tmp_path, matrix_path=matrix)
    data = report.to_dict()

    assert report.ok is True
    assert data['policy_count'] == 1
    assert data['role_count'] == 1
    assert data['gaps'] == []


def test_duplicate_declarations_fail_fast(tmp_path: Path) -> None:
    test_ref = _write_test_file(tmp_path)
    matrix = _write_matrix(
        tmp_path,
        policies=f"""    - policy_id: dup
      allow_tests:
        - {test_ref}::test_a
      deny_tests:
        - {test_ref}::test_b
    - policy_id: dup
      allow_tests:
        - {test_ref}::test_c
      deny_tests:
        - {test_ref}::test_d
""",
    )

    with pytest.raises(ValueError, match='duplicate H4 policy coverage declaration'):
        load_h4_coverage_declarations(matrix)


def test_cli_returns_zero_when_no_gaps(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(tmp_path),
            '--matrix',
            str(matrix),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload['ok'] is True
    assert payload['gaps'] == []


def test_cli_returns_one_for_gaps(tmp_path: Path) -> None:
    _save_policy(tmp_path)
    matrix = _write_matrix(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(tmp_path),
            '--matrix',
            str(matrix),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert 'gap(s)' in result.stderr
    payload = json.loads(result.stdout)
    assert payload['gaps'][0]['issue'] == 'missing_declaration'


def test_cli_returns_two_for_invalid_matrix(tmp_path: Path) -> None:
    matrix = tmp_path / 'bad.yaml'
    matrix.write_text('h4_policy_rbac_coverage: [', encoding='utf-8')

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            '--root',
            str(tmp_path),
            '--matrix',
            str(matrix),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert 'invalid YAML' in result.stderr
