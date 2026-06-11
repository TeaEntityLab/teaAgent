from __future__ import annotations

from teaagent.runner import (
    AgentRunner,
    FinalAnswer,
    ToolRequest,
    validate_tool_decision,
)
from teaagent.types import (
    AuditLogger,
    ErrorCategory,
    InvalidToolDecision,
    RunBudget,
    ToolAnnotations,
    ToolRegistry,
)


def test_valid_tool_decision():
    valid, reason = validate_tool_decision(
        {
            'tool_name': 'workspace_read_file',
            'arguments': {'path': 'foo.py'},
        }
    )
    assert valid
    assert reason == ''


def test_missing_tool_name():
    valid, reason = validate_tool_decision({'arguments': {'a': 1}})
    assert not valid
    assert 'tool_name' in reason


def test_empty_tool_name():
    valid, reason = validate_tool_decision(
        {
            'tool_name': '',
            'arguments': {'a': 1},
        }
    )
    assert not valid
    assert 'non-empty' in reason


def test_whitespace_only_tool_name():
    valid, reason = validate_tool_decision(
        {
            'tool_name': '   ',
            'arguments': {'a': 1},
        }
    )
    assert not valid
    assert 'non-empty' in reason


def test_tool_name_not_string():
    valid, reason = validate_tool_decision(
        {
            'tool_name': 42,
            'arguments': {'a': 1},
        }
    )
    assert not valid
    assert 'must be string' in reason


def test_missing_arguments():
    valid, reason = validate_tool_decision({'tool_name': 'echo'})
    assert not valid
    assert 'arguments' in reason


def test_arguments_is_none():
    valid, reason = validate_tool_decision(
        {
            'tool_name': 'echo',
            'arguments': None,
        }
    )
    assert not valid
    assert 'arguments' in reason


def test_arguments_is_string():
    valid, reason = validate_tool_decision(
        {
            'tool_name': 'echo',
            'arguments': 'not-a-dict',
        }
    )
    assert not valid
    assert 'must be dict' in reason


def test_arguments_is_list():
    valid, reason = validate_tool_decision(
        {
            'tool_name': 'echo',
            'arguments': [1, 2, 3],
        }
    )
    assert not valid
    assert 'must be dict' in reason


def test_input_not_dict():
    valid, reason = validate_tool_decision([1, 2, 3])
    assert not valid
    assert 'not a dict' in reason


def test_empty_dict_still_works_if_tool_name_empty():
    valid, reason = validate_tool_decision({})
    assert not valid
    assert 'tool_name' in reason


def test_category_is_model_logic():
    exc = InvalidToolDecision('missing tool_name')
    assert exc.category == ErrorCategory.MODEL_LOGIC


def test_default_hint():
    exc = InvalidToolDecision('bad arguments')
    assert exc.hint is not None
    assert 'structurally invalid' in str(exc)


def test_raw_decision_preview():
    exc = InvalidToolDecision(
        'empty tool_name', raw_decision_preview='{"tool_name":""}'
    )
    assert exc.raw_decision_preview == '{"tool_name":""}'


def test_subclass_of_agent_harness_error():
    from teaagent.types import AgentHarnessError

    exc = InvalidToolDecision('test')
    assert isinstance(exc, AgentHarnessError)


def _make_runner() -> AgentRunner:
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


def test_invalid_tool_name_empty_string_causes_run_failed():
    runner = _make_runner()
    result = runner.run(
        task='echo something',
        decide=lambda _ctx: ToolRequest(
            tool_name='',
            arguments={'msg': 'hi'},
            call_id='bad-1',
        ),
        run_id='run-empty-tool',
    )
    assert result.status == f'failed:{ErrorCategory.MODEL_LOGIC}'
    assert result.error_message is not None
    assert 'tool_name' in result.error_message


def test_invalid_tool_name_whitespace_causes_run_failed():
    runner = _make_runner()
    result = runner.run(
        task='echo something',
        decide=lambda _ctx: ToolRequest(
            tool_name='   ',
            arguments={'msg': 'hi'},
            call_id='bad-2',
        ),
        run_id='run-ws-tool',
    )
    assert result.status == f'failed:{ErrorCategory.MODEL_LOGIC}'
    assert 'non-empty' in result.error_message


def test_null_arguments_causes_run_failed():
    runner = _make_runner()
    result = runner.run(
        task='echo something',
        decide=lambda _ctx: ToolRequest(
            tool_name='echo',
            arguments=None,
            call_id='bad-3',
        ),
        run_id='run-null-args',
    )
    assert result.status == f'failed:{ErrorCategory.MODEL_LOGIC}'
    assert 'arguments' in result.error_message


def test_valid_tool_request_proceeds_normally():
    runner = _make_runner()

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
    assert result.status == 'completed'
    assert result.tool_calls == 1
    assert result.final_answer.content == 'done'


def test_audit_event_recorded_on_invalid_decision():
    runner = _make_runner()
    runner.run(
        task='echo something',
        decide=lambda _ctx: ToolRequest(
            tool_name='',
            arguments=None,
            call_id='audit-bad',
        ),
        run_id='run-audit-test',
    )
    decision_events = [
        e for e in runner.audit.events if e.event_type == 'tool_decision_invalid'
    ]
    assert len(decision_events) == 1
    event = decision_events[0]
    assert event.payload['tool_name'] == ''
    assert 'tool_name' in event.payload['reason']
    assert 'raw_decision_preview' in event.payload


def test_audit_event_contains_run_failed_after_invalid():
    runner = _make_runner()
    runner.run(
        task='echo something',
        decide=lambda _ctx: ToolRequest(
            tool_name='',
            arguments=None,
            call_id='audit-bad-2',
        ),
        run_id='run-audit-fail',
    )
    failed_events = [e for e in runner.audit.events if e.event_type == 'run_failed']
    assert len(failed_events) >= 1
    assert failed_events[0].payload.get('category') == ErrorCategory.MODEL_LOGIC


def test_final_answer_bypasses_validation():
    runner = _make_runner()
    result = runner.run(
        task='simple question',
        decide=lambda _ctx: FinalAnswer(content='hello world'),
        run_id='run-final-bypass',
    )
    assert result.status == 'completed'
    assert result.final_answer.content == 'hello world'
    assert result.tool_calls == 0
