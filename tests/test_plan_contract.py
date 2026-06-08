"""Unit tests for plan artifact binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.chat_agent import _apply_plan_contract
from teaagent.plan import load_plan_contract
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner
from teaagent.types import AuditLogger, PermissionMode, ToolRegistry


def _write_minimal_plan(path: Path, task: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'# TeaAgent Plan\n\n## Summary\n\n- **Task:** {task}\n',
        encoding='utf-8',
    )


def test_load_plan_contract_requires_plans_dir(tmp_path: Path) -> None:
    external = tmp_path / 'outside.md'
    _write_minimal_plan(external, 'Outside task')
    with pytest.raises(ValueError, match='\\.teaagent/plans'):
        load_plan_contract(external, root=tmp_path)


def test_load_plan_contract_allows_external_with_flag(tmp_path: Path) -> None:
    external = tmp_path / 'outside.md'
    _write_minimal_plan(external, 'External plan task')
    contract = load_plan_contract(external, root=tmp_path, allow_external_plan=True)
    assert contract.task == 'External plan task'


def test_load_plan_contract_accepts_plans_dir_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / '.teaagent' / 'plans' / '20260526-test.md'
    _write_minimal_plan(artifact, 'Plans dir task')
    contract = load_plan_contract(artifact, root=tmp_path)
    assert contract.rel_path == '.teaagent/plans/20260526-test.md'
    assert contract.task == 'Plans dir task'


def test_apply_plan_contract_binds_validator_write_scope(tmp_path: Path) -> None:
    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=AuditLogger(path=None),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
    )
    plan_path = tmp_path / '.teaagent' / 'plans' / 'scope.md'
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text('# TeaAgent Plan\n', encoding='utf-8')

    _apply_plan_contract(
        runner,
        {
            'plan_contract': {
                'path': str(plan_path),
                'rel_path': '.teaagent/plans/scope.md',
                'content_hash': 'abc123',
                'task': 'scoped write',
                'file_targets': ['allowed.txt'],
            }
        },
    )

    contract = runner.plan_validator.get_plan_contract()
    assert contract is not None
    assert contract.file_targets == frozenset({'allowed.txt'})
    drift = runner.plan_validator.validate_write_allowed(
        tool_name='workspace_write_file',
        context={
            'plan_contract': {
                'content_hash': 'abc123',
            }
        },
        tool_arguments={'path': 'outside.txt', 'content': 'nope'},
    )
    assert drift is not None
    assert 'outside the approved plan scope' in drift
