from __future__ import annotations

import unittest

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.errors import ErrorCategory, InvalidToolDecision
from teaagent.runner import (
    AgentRunner,
    FinalAnswer,
    ToolRequest,
    validate_tool_decision,
)
from teaagent.tools import ToolAnnotations, ToolRegistry


class ValidateToolDecisionTests(unittest.TestCase):
    """Unit tests for validate_tool_decision() structural checks."""

    def test_valid_tool_decision(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': 'workspace_read_file',
                'arguments': {'path': 'foo.py'},
            }
        )
        self.assertTrue(valid)
        self.assertEqual(reason, '')

    def test_missing_tool_name(self) -> None:
        valid, reason = validate_tool_decision({'arguments': {'a': 1}})
        self.assertFalse(valid)
        self.assertIn('tool_name', reason)

    def test_empty_tool_name(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': '',
                'arguments': {'a': 1},
            }
        )
        self.assertFalse(valid)
        self.assertIn('non-empty', reason)

    def test_whitespace_only_tool_name(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': '   ',
                'arguments': {'a': 1},
            }
        )
        self.assertFalse(valid)
        self.assertIn('non-empty', reason)

    def test_tool_name_not_string(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': 42,
                'arguments': {'a': 1},
            }
        )
        self.assertFalse(valid)
        self.assertIn('must be string', reason)

    def test_missing_arguments(self) -> None:
        valid, reason = validate_tool_decision({'tool_name': 'echo'})
        self.assertFalse(valid)
        self.assertIn('arguments', reason)

    def test_arguments_is_none(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': 'echo',
                'arguments': None,
            }
        )
        self.assertFalse(valid)
        self.assertIn('arguments', reason)

    def test_arguments_is_string(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': 'echo',
                'arguments': 'not-a-dict',
            }
        )
        self.assertFalse(valid)
        self.assertIn('must be dict', reason)

    def test_arguments_is_list(self) -> None:
        valid, reason = validate_tool_decision(
            {
                'tool_name': 'echo',
                'arguments': [1, 2, 3],
            }
        )
        self.assertFalse(valid)
        self.assertIn('must be dict', reason)

    def test_input_not_dict(self) -> None:
        valid, reason = validate_tool_decision([1, 2, 3])  # type: ignore[arg-type]
        self.assertFalse(valid)
        self.assertIn('not a dict', reason)

    def test_empty_dict_still_works_if_tool_name_empty(self) -> None:
        valid, reason = validate_tool_decision({})
        self.assertFalse(valid)
        self.assertIn('tool_name', reason)


class InvalidToolDecisionExceptionTests(unittest.TestCase):
    """Tests for the InvalidToolDecision exception class."""

    def test_category_is_model_logic(self) -> None:
        exc = InvalidToolDecision('missing tool_name')
        self.assertEqual(exc.category, ErrorCategory.MODEL_LOGIC)

    def test_default_hint(self) -> None:
        exc = InvalidToolDecision('bad arguments')
        self.assertIsNotNone(exc.hint)
        self.assertIn('structurally invalid', str(exc))

    def test_raw_decision_preview(self) -> None:
        exc = InvalidToolDecision(
            'empty tool_name', raw_decision_preview='{"tool_name":""}'
        )
        self.assertEqual(exc.raw_decision_preview, '{"tool_name":""}')

    def test_subclass_of_agent_harness_error(self) -> None:
        from teaagent.errors import AgentHarnessError

        exc = InvalidToolDecision('test')
        self.assertIsInstance(exc, AgentHarnessError)


