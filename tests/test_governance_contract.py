"""Contract tests for the provider-agnostic governance metadata layer (W11)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from teaagent.llm._adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
    _build_governance,
    _gemini_refusal_class,
    _openai_refusal_class,
)
from teaagent.llm._fake_adapter import FakeLLMAdapter
from teaagent.llm._types import (
    CostSource,
    GovernanceMetadata,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMSafetyBlock,
    ProviderConfig,
    RefusalClass,
    SafetyCategory,
    ToolCallFormat,
)

# ---------------------------------------------------------------------------
# GovernanceMetadata dataclass contract
# ---------------------------------------------------------------------------


def test_governance_metadata_has_all_required_fields() -> None:
    required = [
        'provider_id',
        'model_id',
        'input_tokens',
        'output_tokens',
        'tokens_known',
        'estimated_cost_cents',
        'cost_source',
        'actual_cost_cents',
        'tool_call_format',
        'refusal_class',
        'streaming_supported',
    ]
    gm = GovernanceMetadata(
        provider_id='p',
        model_id='m',
        input_tokens=0,
        output_tokens=0,
        tokens_known=False,
        estimated_cost_cents=0.0,
        cost_source=CostSource.UNKNOWN,
        actual_cost_cents=None,
        tool_call_format=ToolCallFormat.NONE,
        refusal_class=RefusalClass.NONE,
        streaming_supported=False,
    )
    for field in required:
        assert hasattr(gm, field), f'GovernanceMetadata is missing field: {field}'


def test_governance_metadata_is_frozen() -> None:
    gm = GovernanceMetadata(
        provider_id='p',
        model_id='m',
        input_tokens=0,
        output_tokens=0,
        tokens_known=False,
        estimated_cost_cents=0.0,
        cost_source=CostSource.UNKNOWN,
        actual_cost_cents=None,
        tool_call_format=ToolCallFormat.NONE,
        refusal_class=RefusalClass.NONE,
        streaming_supported=False,
    )
    with pytest.raises((TypeError, AttributeError)):
        gm.provider_id = 'mutated'


# ---------------------------------------------------------------------------
# LLMResponse auto-fill via __post_init__
# ---------------------------------------------------------------------------


def test_llm_response_autofills_governance_when_omitted_no_tokens() -> None:
    r = LLMResponse(provider='fake', model='fake-model', content='hi')
    assert r.governance is not None
    assert r.governance.cost_source == CostSource.UNKNOWN
    assert r.governance.tokens_known is False
    assert r.governance.estimated_cost_cents == 0.0


def test_llm_response_autofills_governance_when_omitted_with_tokens() -> None:
    r = LLMResponse(
        provider='fake',
        model='fake-model',
        content='hi',
        input_tokens=100,
        output_tokens=50,
    )
    assert r.governance is not None
    assert r.governance.cost_source == CostSource.ESTIMATED
    assert r.governance.tokens_known is True


def test_llm_response_explicit_governance_not_overwritten() -> None:
    explicit = GovernanceMetadata(
        provider_id='myp',
        model_id='mym',
        input_tokens=1,
        output_tokens=1,
        tokens_known=True,
        estimated_cost_cents=999.0,
        cost_source=CostSource.ESTIMATED,
        actual_cost_cents=None,
        tool_call_format=ToolCallFormat.OPENAI,
        refusal_class=RefusalClass.NONE,
        streaming_supported=True,
    )
    r = LLMResponse(
        provider='fake', model='fake-model', content='hi', governance=explicit
    )
    assert r.governance is explicit
    assert r.governance.estimated_cost_cents == 999.0


def test_estimated_cost_cents_property_delegates_to_governance() -> None:
    r = LLMResponse(
        provider='fake',
        model='fake-model',
        content='hi',
        input_tokens=100,
        output_tokens=50,
    )
    assert r.estimated_cost_cents == r.governance.estimated_cost_cents


# ---------------------------------------------------------------------------
# Unknown cost must never be presented as actual cost
# ---------------------------------------------------------------------------


def test_unknown_cost_actual_cost_is_none() -> None:
    r = LLMResponse(provider='fake', model='fake-model', content='hi')
    assert r.governance is not None
    assert r.governance.actual_cost_cents is None


def test_estimated_cost_with_known_tokens_actual_still_none() -> None:
    r = LLMResponse(
        provider='fake',
        model='fake-model',
        content='hi',
        input_tokens=100,
        output_tokens=50,
    )
    assert r.governance is not None
    assert r.governance.actual_cost_cents is None


def test_unknown_cost_source_gives_zero_estimated_cost() -> None:
    r = LLMResponse(provider='fake', model='fake-model', content='hi')
    assert r.governance is not None
    assert r.governance.cost_source == CostSource.UNKNOWN
    assert r.governance.estimated_cost_cents == 0.0


# ---------------------------------------------------------------------------
# Refusal class helpers
# ---------------------------------------------------------------------------


def test_openai_refusal_class_none_for_normal_finish() -> None:
    response: dict[str, Any] = {'choices': [{'finish_reason': 'stop'}]}
    assert _openai_refusal_class(response) == RefusalClass.NONE


def test_openai_refusal_class_content_filter() -> None:
    response: dict[str, Any] = {'choices': [{'finish_reason': 'content_filter'}]}
    assert _openai_refusal_class(response) == RefusalClass.CONTENT_FILTER


def test_openai_refusal_class_none_for_empty_choices() -> None:
    assert _openai_refusal_class({}) == RefusalClass.NONE
    assert _openai_refusal_class({'choices': []}) == RefusalClass.NONE


def test_gemini_refusal_class_safety_block() -> None:
    safety = LLMSafetyBlock(blocked=True, category=SafetyCategory.HARASSMENT)
    assert _gemini_refusal_class(safety) == RefusalClass.SAFETY_BLOCK


def test_gemini_refusal_class_none_for_unblocked() -> None:
    safety = LLMSafetyBlock(blocked=False)
    assert _gemini_refusal_class(safety) == RefusalClass.NONE


def test_gemini_refusal_class_none_for_no_safety() -> None:
    assert _gemini_refusal_class(None) == RefusalClass.NONE


# ---------------------------------------------------------------------------
# _build_governance helper
# ---------------------------------------------------------------------------


def test_build_governance_estimated_when_tokens_known() -> None:
    gm = _build_governance(
        'fake',
        'fake-model',
        100,
        50,
        tokens_known=True,
        refusal_class=RefusalClass.NONE,
        tool_call_format=ToolCallFormat.OPENAI,
        streaming_supported=True,
    )
    assert gm.cost_source == CostSource.ESTIMATED
    assert gm.tokens_known is True
    assert gm.tool_call_format == ToolCallFormat.OPENAI
    assert gm.streaming_supported is True


def test_build_governance_unknown_when_no_tokens() -> None:
    gm = _build_governance(
        'ollama',
        'llama3',
        0,
        0,
        tokens_known=False,
        refusal_class=RefusalClass.NONE,
        tool_call_format=ToolCallFormat.NONE,
        streaming_supported=True,
    )
    assert gm.cost_source == CostSource.UNKNOWN
    assert gm.estimated_cost_cents == 0.0
    assert gm.actual_cost_cents is None


# ---------------------------------------------------------------------------
# Fake adapter compliance
# ---------------------------------------------------------------------------


def test_fake_adapter_response_governance_populated() -> None:
    adapter = FakeLLMAdapter(provider='fake', model='fake-model')
    request = LLMRequest(messages=[LLMMessage(role='user', content='hello')])
    response = adapter.complete(request)
    assert response.governance is not None
    assert response.governance.provider_id == 'fake'
    assert response.governance.model_id == 'fake-model'


def test_fake_adapter_default_response_unknown_cost() -> None:
    adapter = FakeLLMAdapter()
    request = LLMRequest(messages=[LLMMessage(role='user', content='hello')])
    response = adapter.complete(request)
    assert response.governance is not None
    assert response.governance.cost_source == CostSource.UNKNOWN


def test_fake_adapter_scripted_response_with_tokens_estimated_cost() -> None:
    scripted = LLMResponse(
        provider='fake',
        model='fake-model',
        content='scripted',
        input_tokens=200,
        output_tokens=100,
    )
    adapter = FakeLLMAdapter(responses=[scripted])
    request = LLMRequest(messages=[LLMMessage(role='user', content='hello')])
    response = adapter.complete(request)
    assert response.governance is not None
    assert response.governance.cost_source == CostSource.ESTIMATED
    assert response.governance.tokens_known is True


# ---------------------------------------------------------------------------
# OpenAI-compatible adapter governance contract via mock transport
# ---------------------------------------------------------------------------


def _make_openai_config(provider: str = 'gpt') -> ProviderConfig:
    return ProviderConfig(
        name=provider,
        api_key_env='OPENAI_API_KEY',
        default_model='gpt-4o',
        base_url='https://api.openai.com/v1',
        api_key='test-key',
    )


def test_openai_adapter_governance_with_usage() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'choices': [
            {
                'message': {'content': 'hello', 'role': 'assistant'},
                'finish_reason': 'stop',
            }
        ],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
        'model': 'gpt-4o',
    }
    adapter = OpenAICompatibleAdapter(_make_openai_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.cost_source == CostSource.ESTIMATED
    assert response.governance.tokens_known is True
    assert response.governance.input_tokens == 10
    assert response.governance.output_tokens == 5
    assert response.governance.streaming_supported is True
    assert response.governance.actual_cost_cents is None
    assert response.governance.tool_call_format == ToolCallFormat.NONE


def test_openai_adapter_governance_without_usage() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'choices': [
            {
                'message': {'content': 'hello', 'role': 'assistant'},
                'finish_reason': 'stop',
            }
        ],
        'model': 'gpt-4o',
    }
    adapter = OpenAICompatibleAdapter(_make_openai_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.cost_source == CostSource.UNKNOWN
    assert response.governance.tokens_known is False
    assert response.governance.estimated_cost_cents == 0.0


def test_openai_refusal_class_helper_content_filter() -> None:
    """content_filter finish_reason is classified correctly by the helper.

    In practice the adapter raises LLMResponseFormatError on empty content,
    so the refusal_class is only observable on responses where content is present
    but finish_reason is still content_filter (partial responses).
    """
    raw: dict[str, Any] = {'choices': [{'finish_reason': 'content_filter'}]}
    assert _openai_refusal_class(raw) == RefusalClass.CONTENT_FILTER


def test_openai_adapter_governance_tool_call_format() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'choices': [
            {
                'message': {
                    'content': None,
                    'role': 'assistant',
                    'tool_calls': [
                        {
                            'id': 'call_1',
                            'function': {
                                'name': 'read_file',
                                'arguments': '{"path": "/tmp/f"}',
                            },
                        }
                    ],
                },
                'finish_reason': 'tool_calls',
            }
        ],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
        'model': 'gpt-4o',
    }
    adapter = OpenAICompatibleAdapter(_make_openai_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.tool_call_format == ToolCallFormat.OPENAI


# ---------------------------------------------------------------------------
# Claude adapter governance contract via mock transport
# ---------------------------------------------------------------------------


def _make_claude_config() -> ProviderConfig:
    return ProviderConfig(
        name='claude',
        api_key_env='ANTHROPIC_API_KEY',
        default_model='claude-3-5-sonnet-20241022',
        base_url='https://api.anthropic.com/v1',
        api_key='test-key',
    )


def test_claude_adapter_governance_with_usage() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'content': [{'type': 'text', 'text': 'hello'}],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 12, 'output_tokens': 8},
        'model': 'claude-3-5-sonnet-20241022',
    }

    adapter = ClaudeAdapter(_make_claude_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.cost_source == CostSource.ESTIMATED
    assert response.governance.tokens_known is True
    assert response.governance.input_tokens == 12
    assert response.governance.output_tokens == 8
    assert response.governance.tool_call_format == ToolCallFormat.NONE
    assert response.governance.refusal_class == RefusalClass.NONE
    assert response.governance.streaming_supported is True
    assert response.governance.actual_cost_cents is None


def test_claude_adapter_governance_tool_call_format() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'content': [
            {'type': 'text', 'text': 'Using bash:'},
            {
                'type': 'tool_use',
                'id': 'toolu_1',
                'name': 'bash',
                'input': {'cmd': 'ls'},
            },
        ],
        'stop_reason': 'tool_use',
        'usage': {'input_tokens': 20, 'output_tokens': 10},
        'model': 'claude-3-5-sonnet-20241022',
    }

    adapter = ClaudeAdapter(_make_claude_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.tool_call_format == ToolCallFormat.ANTHROPIC


# ---------------------------------------------------------------------------
# Gemini adapter governance contract via mock transport
# ---------------------------------------------------------------------------


def _make_gemini_config() -> ProviderConfig:
    return ProviderConfig(
        name='gemini',
        api_key_env='GEMINI_API_KEY',
        default_model='gemini-1.5-pro',
        base_url='https://generativelanguage.googleapis.com/v1beta',
        api_key='test-key',
    )


def test_gemini_adapter_governance_with_usage() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'candidates': [
            {
                'content': {'parts': [{'text': 'hello'}], 'role': 'model'},
                'finishReason': 'STOP',
            }
        ],
        'usageMetadata': {'promptTokenCount': 8, 'candidatesTokenCount': 4},
    }
    adapter = GeminiAdapter(_make_gemini_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.cost_source == CostSource.ESTIMATED
    assert response.governance.tokens_known is True
    assert response.governance.input_tokens == 8
    assert response.governance.output_tokens == 4
    assert response.governance.refusal_class == RefusalClass.NONE
    assert response.governance.streaming_supported is True


def test_gemini_refusal_class_helper_safety_block() -> None:
    """Gemini SAFETY blocks are classified via _gemini_refusal_class (adapter raises on empty content).

    In practice the Gemini adapter raises LLMResponseFormatError for a blocked
    candidate with empty content, so refusal_class is observable on the
    response only when the provider includes partial text alongside the block.
    """
    safety = LLMSafetyBlock(blocked=True, category=SafetyCategory.HARASSMENT)
    assert _gemini_refusal_class(safety) == RefusalClass.SAFETY_BLOCK


def test_gemini_adapter_governance_without_usage_metadata() -> None:
    transport = MagicMock()
    transport.post_json.return_value = {
        'candidates': [
            {
                'content': {'parts': [{'text': 'hello'}], 'role': 'model'},
                'finishReason': 'STOP',
            }
        ],
    }
    adapter = GeminiAdapter(_make_gemini_config(), transport=transport)
    request = LLMRequest(messages=[LLMMessage(role='user', content='hi')])
    response = adapter.complete(request)

    assert response.governance is not None
    assert response.governance.cost_source == CostSource.UNKNOWN
    assert response.governance.tokens_known is False
    assert response.governance.estimated_cost_cents == 0.0


# ---------------------------------------------------------------------------
# Provider fallback: unknown cost not contributed to budget total
# ---------------------------------------------------------------------------


def test_unknown_cost_not_contributed_to_budget() -> None:
    """Simulate the chat_agent accumulation guard: UNKNOWN cost adds 0 to total."""
    total_cost = 0.0
    from teaagent.llm._types import CostSource as CS

    for _ in range(3):
        r = LLMResponse(provider='ollama', model='llama3', content='hi')
        assert r.governance is not None
        if r.governance.cost_source != CS.UNKNOWN:
            total_cost += r.estimated_cost_cents

    assert total_cost == 0.0, 'UNKNOWN cost must not accumulate in budget tracking'
