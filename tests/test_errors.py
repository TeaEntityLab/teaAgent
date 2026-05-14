from __future__ import annotations

import unittest

from teaagent.errors import (
    AgentHarnessError,
    BudgetExceededError,
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


if __name__ == '__main__':
    unittest.main()