class AgentRunnerInvalidDecisionIntegrationTest(unittest.TestCase):
    """Integration tests: AgentRunner rejects structurally invalid ToolRequest."""

    def _make_runner(self) -> AgentRunner:
        registry = ToolRegistry()
        registry.register(
            name='echo',
            description='echo tool',
            input_schema={
                'type': 'object',
                'properties': {'msg': {'type': 'string'}},
                'required': ['msg'],
            },
            output_schema={
                'type': 'object',
                'properties': {'out': {'type': 'string'}},
                'required': ['out'],
            },
            annotations=ToolAnnotations(
                read_only=True,
                destructive=False,
                idempotent=True,
            ),
            handler=lambda args: {'out': args['msg']},
        )
        return AgentRunner(
            registry=registry,
            audit=AuditLogger(),
            budget=RunBudget(max_iterations=3, max_tool_calls=3),
        )

    def test_invalid_tool_name_empty_string_causes_run_failed(self) -> None:
        runner = self._make_runner()
        result = runner.run(
            task='echo something',
            decide=lambda _ctx: ToolRequest(
                tool_name='',
                arguments={'msg': 'hi'},
                call_id='bad-1',
            ),
            run_id='run-empty-tool',
        )
        self.assertEqual(result.status, f'failed:{ErrorCategory.MODEL_LOGIC}')
        self.assertIsNotNone(result.error_message)
        self.assertIn('tool_name', result.error_message)

    def test_invalid_tool_name_whitespace_causes_run_failed(self) -> None:
        runner = self._make_runner()
        result = runner.run(
            task='echo something',
            decide=lambda _ctx: ToolRequest(
                tool_name='   ',
                arguments={'msg': 'hi'},
                call_id='bad-2',
            ),
            run_id='run-ws-tool',
        )
        self.assertEqual(result.status, f'failed:{ErrorCategory.MODEL_LOGIC}')
        self.assertIn('non-empty', result.error_message)

    def test_null_arguments_causes_run_failed(self) -> None:
        runner = self._make_runner()
        result = runner.run(
            task='echo something',
            decide=lambda _ctx: ToolRequest(
                tool_name='echo',
                arguments=None,  # type: ignore[arg-type]
                call_id='bad-3',
            ),
            run_id='run-null-args',
        )
        self.assertEqual(result.status, f'failed:{ErrorCategory.MODEL_LOGIC}')
        self.assertIn('arguments', result.error_message)

    def test_valid_tool_request_proceeds_normally(self) -> None:
        runner = self._make_runner()

        calls = iter(
            [
                ToolRequest(tool_name='echo', arguments={'msg': 'hi'}, call_id='c1'),
                FinalAnswer(content='done'),
            ]
        )
        result = runner.run(
            task='echo something',
            decide=lambda _ctx: next(calls),
            run_id='run-valid',
        )
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.final_answer.content, 'done')

    def test_audit_event_recorded_on_invalid_decision(self) -> None:
        runner = self._make_runner()
        runner.run(
            task='echo something',
            decide=lambda _ctx: ToolRequest(
                tool_name='',
                arguments=None,  # type: ignore[arg-type]
                call_id='audit-bad',
            ),
            run_id='run-audit-test',
        )
        decision_events = [
            e for e in runner.audit.events if e.event_type == 'tool_decision_invalid'
        ]
        self.assertEqual(len(decision_events), 1)
        event = decision_events[0]
        self.assertEqual(event.payload['tool_name'], '')
        self.assertIn('tool_name', event.payload['reason'])
        self.assertIn('raw_decision_preview', event.payload)

    def test_audit_event_contains_run_failed_after_invalid(self) -> None:
        runner = self._make_runner()
        runner.run(
            task='echo something',
            decide=lambda _ctx: ToolRequest(
                tool_name='',
                arguments=None,  # type: ignore[arg-type]
                call_id='audit-bad-2',
            ),
            run_id='run-audit-fail',
        )
        failed_events = [e for e in runner.audit.events if e.event_type == 'run_failed']
        self.assertGreaterEqual(len(failed_events), 1)
        self.assertEqual(
            failed_events[0].payload.get('category'),
            ErrorCategory.MODEL_LOGIC,
        )

    def test_final_answer_bypasses_validation(self) -> None:
        runner = self._make_runner()
        result = runner.run(
            task='simple question',
            decide=lambda _ctx: FinalAnswer(content='hello world'),
            run_id='run-final-bypass',
        )
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.final_answer.content, 'hello world')
        self.assertEqual(result.tool_calls, 0)


if __name__ == '__main__':
    unittest.main()
