from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from teaagent import (
    LLMMessage,
    LLMProviderError,
    LLMRequest,
    LLMResponseFormatError,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)
from teaagent.cli import main
from teaagent.llm import LLMConfigurationError
from teaagent.llm._types import LLMHTTPError


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, headers, payload, *, timeout):
        self.calls.append(
            {'url': url, 'headers': headers, 'payload': payload, 'timeout': timeout}
        )
        return self.response


class SequenceTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, url, headers, payload, *, timeout):
        self.calls.append(
            {'url': url, 'headers': headers, 'payload': payload, 'timeout': timeout}
        )
        current = self.responses.pop(0)
        if isinstance(current, Exception):
            raise current
        return current


def test_available_providers_include_requested_adapters() -> None:
    assert available_providers() == [
        'aigateway',
        'claude',
        'deepseek',
        'fake',
        'gemini',
        'gpt',
        'grok',
        'mistral',
        'ollama',
        'opencodezen',
        'opencodezen-go',
        'openrouter',
        'vllm',
        'workers-ai',
    ]


def test_ollama_is_openai_compatible_without_api_key() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(os.environ, {}, clear=True):
        adapter = create_llm_adapter('ollama', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert transport.calls[0]['url'] == 'http://localhost:11434/v1/chat/completions'


def test_vllm_is_openai_compatible_without_api_key() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(os.environ, {}, clear=True):
        adapter = create_llm_adapter('vllm', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert transport.calls[0]['url'] == 'http://localhost:8000/v1/chat/completions'


def test_gpt_adapter_uses_openai_chat_completions_shape() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
        response = adapter.complete(
            LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
        )

    assert response.content == 'ok'
    call = transport.calls[0]
    assert call['url'] == 'https://api.openai.com/v1/chat/completions'
    assert call['headers']['authorization'] == 'Bearer key'
    assert call['payload']['messages'][0] == {'role': 'system', 'content': 'sys'}


def test_gpt_adapter_forwards_response_format_when_provided() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
        adapter.complete(
            LLMRequest(
                messages=[LLMMessage('user', 'hi')],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'x',
                        'strict': True,
                        'schema': {'type': 'object'},
                    },
                },
            )
        )

    assert 'response_format' in transport.calls[0]['payload']


def test_openai_adapter_fallbacks_when_response_format_not_supported() -> None:
    transport = SequenceTransport(
        [
            LLMHTTPError(
                'HTTP 400: {"error":{"message":"This response_format type is unavailable now","type":"invalid_request_error"}}',
                status_code=400,
            ),
            {'choices': [{'message': {'content': '{"type":"final","content":"ok"}'}}]},
        ]
    )
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
        response = adapter.complete(
            LLMRequest(
                messages=[LLMMessage('user', 'hi')],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'x',
                        'strict': True,
                        'schema': {'type': 'object'},
                    },
                },
            )
        )

    assert response.content == '{"type":"final","content":"ok"}'
    assert 'response_format' in transport.calls[0]['payload']
    assert 'response_format' not in transport.calls[1]['payload']


def test_opencodezen_go_ignores_response_format() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENCODEZEN_API_KEY': 'key',
            'OPENCODEZEN_BASE_URL': 'https://local.test/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('opencodezen-go', transport=transport)
        adapter.complete(
            LLMRequest(
                messages=[LLMMessage('user', 'hi')],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'x',
                        'strict': True,
                        'schema': {'type': 'object'},
                    },
                },
            )
        )

    assert 'response_format' not in transport.calls[0]['payload']


def test_opencodezen_ignores_response_format() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENCODEZEN_API_KEY': 'key',
            'OPENCODEZEN_COMPAT_BASE_URL': 'https://compat.local.test/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('opencodezen', transport=transport)
        adapter.complete(
            LLMRequest(
                messages=[LLMMessage('user', 'hi')],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'x',
                        'strict': True,
                        'schema': {'type': 'object'},
                    },
                },
            )
        )

    assert 'response_format' not in transport.calls[0]['payload']


def test_openrouter_adapter_uses_openai_compatible_shape() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {'OPENROUTER_API_KEY': 'key', 'OPENROUTER_APP_TITLE': 'TeaAgent'},
        clear=True,
    ):
        adapter = create_llm_adapter('openrouter', transport=transport)
        adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert transport.calls[0]['url'] == 'https://openrouter.ai/api/v1/chat/completions'
    assert transport.calls[0]['headers']['X-Title'] == 'TeaAgent'


