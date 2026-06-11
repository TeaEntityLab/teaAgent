"""Unit tests for plan artifact binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.chat_agent import _apply_plan_contract
from teaagent.plan import load_plan_contract
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner
from teaagent.runner._plan_validator import PlanValidator
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


def test_plan_validator_evaluate_write_gate_allows_scoped_write() -> None:
    validator = PlanValidator(
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
    )
    validator.set_plan_contract(
        {
            'rel_path': '.teaagent/plans/scope.md',
            'file_targets': ['allowed.txt'],
            'content_hash': 'abc123',
        }
    )

    gate_error = validator.evaluate_write_gate(
        tool_name='workspace_write_file',
        context={},
        tool_arguments={'path': 'allowed.txt', 'content': 'ok'},
    )

    assert gate_error is None


def test_plan_validator_evaluate_write_gate_blocks_drift_before_lint() -> None:
    validator = PlanValidator(
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
    )
    validator.set_plan_contract(
        {
            'rel_path': '.teaagent/plans/scope.md',
            'file_targets': ['allowed.txt'],
            'content_hash': 'abc123',
        }
    )
    validator.set_read_only_lint_errors(['lint error'])

    gate_error = validator.evaluate_write_gate(
        tool_name='workspace_write_file',
        context={},
        tool_arguments={'path': 'blocked.txt', 'content': 'nope'},
    )

    assert gate_error is not None
    assert 'outside the approved plan scope' in gate_error


def test_plan_validator_evaluate_write_gate_blocks_read_only_lint() -> None:
    validator = PlanValidator(
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY),
    )
    validator.set_read_only_lint_errors(['lint error'])

    gate_error = validator.evaluate_write_gate(
        tool_name='workspace_write_file',
        context={},
        tool_arguments={'path': 'anything.txt', 'content': 'nope'},
    )

    assert gate_error is not None
    assert 'read-only runs cannot invoke tools' in gate_error


# ---------------------------------------------------------------------------
# Negative test cases for plan.py
# ---------------------------------------------------------------------------


def test_load_plan_contract_missing_file(tmp_path: Path) -> None:
    """Test that loading a plan from a missing file raises FileNotFoundError."""
    missing = tmp_path / '.teaagent' / 'plans' / 'missing.md'
    with pytest.raises(FileNotFoundError, match='plan artifact not found'):
        load_plan_contract(missing, root=tmp_path)


def test_load_plan_contract_missing_task_line(tmp_path: Path) -> None:
    """Test that a plan without a **Task:** line raises ValueError."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'no-task.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\nNo task here\n', encoding='utf-8'
    )
    with pytest.raises(ValueError, match='missing.*Task:'):
        load_plan_contract(artifact, root=tmp_path)


def test_load_plan_contract_empty_task(tmp_path: Path) -> None:
    """Test that a plan with empty task is handled."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'empty-task.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:**   \n', encoding='utf-8'
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    # Empty task should be captured
    assert contract.task == ''


def test_load_plan_contract_empty_file(tmp_path: Path) -> None:
    """Test that loading an empty plan file raises ValueError."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'empty.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='missing.*Task:'):
        load_plan_contract(artifact, root=tmp_path)


def test_load_plan_contract_whitespace_only_file(tmp_path: Path) -> None:
    """Test that a plan file with only whitespace raises ValueError."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'whitespace.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text('   \n\t\n  ', encoding='utf-8')
    with pytest.raises(ValueError, match='missing.*Task:'):
        load_plan_contract(artifact, root=tmp_path)


def test_load_plan_contract_invalid_markdown(tmp_path: Path) -> None:
    """Test that a plan with invalid markdown structure is handled."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'invalid.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text('Random text without proper structure', encoding='utf-8')
    with pytest.raises(ValueError, match='missing.*Task:'):
        load_plan_contract(artifact, root=tmp_path)


def test_load_plan_contract_special_characters_in_task(tmp_path: Path) -> None:
    """Test that special characters in task are handled."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'special.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Fix bug with "quotes" and \'apostrophes\' and <brackets>\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert 'quotes' in contract.task


def test_load_plan_contract_unicode_in_task(tmp_path: Path) -> None:
    """Test that unicode characters in task are handled."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'unicode.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** 修复bug和添加功能 🐛\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert '修复bug' in contract.task


def test_load_plan_contract_very_long_task(tmp_path: Path) -> None:
    """Test that very long task descriptions are handled."""
    long_task = 'Fix bug ' * 1000
    artifact = tmp_path / '.teaagent' / 'plans' / 'long.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        f'# TeaAgent Plan\n\n## Summary\n\n- **Task:** {long_task}\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert len(contract.task) > 1000


