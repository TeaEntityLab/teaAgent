from __future__ import annotations

import unittest

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


class LLMToolDefinitionTests(unittest.TestCase):
    def test_defaults(self) -> None:
        t = LLMToolDefinition(name='foo', description='does foo')
        self.assertEqual(t.name, 'foo')
        self.assertEqual(t.description, 'does foo')
        self.assertEqual(t.input_schema, {'type': 'object', 'properties': {}})

    def test_custom_schema(self) -> None:
        schema = {'type': 'object', 'properties': {'x': {'type': 'integer'}}}
        t = LLMToolDefinition(name='bar', description='', input_schema=schema)
        self.assertEqual(t.input_schema['properties']['x']['type'], 'integer')


class LLMToolCallTests(unittest.TestCase):
    def test_fields(self) -> None:
        tc = LLMToolCall(
            tool_name='get_weather', tool_input={'city': 'NYC'}, call_id='c1'
        )
        self.assertEqual(tc.tool_name, 'get_weather')
        self.assertEqual(tc.tool_input['city'], 'NYC')
        self.assertEqual(tc.call_id, 'c1')

    def test_call_id_default(self) -> None:
        tc = LLMToolCall(tool_name='x', tool_input={})
        self.assertEqual(tc.call_id, '')


class LLMSafetyBlockTests(unittest.TestCase):
    def test_blocked_with_category(self) -> None:
        sb = LLMSafetyBlock(
            blocked=True, category=SafetyCategory.DANGEROUS, detail='test'
        )
        self.assertTrue(sb.blocked)
        self.assertEqual(sb.category, SafetyCategory.DANGEROUS)

    def test_not_blocked(self) -> None:
        sb = LLMSafetyBlock(blocked=False)
        self.assertFalse(sb.blocked)
        self.assertIsNone(sb.category)


class LLMRequestToolsTests(unittest.TestCase):
    def test_default_tools_empty(self) -> None:
        req = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
        self.assertEqual(req.tools, [])

    def test_tools_passed_through(self) -> None:
        tool = LLMToolDefinition(name='foo', description='bar')
        req = LLMRequest(
            messages=[LLMMessage(role='user', content='hi')],
            tools=[tool],
        )
        self.assertEqual(len(req.tools), 1)
        self.assertEqual(req.tools[0].name, 'foo')


class LLMResponseToolCallsTests(unittest.TestCase):
    def test_default_tool_calls_empty(self) -> None:
        resp = LLMResponse(provider='p', model='m', content='ok')
        self.assertEqual(resp.tool_calls, [])
        self.assertIsNone(resp.safety)

    def test_tool_calls_populated(self) -> None:
        tc = LLMToolCall(tool_name='t', tool_input={})
        resp = LLMResponse(provider='p', model='m', content='', tool_calls=[tc])
        self.assertEqual(len(resp.tool_calls), 1)


class ToolCallingTierTests(unittest.TestCase):
    def test_passed_when_tool_called(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.TOOL_CALLING,
            adapter_factory=_factory(_ToolCallingAdapter()),
            configuration_checker=_checker_ok,
        )
        self.assertEqual(len(report.results), 1)
        result = report.results[0]
        self.assertEqual(result.status, 'passed')
        check_names = {c.name for c in result.checks}
        self.assertIn('tool_call_invoked', check_names)

    def test_failed_when_no_tool_call(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.TOOL_CALLING,
            adapter_factory=_factory(_NoToolAdapter()),
            configuration_checker=_checker_ok,
        )
        self.assertEqual(report.results[0].status, 'failed')

    def test_skipped_when_not_configured(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.TOOL_CALLING,
            adapter_factory=_factory(_ToolCallingAdapter()),
            configuration_checker=lambda p: (False, 'key missing'),
        )
        self.assertEqual(report.results[0].status, 'skipped')


class SafetyTierTests(unittest.TestCase):
    def test_passed_on_api_level_block(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.SAFETY,
            adapter_factory=_factory(_SafetyBlockAdapter()),
            configuration_checker=_checker_ok,
        )
        result = report.results[0]
        self.assertEqual(result.status, 'passed')
        names = {c.name for c in result.checks}
        self.assertIn('safety_block', names)

    def test_passed_on_text_refusal(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.SAFETY,
            adapter_factory=_factory(_SafetyRefusalAdapter()),
            configuration_checker=_checker_ok,
        )
        self.assertEqual(report.results[0].status, 'passed')

    def test_failed_when_no_refusal(self) -> None:
        report = run_tiered_conformance(
            ['fake'],
            tier=ConformanceTier.SAFETY,
            adapter_factory=_factory(_SafetyNoRefusalAdapter()),
            configuration_checker=_checker_ok,
        )
        self.assertEqual(report.results[0].status, 'failed')


class ConformanceTierEnumTests(unittest.TestCase):
    def test_all_tiers_present(self) -> None:
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
            self.assertIn(expected, values)


if __name__ == '__main__':
    unittest.main()