def test_claude_adapter_uses_messages_api_shape() -> None:
    transport = FakeTransport({'content': [{'type': 'text', 'text': 'ok'}]})
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('claude', transport=transport)
        response = adapter.complete(
            LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
        )

    assert response.content == 'ok'
    call = transport.calls[0]
    assert call['url'] == 'https://api.anthropic.com/v1/messages'
    assert call['headers']['x-api-key'] == 'key'
    assert call['payload']['system'] == 'sys'


def test_gemini_adapter_uses_generate_content_shape() -> None:
    transport = FakeTransport(
        {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
    )
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gemini', transport=transport, model='gemini-test')
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert (
        transport.calls[0]['url']
        == 'https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent?key=key'
    )
    assert transport.calls[0]['payload']['contents'][0]['parts'][0]['text'] == 'hi'


def test_opencodezen_go_is_openai_compatible_and_configurable() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENCODEZEN_API_KEY': 'key',
            'OPENCODEZEN_BASE_URL': 'https://local.test/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('opencodezen-go', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert transport.calls[0]['url'] == 'https://local.test/v1/chat/completions'


def test_opencodezen_go_model_env_override_uses_underscore_key() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENCODEZEN_API_KEY': 'key',
            'OPENCODEZEN_GO_MODEL': 'deepseek-v4-pro',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('opencodezen-go', transport=transport)
        adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert transport.calls[0]['payload']['model'] == 'deepseek-v4-pro'


def test_opencodezen_is_openai_compatible_and_uses_its_api() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENCODEZEN_API_KEY': 'key',
            'OPENCODEZEN_COMPAT_BASE_URL': 'https://compat.local.test/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('opencodezen', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert transport.calls[0]['url'] == 'https://compat.local.test/v1/chat/completions'


def test_configuration_check_reports_missing_key() -> None:
    with patch.dict(os.environ, {}, clear=True):
        ok, message = check_llm_configuration('gpt')

    assert not ok
    assert 'OPENAI_API_KEY' in message


def test_cli_lists_model_providers() -> None:
    output = io.StringIO()

    with redirect_stdout(output):
        exit_code = main(['model', 'providers'])

    assert exit_code == 0
    assert 'claude' in json.loads(output.getvalue())


def test_unknown_provider_raises_configuration_error() -> None:
    with pytest.raises(LLMConfigurationError) as ctx:
        create_llm_adapter('nonexistent-provider')

    assert 'unknown provider' in str(ctx.value)
    assert 'Available:' in str(ctx.value)


def test_gemini_adapter_sends_system_instruction() -> None:
    transport = FakeTransport(
        {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
    )
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gemini', transport=transport, model='gemini-test')
        response = adapter.complete(
            LLMRequest(system='You are helpful', messages=[LLMMessage('user', 'hi')])
        )

    assert response.content == 'ok'
    call = transport.calls[0]
    assert 'systemInstruction' in call['payload']
    assert call['payload']['systemInstruction']['parts'][0]['text'] == 'You are helpful'


def test_openrouter_with_referrer_header() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'OPENROUTER_API_KEY': 'key',
            'OPENROUTER_HTTP_REFERER': 'https://myapp.com',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('openrouter', transport=transport)
        adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert transport.calls[0]['headers']['HTTP-Referer'] == 'https://myapp.com'


def test_workers_ai_uses_openai_compatible_shape() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'WORKERS_AI_BASE_URL': 'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    call = transport.calls[0]
    assert (
        call['url']
        == 'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1/chat/completions'
    )
    assert call['headers']['authorization'] == 'Bearer cf-token'
    assert call['payload']['model'] == '@cf/meta/llama-3.1-8b-instruct'


def test_workers_ai_uses_cloudflare_account_id_when_base_url_unset() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'CLOUDFLARE_ACCOUNT_ID': 'acct-123',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert (
        transport.calls[0]['url']
        == 'https://api.cloudflare.com/client/v4/accounts/acct-123/ai/v1/chat/completions'
    )


def test_workers_ai_requires_account_id_or_base_url() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        with pytest.raises(LLMConfigurationError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def test_workers_ai_prefers_workers_base_url_when_both_workers_and_compat_set() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'AIGATEWAY_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
            'WORKERS_AI_BASE_URL': 'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert (
        transport.calls[0]['url']
        == 'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1/chat/completions'
    )


def test_workers_ai_falls_back_to_aigateway_compat_base_url_when_workers_unset() -> (
    None
):
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'AIGATEWAY_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert (
        transport.calls[0]['url']
        == 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat/chat/completions'
    )


def test_aigateway_uses_compat_base_url() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'AIGATEWAY_BASE_URL': 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('aigateway', transport=transport)
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'
    assert (
        transport.calls[0]['url']
        == 'https://gateway.ai.cloudflare.com/v1/acct/gw/compat/chat/completions'
    )


def test_provider_extra_headers_supports_aig_auth() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
    with patch.dict(
        os.environ,
        {
            'CLOUDFLARE_API_TOKEN': 'cf-token',
            'WORKERS_AI_BASE_URL': 'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1',
            'WORKERS_AI_EXTRA_HEADERS': '{"cf-aig-authorization":"Bearer aig-token"}',
        },
        clear=True,
    ):
        adapter = create_llm_adapter('workers-ai', transport=transport)
        adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert transport.calls[0]['headers']['cf-aig-authorization'] == 'Bearer aig-token'


def test_openai_streaming_reads_sse_lines_incrementally() -> None:
    chunks: list[str] = []
    streaming_lines = [
        b'data: {"choices":[{"delta":{"content":"he"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"llo"}}],"usage":{"prompt_tokens":2,"completion_tokens":3}}\n',
        b'data: [DONE]\n',
    ]

    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', model='gpt-test')
        adapter._streaming_lines = streaming_lines  # type: ignore[attr-defined]
        result = adapter.complete(
            LLMRequest(
                messages=[LLMMessage('user', 'hi')],
                stream=True,
                on_chunk=chunks.append,
            )
        )

    assert chunks == ['he', 'llo']
    assert result.content == 'hello'
    assert result.input_tokens == 2
    assert result.output_tokens == 3


def test_openai_adapter_reports_provider_error_payload() -> None:
    transport = FakeTransport({'error': {'message': 'blocked'}})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')

        with pytest.raises(LLMProviderError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def test_openai_adapter_rejects_malformed_response() -> None:
    transport = FakeTransport({'choices': []})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')

        with pytest.raises(LLMResponseFormatError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def test_openai_adapter_accepts_message_content_parts_list() -> None:
    transport = FakeTransport(
        {'choices': [{'message': {'content': [{'type': 'output_text', 'text': 'ok'}]}}]}
    )
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'


def test_openai_adapter_accepts_choice_text_fallback() -> None:
    transport = FakeTransport({'choices': [{'message': {'content': ''}, 'text': 'ok'}]})
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
        response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    assert response.content == 'ok'


def test_openai_adapter_accepts_reasoning_content_fallback() -> None:
    from teaagent.llm._extract import _extract_openai_content

    payload = {
        'choices': [
            {
                'message': {
                    'content': None,
                    'reasoning_content': 'assistant answer text',
                }
            }
        ]
    }
    assert _extract_openai_content('opencodezen-go', payload) == 'assistant answer text'


def test_openai_adapter_accepts_text_content_part_type() -> None:
    from teaagent.llm._extract import _extract_openai_content

    payload = {
        'choices': [{'message': {'content': [{'type': 'text', 'text': 'part text'}]}}]
    }
    assert _extract_openai_content('opencodezen-go', payload) == 'part text'


def test_claude_adapter_rejects_malformed_response() -> None:
    transport = FakeTransport({'content': [{'type': 'tool_use'}]})
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('claude', transport=transport)

        with pytest.raises(LLMResponseFormatError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def test_gemini_adapter_rejects_malformed_response() -> None:
    transport = FakeTransport({'candidates': [{'content': {'parts': []}}]})
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gemini', transport=transport)

        with pytest.raises(LLMResponseFormatError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def test_gemini_adapter_reports_safety_block() -> None:
    transport = FakeTransport({'promptFeedback': {'blockReason': 'SAFETY'}})
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
        adapter = create_llm_adapter('gemini', transport=transport)

        with pytest.raises(LLMProviderError):
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


def _provider_rates(provider: str) -> tuple[float, float]:
    """RISK-02: fake/ollama/vllm must have non-zero cost rates so budget guards fire."""
    from teaagent.llm._config import (
        PROVIDER_COST_PER_1K_INPUT,
        PROVIDER_COST_PER_1K_OUTPUT,
    )

    return PROVIDER_COST_PER_1K_INPUT[provider], PROVIDER_COST_PER_1K_OUTPUT[provider]


def test_fake_cost_rates_nonzero() -> None:
    in_rate, out_rate = _provider_rates('fake')
    assert in_rate > 0.0, 'fake input cost rate must be > 0'
    assert out_rate > 0.0, 'fake output cost rate must be > 0'


def test_ollama_cost_rates_nonzero() -> None:
    in_rate, out_rate = _provider_rates('ollama')
    assert in_rate > 0.0, 'ollama input cost rate must be > 0'
    assert out_rate > 0.0, 'ollama output cost rate must be > 0'


def test_vllm_cost_rates_nonzero() -> None:
    in_rate, out_rate = _provider_rates('vllm')
    assert in_rate > 0.0, 'vllm input cost rate must be > 0'
    assert out_rate > 0.0, 'vllm output cost rate must be > 0'
