"""Unit tests for plan artifact binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.plan import load_plan_contract


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
