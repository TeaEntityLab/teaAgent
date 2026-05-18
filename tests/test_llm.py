from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

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


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, headers, payload, *, timeout):
        self.calls.append(
            {'url': url, 'headers': headers, 'payload': payload, 'timeout': timeout}
        )
        return self.response


class LLMAdapterTests(unittest.TestCase):
    def test_available_providers_include_requested_adapters(self) -> None:
        self.assertEqual(
            available_providers(),
            [
                'claude',
                'deepseek',
                'gemini',
                'gpt',
                'grok',
                'mistral',
                'ollama',
                'opencodezen-go',
                'openrouter',
                'vllm',
                'workers-ai',
            ],
        )

    def test_ollama_is_openai_compatible_without_api_key(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(os.environ, {}, clear=True):
            adapter = create_llm_adapter('ollama', transport=transport)
            response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'], 'http://localhost:11434/v1/chat/completions'
        )

    def test_vllm_is_openai_compatible_without_api_key(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(os.environ, {}, clear=True):
            adapter = create_llm_adapter('vllm', transport=transport)
            response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'], 'http://localhost:8000/v1/chat/completions'
        )

    def test_gpt_adapter_uses_openai_chat_completions_shape(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')
            response = adapter.complete(
                LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(call['headers']['authorization'], 'Bearer key')
        self.assertEqual(
            call['payload']['messages'][0], {'role': 'system', 'content': 'sys'}
        )

    def test_gpt_adapter_forwards_response_format_when_provided(self) -> None:
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

        self.assertIn('response_format', transport.calls[0]['payload'])

    def test_openrouter_adapter_uses_openai_compatible_shape(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(
            os.environ,
            {'OPENROUTER_API_KEY': 'key', 'OPENROUTER_APP_TITLE': 'TeaAgent'},
            clear=True,
        ):
            adapter = create_llm_adapter('openrouter', transport=transport)
            adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(
            transport.calls[0]['url'], 'https://openrouter.ai/api/v1/chat/completions'
        )
        self.assertEqual(transport.calls[0]['headers']['X-Title'], 'TeaAgent')

    def test_claude_adapter_uses_messages_api_shape(self) -> None:
        transport = FakeTransport({'content': [{'type': 'text', 'text': 'ok'}]})
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('claude', transport=transport)
            response = adapter.complete(
                LLMRequest(system='sys', messages=[LLMMessage('user', 'hi')])
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://api.anthropic.com/v1/messages')
        self.assertEqual(call['headers']['x-api-key'], 'key')
        self.assertEqual(call['payload']['system'], 'sys')

    def test_gemini_adapter_uses_generate_content_shape(self) -> None:
        transport = FakeTransport(
            {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        )
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter(
                'gemini', transport=transport, model='gemini-test'
            )
            response = adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'],
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent?key=key',
        )
        self.assertEqual(
            transport.calls[0]['payload']['contents'][0]['parts'][0]['text'], 'hi'
        )

    def test_opencodezen_go_is_openai_compatible_and_configurable(self) -> None:
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

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'], 'https://local.test/v1/chat/completions'
        )

    def test_opencodezen_go_model_env_override_uses_underscore_key(self) -> None:
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

        self.assertEqual(transport.calls[0]['payload']['model'], 'deepseek-v4-pro')

    def test_configuration_check_reports_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ok, message = check_llm_configuration('gpt')

        self.assertFalse(ok)
        self.assertIn('OPENAI_API_KEY', message)

    def test_cli_lists_model_providers(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(['model', 'providers'])

        self.assertEqual(exit_code, 0)
        self.assertIn('claude', json.loads(output.getvalue()))

    def test_unknown_provider_raises_configuration_error(self) -> None:
        with self.assertRaises(LLMConfigurationError) as ctx:
            create_llm_adapter('nonexistent-provider')

        self.assertIn('unknown provider', str(ctx.exception))
        self.assertIn('Available:', str(ctx.exception))

    def test_gemini_adapter_sends_system_instruction(self) -> None:
        transport = FakeTransport(
            {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}
        )
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter(
                'gemini', transport=transport, model='gemini-test'
            )
            response = adapter.complete(
                LLMRequest(
                    system='You are helpful', messages=[LLMMessage('user', 'hi')]
                )
            )

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertIn('systemInstruction', call['payload'])
        self.assertEqual(
            call['payload']['systemInstruction']['parts'][0]['text'], 'You are helpful'
        )

    def test_openrouter_with_referrer_header(self) -> None:
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

        self.assertEqual(
            transport.calls[0]['headers']['HTTP-Referer'], 'https://myapp.com'
        )

    def test_workers_ai_uses_openai_compatible_shape(self) -> None:
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

        self.assertEqual(response.content, 'ok')
        call = transport.calls[0]
        self.assertEqual(
            call['url'],
            'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1/chat/completions',
        )
        self.assertEqual(call['headers']['authorization'], 'Bearer cf-token')
        self.assertEqual(call['payload']['model'], '@cf/meta/llama-3.1-8b-instruct')

    def test_workers_ai_uses_cloudflare_account_id_when_base_url_unset(self) -> None:
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

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'],
            'https://api.cloudflare.com/client/v4/accounts/acct-123/ai/v1/chat/completions',
        )

    def test_workers_ai_requires_account_id_or_base_url(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'content': 'ok'}}]})
        with patch.dict(
            os.environ,
            {
                'CLOUDFLARE_API_TOKEN': 'cf-token',
            },
            clear=True,
        ):
            adapter = create_llm_adapter('workers-ai', transport=transport)
            with self.assertRaises(LLMConfigurationError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    def test_workers_ai_prefers_workers_base_url_when_both_workers_and_compat_set(
        self,
    ) -> None:
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

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'],
            'https://api.cloudflare.com/client/v4/accounts/abc/ai/v1/chat/completions',
        )

    def test_workers_ai_falls_back_to_aigateway_compat_base_url_when_workers_unset(
        self,
    ) -> None:
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

        self.assertEqual(response.content, 'ok')
        self.assertEqual(
            transport.calls[0]['url'],
            'https://gateway.ai.cloudflare.com/v1/acct/gw/compat/chat/completions',
        )

    def test_provider_extra_headers_supports_aig_auth(self) -> None:
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

        self.assertEqual(
            transport.calls[0]['headers']['cf-aig-authorization'],
            'Bearer aig-token',
        )

    def test_openai_streaming_reads_sse_lines_incrementally(self) -> None:
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

        self.assertEqual(chunks, ['he', 'llo'])
        self.assertEqual(result.content, 'hello')
        self.assertEqual(result.input_tokens, 2)
        self.assertEqual(result.output_tokens, 3)

    def test_openai_adapter_reports_provider_error_payload(self) -> None:
        transport = FakeTransport({'error': {'message': 'blocked'}})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')

            with self.assertRaises(LLMProviderError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    def test_openai_adapter_rejects_malformed_response(self) -> None:
        transport = FakeTransport({'choices': []})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gpt', transport=transport, model='gpt-test')

            with self.assertRaises(LLMResponseFormatError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    def test_claude_adapter_rejects_malformed_response(self) -> None:
        transport = FakeTransport({'content': [{'type': 'tool_use'}]})
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('claude', transport=transport)

            with self.assertRaises(LLMResponseFormatError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    def test_gemini_adapter_rejects_malformed_response(self) -> None:
        transport = FakeTransport({'candidates': [{'content': {'parts': []}}]})
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gemini', transport=transport)

            with self.assertRaises(LLMResponseFormatError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))

    def test_gemini_adapter_reports_safety_block(self) -> None:
        transport = FakeTransport({'promptFeedback': {'blockReason': 'SAFETY'}})
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'key'}, clear=True):
            adapter = create_llm_adapter('gemini', transport=transport)

            with self.assertRaises(LLMProviderError):
                adapter.complete(LLMRequest(messages=[LLMMessage('user', 'hi')]))


if __name__ == '__main__':
    unittest.main()