def test_load_plan_contract_multiple_task_lines(tmp_path: Path) -> None:
    """Test that multiple **Task:** lines are handled (first one wins)."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'multi-task.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** First task\n- **Task:** Second task\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    # Should match the first occurrence
    assert 'First task' in contract.task


def test_load_plan_contract_relative_path_resolution(tmp_path: Path) -> None:
    """Test that relative paths are resolved correctly."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'relative.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test task\n',
        encoding='utf-8',
    )
    contract = load_plan_contract('.teaagent/plans/relative.md', root=tmp_path)
    assert contract.rel_path == '.teaagent/plans/relative.md'


def test_load_plan_contract_absolute_path(tmp_path: Path) -> None:
    """Test that absolute paths are handled."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'absolute.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test task\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact.resolve(), root=tmp_path)
    assert contract.task == 'Test task'


def test_load_plan_contract_file_targets_extraction(tmp_path: Path) -> None:
    """Test that file targets are extracted from plan content."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'targets.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test task\n\n## Files likely touched\n\n- `src/main.py`\n- `tests/test_main.py`\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert 'src/main.py' in contract.file_targets
    assert 'tests/test_main.py' in contract.file_targets


def test_load_plan_contract_no_file_targets(tmp_path: Path) -> None:
    """Test that plans without file targets section have empty targets."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'no-targets.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test task\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    assert len(contract.file_targets) == 0


def test_load_plan_contract_malformed_file_targets(tmp_path: Path) -> None:
    """Test that malformed file targets are handled gracefully."""
    artifact = tmp_path / '.teaagent' / 'plans' / 'bad-targets.md'
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test task\n\n## Files likely touched\n\nRandom text without list format\n',
        encoding='utf-8',
    )
    contract = load_plan_contract(artifact, root=tmp_path)
    # Should not crash
    assert contract.task == 'Test task'


def test_plan_contract_allows_file_write_with_no_targets(tmp_path: Path) -> None:
    """Test that file writes are allowed when no targets specified."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset(),
    )
    # With no targets, all writes should be allowed
    assert contract.allows_file_write('any/path.py') is True


def test_plan_contract_blocks_file_write_outside_targets(tmp_path: Path) -> None:
    """Test that file writes are blocked when outside approved targets."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset({'src/main.py'}),
    )
    assert contract.allows_file_write('src/other.py') is False


def test_plan_contract_allows_file_write_inside_targets(tmp_path: Path) -> None:
    """Test that file writes are allowed when inside approved targets."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset({'src/main.py'}),
    )
    assert contract.allows_file_write('src/main.py') is True


def test_plan_contract_allows_subdirectory_writes(tmp_path: Path) -> None:
    """Test that writes to subdirectories of approved targets are allowed."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset({'src'}),  # Without trailing slash
    )
    assert contract.allows_file_write('src/subdir/file.py') is True


def test_plan_contract_blocks_different_directory(tmp_path: Path) -> None:
    """Test that writes to different directories are blocked."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset({'src/'}),
    )
    assert contract.allows_file_write('tests/file.py') is False


def test_plan_contract_validate_with_empty_task(tmp_path: Path) -> None:
    """Test that validation catches empty task."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'plan.md',
        rel_path='plan.md',
        content_hash='abc',
        task='',
        file_targets=frozenset(),
    )
    errors = contract.validate()
    assert len(errors) > 0
    assert 'empty' in errors[0].lower()


def test_plan_contract_validate_with_missing_file(tmp_path: Path) -> None:
    """Test that validation catches missing plan file."""
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=tmp_path / 'nonexistent.md',
        rel_path='nonexistent.md',
        content_hash='abc',
        task='test',
        file_targets=frozenset(),
    )
    errors = contract.validate()
    assert len(errors) > 0
    assert 'not found' in errors[0].lower()


def test_plan_contract_validate_with_valid_contract(tmp_path: Path) -> None:
    """Test that validation passes for valid contract."""
    artifact = tmp_path / 'plan.md'
    artifact.write_text('test', encoding='utf-8')
    from teaagent.plan import PlanContract

    contract = PlanContract(
        path=artifact,
        rel_path='plan.md',
        content_hash='abc',
        task='test task',
        file_targets=frozenset(),
    )
    errors = contract.validate()
    assert len(errors) == 0


def test_plan_content_hash_consistency(tmp_path: Path) -> None:
    """Test that content hash is consistent for same content."""
    from teaagent.plan import plan_content_hash

    content = '# TeaAgent Plan\n\n## Summary\n\n- **Task:** Test\n'
    hash1 = plan_content_hash(content)
    hash2 = plan_content_hash(content)
    assert hash1 == hash2


def test_plan_content_hash_different_for_different_content(tmp_path: Path) -> None:
    """Test that content hash differs for different content."""
    from teaagent.plan import plan_content_hash

    hash1 = plan_content_hash('content1')
    hash2 = plan_content_hash('content2')
    assert hash1 != hash2


def test_plan_content_hash_empty_string(tmp_path: Path) -> None:
    """Test that content hash works for empty string."""
    from teaagent.plan import plan_content_hash

    hash_value = plan_content_hash('')
    assert hash_value is not None
    assert len(hash_value) > 0
