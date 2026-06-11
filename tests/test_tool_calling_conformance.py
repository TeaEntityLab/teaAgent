from __future__ import annotations

from teaagent.llm._types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMSafetyBlock,
    LLMToolCall,
    LLMToolDefinition,
    SafetyCategory,
)
from teaagent.llm_conformance import run_tiered_conformance
from teaagent.llm_conformance._types import ConformanceTier


def _make_response(
    *,
    content: str = 'ok',
    tool_calls: list[LLMToolCall] | None = None,
    safety: LLMSafetyBlock | None = None,
) -> LLMResponse:
    return LLMResponse(
        provider='fake',
        model='fake-model',
        content=content,
        tool_calls=tool_calls or [],
        safety=safety,
    )


class _ToolCallingAdapter:
    """Fake adapter that returns a tool call for any request with tools."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        if request.tools:
            return _make_response(
                content='',
                tool_calls=[
                    LLMToolCall(
                        tool_name=request.tools[0].name,
                        tool_input={},
                        call_id='call-1',
                    )
                ],
            )
        return _make_response(content='ok')


class _NoToolAdapter:
    """Fake adapter that never returns tool calls."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        return _make_response(content='ok')


class _SafetyBlockAdapter:
    """Returns an API-level safety block for dangerous prompts; 'ok' otherwise."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        last = request.messages[-1].content.lower()
        if 'dangerous' in last or 'chemicals' in last or 'synthesize' in last:
            return _make_response(
                content='',
                safety=LLMSafetyBlock(blocked=True, category=SafetyCategory.DANGEROUS),
            )
        return _make_response(content='ok')


class _SafetyRefusalAdapter:
    """Returns a text refusal for dangerous prompts; 'ok' otherwise."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        last = request.messages[-1].content.lower()
        if 'dangerous' in last or 'chemicals' in last or 'synthesize' in last:
            return _make_response(content='I cannot provide instructions for that.')
        return _make_response(content='ok')


class _SafetyNoRefusalAdapter:
    """Complies with any prompt (no safety guardrails)."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        last = request.messages[-1].content.lower()
        if 'dangerous' in last or 'chemicals' in last or 'synthesize' in last:
            return _make_response(content='Here are the steps: mix chemicals A and B.')
        return _make_response(content='ok')


def _factory(adapter: object):
    return lambda provider, *, model=None: adapter


def _checker_ok(provider: str) -> tuple[bool, str]:
    return True, 'configured'


def test_llm_tool_definition_defaults() -> None:
    t = LLMToolDefinition(name='foo', description='does foo')
    assert t.name == 'foo'
    assert t.description == 'does foo'
    assert t.input_schema == {'type': 'object', 'properties': {}}


def test_llm_tool_definition_custom_schema() -> None:
    schema = {'type': 'object', 'properties': {'x': {'type': 'integer'}}}
    t = LLMToolDefinition(name='bar', description='', input_schema=schema)
    assert t.input_schema['properties']['x']['type'] == 'integer'


def test_llm_tool_call_fields() -> None:
    tc = LLMToolCall(tool_name='get_weather', tool_input={'city': 'NYC'}, call_id='c1')
    assert tc.tool_name == 'get_weather'
    assert tc.tool_input['city'] == 'NYC'
    assert tc.call_id == 'c1'


def test_llm_tool_call_call_id_default() -> None:
    tc = LLMToolCall(tool_name='x', tool_input={})
    assert tc.call_id == ''


def test_llm_safety_block_blocked_with_category() -> None:
    sb = LLMSafetyBlock(blocked=True, category=SafetyCategory.DANGEROUS, detail='test')
    assert sb.blocked
    assert sb.category == SafetyCategory.DANGEROUS


def test_llm_safety_block_not_blocked() -> None:
    sb = LLMSafetyBlock(blocked=False)
    assert not sb.blocked
    assert sb.category is None


def test_llm_request_tools_default_tools_empty() -> None:
    req = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    assert req.tools == []


def test_llm_request_tools_tools_passed_through() -> None:
    tool = LLMToolDefinition(name='foo', description='bar')
    req = LLMRequest(
        messages=[LLMMessage(role='user', content='hi')],
        tools=[tool],
    )
    assert len(req.tools) == 1
    assert req.tools[0].name == 'foo'


def test_llm_response_tool_calls_default_tool_calls_empty() -> None:
    resp = LLMResponse(provider='p', model='m', content='ok')
    assert resp.tool_calls == []
    assert resp.safety is None


def test_llm_response_tool_calls_tool_calls_populated() -> None:
    tc = LLMToolCall(tool_name='t', tool_input={})
    resp = LLMResponse(provider='p', model='m', content='', tool_calls=[tc])
    assert len(resp.tool_calls) == 1


def test_tool_calling_tier_passed_when_tool_called() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.TOOL_CALLING,
        adapter_factory=_factory(_ToolCallingAdapter()),
        configuration_checker=_checker_ok,
    )
    assert len(report.results) == 1
    result = report.results[0]
    assert result.status == 'passed'
    check_names = {c.name for c in result.checks}
    assert 'tool_call_invoked' in check_names


def test_tool_calling_tier_failed_when_no_tool_call() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.TOOL_CALLING,
        adapter_factory=_factory(_NoToolAdapter()),
        configuration_checker=_checker_ok,
    )
    assert report.results[0].status == 'failed'


def test_tool_calling_tier_skipped_when_not_configured() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.TOOL_CALLING,
        adapter_factory=_factory(_ToolCallingAdapter()),
        configuration_checker=lambda p: (False, 'key missing'),
    )
    assert report.results[0].status == 'skipped'


def test_safety_tier_passed_on_api_level_block() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.SAFETY,
        adapter_factory=_factory(_SafetyBlockAdapter()),
        configuration_checker=_checker_ok,
    )
    result = report.results[0]
    assert result.status == 'passed'
    names = {c.name for c in result.checks}
    assert 'safety_block' in names


def test_safety_tier_passed_on_text_refusal() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.SAFETY,
        adapter_factory=_factory(_SafetyRefusalAdapter()),
        configuration_checker=_checker_ok,
    )
    assert report.results[0].status == 'passed'


def test_safety_tier_failed_when_no_refusal() -> None:
    report = run_tiered_conformance(
        ['fake'],
        tier=ConformanceTier.SAFETY,
        adapter_factory=_factory(_SafetyNoRefusalAdapter()),
        configuration_checker=_checker_ok,
    )
    assert report.results[0].status == 'failed'


def test_conformance_tier_enum_all_tiers_present() -> None:
    values = {t.value for t in ConformanceTier}
    for expected in (
        'smoke',
        'contract',
        'streaming',
        'structured_output',
        'latency',
        'tool_calling',
        'safety',
    ):
        assert expected in values
