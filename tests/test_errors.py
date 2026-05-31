from __future__ import annotations

import unittest

from teaagent.errors import (
    AgentHarnessError,
    BudgetExceededError,
    DenialReasonCode,
    ErrorCategory,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)


class ErrorCategoryTests(unittest.TestCase):
    def test_categories_are_string_enum(self) -> None:
        self.assertEqual(ErrorCategory.TRANSIENT, 'transient')
        self.assertEqual(ErrorCategory.MODEL_LOGIC, 'model_logic')
        self.assertEqual(ErrorCategory.PERMISSION, 'permission')
        self.assertEqual(ErrorCategory.SYSTEM, 'system')

    def test_category_is_instance_of_str(self) -> None:
        for category in ErrorCategory:
            self.assertIsInstance(category, str)


class ErrorHierarchyTests(unittest.TestCase):
    def test_agent_harness_error_is_exception(self) -> None:
        exc = AgentHarnessError('base error')
        self.assertIsInstance(exc, Exception)
        self.assertEqual(exc.category, ErrorCategory.SYSTEM)

    def test_budget_exceeded_is_model_logic(self) -> None:
        exc = BudgetExceededError('too many iterations')
        self.assertIsInstance(exc, AgentHarnessError)
        self.assertEqual(exc.category, ErrorCategory.MODEL_LOGIC)

    def test_tool_validation_error_is_model_logic(self) -> None:
        exc = ToolValidationError('bad input')
        self.assertIsInstance(exc, AgentHarnessError)
        self.assertEqual(exc.category, ErrorCategory.MODEL_LOGIC)

    def test_tool_permission_error_is_permission(self) -> None:
        exc = ToolPermissionError('not allowed')
        self.assertIsInstance(exc, AgentHarnessError)
        self.assertEqual(exc.category, ErrorCategory.PERMISSION)

    def test_tool_execution_error_is_system(self) -> None:
        exc = ToolExecutionError('runtime failure')
        self.assertIsInstance(exc, AgentHarnessError)
        self.assertEqual(exc.category, ErrorCategory.SYSTEM)

    def test_error_message_is_preserved(self) -> None:
        for cls in [
            BudgetExceededError,
            ToolValidationError,
            ToolPermissionError,
            ToolExecutionError,
        ]:
            exc = cls('test message 123')
            # str() includes the original message; it may also include a hint suffix
            self.assertIn('test message 123', str(exc))


class ErrorCategoryMatchingTests(unittest.TestCase):
    def test_permission_errors_create_failed_permission_status(self) -> None:
        exc = ToolPermissionError('blocked')
        self.assertEqual(f'failed:{exc.category}', 'failed:permission')

    def test_system_errors_create_failed_system_status(self) -> None:
        exc = ToolExecutionError('crash')
        self.assertEqual(f'failed:{exc.category}', 'failed:system')

    def test_model_logic_errors_create_failed_model_logic_status(self) -> None:
        exc = BudgetExceededError('budget')
        self.assertEqual(f'failed:{exc.category}', 'failed:model_logic')


class DenialReasonCodeTests(unittest.TestCase):
    def test_all_reason_codes_are_strings(self) -> None:
        for code in DenialReasonCode:
            self.assertIsInstance(code, str)

    def test_read_only_mode_code(self) -> None:
        self.assertEqual(DenialReasonCode.READ_ONLY_MODE, 'read_only_mode')

    def test_workspace_write_mode_code(self) -> None:
        self.assertEqual(DenialReasonCode.WORKSPACE_WRITE_MODE, 'workspace_write_mode')

    def test_file_policy_denied_code(self) -> None:
        self.assertEqual(DenialReasonCode.FILE_POLICY_DENIED, 'file_policy_denied')

    def test_plan_contract_denied_code(self) -> None:
        self.assertEqual(DenialReasonCode.PLAN_CONTRACT_DENIED, 'plan_contract_denied')

    def test_jit_user_denied_code(self) -> None:
        self.assertEqual(DenialReasonCode.JIT_USER_DENIED, 'jit_user_denied')

    def test_jit_no_approval_code(self) -> None:
        self.assertEqual(DenialReasonCode.JIT_NO_APPROVAL, 'jit_no_approval')

    def test_multisig_no_quorum_code(self) -> None:
        self.assertEqual(DenialReasonCode.MULTISIG_NO_QUORUM, 'multisig_no_quorum')

    def test_auto_mode_blocked_code(self) -> None:
        self.assertEqual(DenialReasonCode.AUTO_MODE_BLOCKED, 'auto_mode_blocked')

    def test_missing_state_code(self) -> None:
        self.assertEqual(DenialReasonCode.MISSING_STATE, 'missing_state')

    def test_enum_values_distinct(self) -> None:
        values = [code.value for code in DenialReasonCode]
        self.assertEqual(len(values), len(set(values)))


class ToolPermissionErrorReasonCodeTests(unittest.TestCase):
    def test_default_reason_code_is_none(self) -> None:
        exc = ToolPermissionError('blocked')
        self.assertIsNone(exc.reason_code)

    def test_can_set_reason_code(self) -> None:
        exc = ToolPermissionError(
            'blocked', reason_code=DenialReasonCode.READ_ONLY_MODE
        )
        self.assertEqual(exc.reason_code, DenialReasonCode.READ_ONLY_MODE)

    def test_reason_code_in_error_hierarchy(self) -> None:
        exc = ToolPermissionError(
            'blocked', reason_code=DenialReasonCode.JIT_USER_DENIED
        )
        self.assertIsInstance(exc, AgentHarnessError)
        self.assertEqual(exc.category, ErrorCategory.PERMISSION)
        self.assertEqual(exc.reason_code, DenialReasonCode.JIT_USER_DENIED)

    def test_hint_still_defaults_when_no_reason_code(self) -> None:
        exc = ToolPermissionError('blocked')
        self.assertIn('--permission-mode', str(exc))

    def test_hint_still_defaults_with_reason_code(self) -> None:
        exc = ToolPermissionError(
            'blocked', reason_code=DenialReasonCode.READ_ONLY_MODE
        )
        self.assertIn('--permission-mode', str(exc))

    def test_custom_hint_with_reason_code(self) -> None:
        exc = ToolPermissionError(
            'blocked',
            hint='custom hint',
            reason_code=DenialReasonCode.AUTO_MODE_BLOCKED,
        )
        self.assertEqual(exc.hint, 'custom hint')
        self.assertEqual(exc.reason_code, DenialReasonCode.AUTO_MODE_BLOCKED)


if __name__ == '__main__':
    unittest.main()
