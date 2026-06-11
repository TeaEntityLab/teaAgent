from __future__ import annotations

from teaagent.types import (
    AgentHarnessError,
    BudgetExceededError,
    DenialReasonCode,
    ErrorCategory,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)


def test_categories_are_string_enum() -> None:
    assert ErrorCategory.TRANSIENT == 'transient'
    assert ErrorCategory.MODEL_LOGIC == 'model_logic'
    assert ErrorCategory.PERMISSION == 'permission'
    assert ErrorCategory.SYSTEM == 'system'


def test_category_is_instance_of_str() -> None:
    for category in ErrorCategory:
        assert isinstance(category, str)


def test_agent_harness_error_is_exception() -> None:
    exc = AgentHarnessError('base error')
    assert isinstance(exc, Exception)
    assert exc.category == ErrorCategory.SYSTEM


def test_budget_exceeded_is_model_logic() -> None:
    exc = BudgetExceededError('too many iterations')
    assert isinstance(exc, AgentHarnessError)
    assert exc.category == ErrorCategory.MODEL_LOGIC


def test_tool_validation_error_is_model_logic() -> None:
    exc = ToolValidationError('bad input')
    assert isinstance(exc, AgentHarnessError)
    assert exc.category == ErrorCategory.MODEL_LOGIC


def test_tool_permission_error_is_permission() -> None:
    exc = ToolPermissionError('not allowed')
    assert isinstance(exc, AgentHarnessError)
    assert exc.category == ErrorCategory.PERMISSION


def test_tool_execution_error_is_system() -> None:
    exc = ToolExecutionError('runtime failure')
    assert isinstance(exc, AgentHarnessError)
    assert exc.category == ErrorCategory.SYSTEM


def test_error_message_is_preserved() -> None:
    for cls in [
        BudgetExceededError,
        ToolValidationError,
        ToolPermissionError,
        ToolExecutionError,
    ]:
        exc = cls('test message 123')
        # str() includes the original message; it may also include a hint suffix
        assert 'test message 123' in str(exc)


def test_permission_errors_create_failed_permission_status() -> None:
    exc = ToolPermissionError('blocked')
    assert f'failed:{exc.category}' == 'failed:permission'


def test_system_errors_create_failed_system_status() -> None:
    exc = ToolExecutionError('crash')
    assert f'failed:{exc.category}' == 'failed:system'


def test_model_logic_errors_create_failed_model_logic_status() -> None:
    exc = BudgetExceededError('budget')
    assert f'failed:{exc.category}' == 'failed:model_logic'


def test_all_reason_codes_are_strings() -> None:
    for code in DenialReasonCode:
        assert isinstance(code, str)


def test_read_only_mode_code() -> None:
    assert DenialReasonCode.READ_ONLY_MODE == 'read_only_mode'


def test_workspace_write_mode_code() -> None:
    assert DenialReasonCode.WORKSPACE_WRITE_MODE == 'workspace_write_mode'


def test_file_policy_denied_code() -> None:
    assert DenialReasonCode.FILE_POLICY_DENIED == 'file_policy_denied'


def test_plan_contract_denied_code() -> None:
    assert DenialReasonCode.PLAN_CONTRACT_DENIED == 'plan_contract_denied'


def test_jit_user_denied_code() -> None:
    assert DenialReasonCode.JIT_USER_DENIED == 'jit_user_denied'


def test_jit_no_approval_code() -> None:
    assert DenialReasonCode.JIT_NO_APPROVAL == 'jit_no_approval'


def test_multisig_no_quorum_code() -> None:
    assert DenialReasonCode.MULTISIG_NO_QUORUM == 'multisig_no_quorum'


def test_auto_mode_blocked_code() -> None:
    assert DenialReasonCode.AUTO_MODE_BLOCKED == 'auto_mode_blocked'


def test_missing_state_code() -> None:
    assert DenialReasonCode.MISSING_STATE == 'missing_state'


def test_enum_values_distinct() -> None:
    values = [code.value for code in DenialReasonCode]
    assert len(values) == len(set(values))


def test_default_reason_code_is_none() -> None:
    exc = ToolPermissionError('blocked')
    assert exc.reason_code is None


def test_can_set_reason_code() -> None:
    exc = ToolPermissionError('blocked', reason_code=DenialReasonCode.READ_ONLY_MODE)
    assert exc.reason_code == DenialReasonCode.READ_ONLY_MODE


def test_reason_code_in_error_hierarchy() -> None:
    exc = ToolPermissionError('blocked', reason_code=DenialReasonCode.JIT_USER_DENIED)
    assert isinstance(exc, AgentHarnessError)
    assert exc.category == ErrorCategory.PERMISSION
    assert exc.reason_code == DenialReasonCode.JIT_USER_DENIED


def test_hint_still_defaults_when_no_reason_code() -> None:
    exc = ToolPermissionError('blocked')
    assert '--permission-mode' in str(exc)


def test_hint_still_defaults_with_reason_code() -> None:
    exc = ToolPermissionError('blocked', reason_code=DenialReasonCode.READ_ONLY_MODE)
    assert '--permission-mode' in str(exc)


def test_custom_hint_with_reason_code() -> None:
    exc = ToolPermissionError(
        'blocked',
        hint='custom hint',
        reason_code=DenialReasonCode.AUTO_MODE_BLOCKED,
    )
    assert exc.hint == 'custom hint'
    assert exc.reason_code == DenialReasonCode.AUTO_MODE_BLOCKED
